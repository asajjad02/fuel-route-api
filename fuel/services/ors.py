"""OpenRouteService client: driving routes and address search, with a local quota guard.

Coordinates here are (lat, lon); ORS uses [lon, lat], so we flip only at this boundary.
"""

import time

import requests
from django.conf import settings
from django.core.cache import cache

from fuel.constants import (
    MINUTE,
    ORS_BASE_URL,
    ORS_QUOTAS,
    ORS_TIMEOUT_SECONDS,
    ORS_USA_COUNTRY_ID,
)
from fuel.errors import InvalidLocation, QuotaExceeded, RouteNotFound, RoutingServiceError


def get_route(start, finish):
    """Return (road as [(lat, lon), ...], distance in miles) for driving start -> finish."""
    data = _request(
        'directions',
        'POST',
        '/v2/directions/driving-car/geojson',
        json={
            'coordinates': [[start[1], start[0]], [finish[1], finish[0]]],
            'units': 'mi',
            'extra_info': ['countryinfo'],  # which country each stretch of road is in
        },
    )
    feature = data['features'][0]
    # Each entry is [first point, last point, country]. A route may cross Canada on the way
    # (Detroit -> Buffalo), but both ends must be in the USA.
    countries = feature['properties']['extras']['countryinfo']['values']
    if {countries[0][2], countries[-1][2]} != {ORS_USA_COUNTRY_ID}:
        raise InvalidLocation('The start and finish must both be in the USA.')
    road = [(lat, lon) for lon, lat in feature['geometry']['coordinates']]
    return road, feature['properties']['summary']['distance']


def geocode(text):
    """Return (lat, lon) of the best US match for a free-text address."""
    data = _request(
        'geocode',
        'GET',
        '/geocode/search',
        params={'text': text, 'boundary.country': 'US', 'size': 1},
    )
    if not data['features']:
        raise InvalidLocation(f'Could not find a US location matching "{text}".')
    lon, lat = data['features'][0]['geometry']['coordinates']
    return lat, lon


def _request(endpoint, method, path, **kwargs):
    _reserve_quota(endpoint)
    try:
        response = requests.request(
            method,
            f'{ORS_BASE_URL}{path}',
            headers={'Authorization': settings.ORS_API_KEY},
            timeout=ORS_TIMEOUT_SECONDS,
            **kwargs,
        )
    except requests.RequestException as exc:
        raise RoutingServiceError(f'Routing service unreachable: {exc}') from exc

    if response.status_code == 429:
        raise QuotaExceeded(retry_after=int(response.headers.get('Retry-After', MINUTE)))
    # A rejected key is our misconfiguration, not the caller's fault.
    if response.status_code in (401, 403) or response.status_code >= 500:
        raise RoutingServiceError(
            f'Routing service error ({response.status_code}): {_error_message(response)}'
        )
    if not response.ok:
        raise RouteNotFound(_error_message(response))
    return response.json()


def _reserve_quota(endpoint):
    """Count this call against every ORS window; refuse before calling if any is used up."""
    now = time.time()
    for limit, window in ORS_QUOTAS[endpoint]:
        key = f'ors-quota:{endpoint}:{window}:{int(now // window)}'
        cache.add(key, 0, timeout=window)
        if cache.incr(key) > limit:
            raise QuotaExceeded(retry_after=int(window - now % window) + 1)


def _error_message(response):
    try:
        error = response.json()['error']
    except (ValueError, KeyError, TypeError):
        return response.text[:200]
    return error.get('message', error) if isinstance(error, dict) else error
