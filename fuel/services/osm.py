"""OpenStreetMap highway exits and towns, used only to build the committed location files."""

import json
import re
import time

import numpy as np
import requests

from fuel.constants import (
    EXIT_MAX_MILES,
    EXIT_NUMBER_ONLY_MAX_MILES,
    EXIT_SPREAD_MILES,
    OSM_CACHE_DIR,
    OVERPASS_ATTEMPTS,
    OVERPASS_QUERY,
    OVERPASS_RETRY_SECONDS,
    OVERPASS_TIMEOUT_SECONDS,
    OVERPASS_URL,
    PLACE_NAME_TAGS,
    PLACE_RANKS,
    PLACE_SUFFIX_RE,
)
from fuel.services.addresses import parse_roads, place_key
from fuel.services.geo import haversine_miles


def fetch_state(state):
    """Highways, their exits and the towns of one state, downloaded once and kept on disk."""
    path = OSM_CACHE_DIR / f'{state}.json'
    if not path.exists():
        OSM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_download(state))
    return json.loads(path.read_bytes())['elements']


def _download(state):
    query = OVERPASS_QUERY.format(
        timeout=OVERPASS_TIMEOUT_SECONDS, state=state, place_types='|'.join(PLACE_RANKS)
    )
    for attempt in range(1, OVERPASS_ATTEMPTS + 1):
        response = requests.post(
            OVERPASS_URL,
            data={'data': query},
            timeout=OVERPASS_TIMEOUT_SECONDS + 30,
            headers={'User-Agent': 'spotter-fuel-route/1.0'},
        )
        # A busy server answers 429/5xx, or 200 with an error page instead of JSON.
        if response.ok and response.content.lstrip().startswith(b'{'):
            return response.content
        if attempt < OVERPASS_ATTEMPTS:
            time.sleep(OVERPASS_RETRY_SECONDS * attempt)
    response.raise_for_status()
    raise ValueError(f'Overpass sent no data for {state}: {response.text[:200]}')


def index_towns(elements):
    """Map place_key(town name) -> (lat, lon); a city beats a town, a town beats a village."""
    places = [e for e in elements if e['type'] == 'node' and e['tags'].get('place') in PLACE_RANKS]
    places.sort(key=lambda e: PLACE_RANKS.index(e['tags']['place']))
    names = [
        (name.strip(), (place['lat'], place['lon']))
        for place in places
        for tag in PLACE_NAME_TAGS
        for name in place['tags'].get(tag, '').split(';')
        if name.strip()
    ]
    towns = {}
    for name, coords in names:
        towns.setdefault(place_key(name), coords)
    # Second pass, so real names win: "Pennsauken Township" also answers to "Pennsauken".
    for name, coords in names:
        if suffix := PLACE_SUFFIX_RE.search(name):
            towns.setdefault(place_key(name[: suffix.start()]), coords)
    return towns


def index_exits(elements):
    """Map exit number ("36" for "36A") -> [(lat, lon, roads the exit sits on), ...]."""
    exit_nodes = {
        e['id']: e
        for e in elements
        if e['type'] == 'node'
        and e['tags'].get('highway') == 'motorway_junction'
        and 'ref' in e['tags']  # the town query can return unnumbered exits too
    }
    roads = {node_id: set() for node_id in exit_nodes}
    for way in (e for e in elements if e['type'] == 'way'):
        for node_id in way['nodes']:
            if node_id in roads:
                roads[node_id].update(parse_roads(way['tags']['ref']))
    exits = {}
    for node_id, node in exit_nodes.items():
        if number := re.match(r'\d+', node['tags']['ref']):
            exits.setdefault(number[0].lstrip('0') or '0', []).append(
                (node['lat'], node['lon'], roads[node_id])
            )
    return exits


def locate_exit(address, town, exits):
    """(lat, lon) of the exit named in `address`, or None. `town` is (lat, lon) or None."""
    candidates = exits.get(address.exit_number, [])
    on_road = [
        (lat, lon)
        for lat, lon, roads in candidates
        if address.exit_road and any(address.exit_road.matches(road) for road in roads)
    ]
    if town is None:
        # No town to compare against: trust the exit only if the highway has just one with
        # that number (both carriageways of one exit sit close together).
        return on_road[0] if on_road and _spread_miles(on_road) <= EXIT_SPREAD_MILES else None
    if on_road:
        return _nearest(town, on_road, EXIT_MAX_MILES)
    if address.exit_road and address.exit_road.kind == 'I':
        return None  # an interstate exit missing from that interstate is a data error
    # Turnpikes and US routes are often tagged differently: trust the number only nearby.
    return _nearest(town, [(lat, lon) for lat, lon, _ in candidates], EXIT_NUMBER_ONLY_MAX_MILES)


def _spread_miles(points):
    lat, lon = np.array(points).T
    return haversine_miles(lat[0], lon[0], lat, lon).max()


def _nearest(town, points, max_miles):
    if not points:
        return None
    lat, lon = np.array(points).T
    distances = haversine_miles(town[0], town[1], lat, lon)
    best = distances.argmin()
    return (float(lat[best]), float(lon[best])) if distances[best] <= max_miles else None
