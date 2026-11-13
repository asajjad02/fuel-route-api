"""Orchestrates a trip: resolve locations, route once, match stations, plan fuel stops."""

from dataclasses import dataclass

from django.core.cache import cache

from fuel.constants import COORD_PRECISION, MAP_MAX_POINTS, TRIP_CACHE_TTL
from fuel.errors import InvalidLocation
from fuel.services.geo import stations_along_route
from fuel.services.locations import resolve_location
from fuel.services.ors import get_route
from fuel.services.planner import FuelPlan, plan_fuel_stops


@dataclass(frozen=True)
class Trip:
    start: tuple
    finish: tuple
    distance_miles: float
    geometry: list  # (lat, lon) points, thinned for display
    plan: FuelPlan


def plan_trip(start, finish):
    """Return the Trip between two location strings, cached by their rounded coordinates."""
    # Rounding (~100 m) lets equivalent inputs ("Dallas, TX" vs its coordinates) share a cache hit.
    start, finish = (
        tuple(round(c, COORD_PRECISION) for c in resolve_location(text))
        for text in (start, finish)
    )
    if start == finish:
        raise InvalidLocation('Start and finish are the same place.')
    # shortcut: cached trips keep their prices until TRIP_CACHE_TTL even if stations are reloaded;
    # clear the cache in load_stations if prices change more often than that.
    key = f'trip:{start[0]},{start[1]}:{finish[0]},{finish[1]}'
    return cache.get_or_set(key, lambda: _build_trip(start, finish), TRIP_CACHE_TTL)


def _build_trip(start, finish):
    geometry, miles = get_route(start, finish)
    plan = plan_fuel_stops(stations_along_route(geometry, miles), miles)
    step = max(1, len(geometry) // MAP_MAX_POINTS)
    return Trip(start, finish, miles, [*geometry[::step], geometry[-1]], plan)
