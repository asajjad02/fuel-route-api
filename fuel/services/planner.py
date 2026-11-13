"""Cheapest refuelling plan along a fixed route (greedy "gas station problem").

At each stop: if a station cheaper by more than `min_saving` is within range, buy just enough to
reach the nearest one; otherwise fill the tank and drive to the cheapest station within range.
With min_saving=0 this is optimal for a fixed route with linear fuel prices; a positive value
trades a few cents for far fewer stops. Runs in O(n * k), n stations and k stations per tank.
"""

from bisect import bisect_right
from dataclasses import dataclass
from math import inf
from types import SimpleNamespace

from fuel.constants import MAX_RANGE_MILES, MILES_PER_GALLON, MIN_PRICE_SAVING
from fuel.errors import NoStationInRange


@dataclass(frozen=True)
class FuelStop:
    at: object  # a RouteStation (anything with .mile and .price)
    gallons: float

    @property
    def cost(self):
        return self.gallons * self.at.price


@dataclass(frozen=True)
class FuelPlan:
    stops: list
    # The tank starts empty, so the drive to the first station is billed at that station's price.
    initial_gallons: float
    initial_cost: float
    total_gallons: float
    total_cost: float

    @property
    def stop_count(self):
        return len(self.stops)


def plan_fuel_stops(
    stations,
    total_miles,
    max_range=MAX_RANGE_MILES,
    mpg=MILES_PER_GALLON,
    min_saving=MIN_PRICE_SAVING,
):
    """Plan stops along `stations` (sorted by .mile) to cover `total_miles` at least cost."""
    if not stations or stations[0].mile > max_range:
        raise NoStationInRange(0)

    # The destination acts as a free "station" so the plan never buys fuel it won't use.
    nodes = [*stations, SimpleNamespace(mile=total_miles, price=-inf)]
    miles = [node.mile for node in nodes]
    stops = []
    i, tank = 0, 0.0  # tank is measured in miles of range left on arrival

    while i < len(nodes) - 1:
        here = nodes[i]
        reachable = range(i + 1, bisect_right(miles, here.mile + max_range))
        if not reachable:
            raise NoStationInRange(here.mile)

        target = next((k for k in reachable if nodes[k].price < here.price - min_saving), None)
        if target is not None:
            fill_to = nodes[target].mile - here.mile
        else:
            # Stations within min_saving of the best price count as equal; prefer the farthest.
            best = min(nodes[k].price for k in reachable)
            target = max(k for k in reachable if nodes[k].price <= best + min_saving)
            fill_to = max_range

        if fill_to > tank:
            stops.append(FuelStop(here, (fill_to - tank) / mpg))
        tank = max(tank, fill_to) - (nodes[target].mile - here.mile)
        i = target

    initial_gallons = stations[0].mile / mpg
    initial_cost = initial_gallons * stations[0].price
    return FuelPlan(
        stops=stops,
        initial_gallons=initial_gallons,
        initial_cost=initial_cost,
        total_gallons=initial_gallons + sum(s.gallons for s in stops),
        total_cost=initial_cost + sum(s.cost for s in stops),
    )
