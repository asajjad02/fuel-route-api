"""Turn a start or finish string into (lat, lon)."""

import hashlib

from django.core.cache import cache

from fuel.constants import CITY_STATE_RE, GEOCODE_CACHE_TTL, LAT_LNG_RE, US_LAT_RANGE, US_LON_RANGE
from fuel.errors import InvalidLocation
from fuel.models import Place
from fuel.services import ors
from fuel.services.addresses import place_key


def resolve_location(text):
    """Accepts "lat,lng", "City, ST" or a street address. Only an address needs an API call."""
    if match := LAT_LNG_RE.match(text):
        lat, lon = float(match[1]), float(match[2])
        in_usa = (
            US_LAT_RANGE[0] <= lat <= US_LAT_RANGE[1] and US_LON_RANGE[0] <= lon <= US_LON_RANGE[1]
        )
        if not in_usa:
            raise InvalidLocation(f'Coordinates {lat},{lon} are outside the USA.')
        return lat, lon

    if match := CITY_STATE_RE.match(text):
        place = Place.objects.filter(state=match[2].upper(), key=place_key(match[1])).first()
        if place:
            return place.latitude, place.longitude

    # md5 only turns arbitrary text into a short, cache-safe key.
    key = 'geocode:' + hashlib.md5(' '.join(text.lower().split()).encode()).hexdigest()
    return cache.get_or_set(key, lambda: ors.geocode(text), GEOCODE_CACHE_TTL)
