import random
from types import SimpleNamespace

from django.test import SimpleTestCase

from fuel.errors import NoStationInRange
from fuel.services.planner import plan_fuel_stops


def station(mile, price):
    return SimpleNamespace(mile=mile, price=price)


def purchases(plan):
    return [(stop.at.mile, round(stop.gallons, 6)) for stop in plan.stops]


class PlanFuelStopsTests(SimpleTestCase):
    def test_readme_example_does_not_fill_up_at_a_local_low(self):
        # B is cheaper than A, but C (in reach of B) is cheaper still: filling up at B would
        # cost $234; buying just enough to reach C costs $224.
        stations = [station(0, 3.20), station(100, 3.00), station(350, 2.60)]

        plan = plan_fuel_stops(stations, total_miles=800)

        self.assertEqual(purchases(plan), [(0, 10), (100, 25), (350, 45)])
        self.assertAlmostEqual(plan.total_cost, 224.0)

    def test_buys_just_enough_to_reach_cheaper_station(self):
        plan = plan_fuel_stops([station(0, 3.0), station(100, 2.0)], total_miles=300)

        self.assertEqual(purchases(plan), [(0, 10), (100, 20)])
        self.assertAlmostEqual(plan.total_cost, 10 * 3.0 + 20 * 2.0)

    def test_fills_up_when_nothing_cheaper_in_range(self):
        plan = plan_fuel_stops([station(0, 2.0), station(400, 3.0)], total_miles=800)

        # Full 500-mile tank at the cheap station, then only the remaining 300 miles at $3.
        self.assertEqual(purchases(plan), [(0, 50), (400, 30)])
        self.assertAlmostEqual(plan.total_cost, 50 * 2.0 + 30 * 3.0)

    def test_skips_pricier_station_when_cheaper_one_is_reachable(self):
        stations = [station(0, 3.0), station(100, 4.0), station(200, 2.0)]

        plan = plan_fuel_stops(stations, total_miles=400)

        self.assertEqual(purchases(plan), [(0, 20), (200, 20)])

    def test_marginally_cheaper_station_is_not_worth_a_stop(self):
        stations = [station(0, 3.00), station(100, 2.99)]

        default = plan_fuel_stops(stations, total_miles=300)
        strict = plan_fuel_stops(stations, total_miles=300, min_saving=0)

        self.assertEqual(purchases(default), [(0, 30)])
        self.assertEqual(purchases(strict), [(0, 10), (100, 20)])
        self.assertLess(strict.total_cost, default.total_cost)

    def test_fill_up_drives_to_farthest_station_within_saving_of_best_price(self):
        stations = [station(0, 3.00), station(100, 3.20), station(300, 3.22), station(600, 3.0)]

        default = plan_fuel_stops(stations, total_miles=900)
        strict = plan_fuel_stops(stations, total_miles=900, min_saving=0)

        self.assertEqual([s.at.mile for s in default.stops], [0, 300, 600])
        self.assertEqual([s.at.mile for s in strict.stops], [0, 100, 600])

    def test_drive_to_first_station_is_billed_at_its_price(self):
        plan = plan_fuel_stops([station(50, 3.0)], total_miles=100)

        self.assertEqual(plan.initial_gallons, 5)
        self.assertEqual(purchases(plan), [(50, 5)])
        self.assertAlmostEqual(plan.total_cost, 10 * 3.0)

    def test_gap_longer_than_range_raises(self):
        with self.assertRaises(NoStationInRange) as ctx:
            plan_fuel_stops([station(0, 3.0), station(600, 3.0)], total_miles=700)
        self.assertEqual(ctx.exception.mile, 0)

    def test_first_station_out_of_range_raises(self):
        with self.assertRaises(NoStationInRange):
            plan_fuel_stops([station(501, 3.0)], total_miles=600)

    def test_no_stations_raises(self):
        with self.assertRaises(NoStationInRange):
            plan_fuel_stops([], total_miles=10)

    def test_buys_exactly_the_fuel_the_route_needs(self):
        rng = random.Random(42)
        miles = sorted(rng.uniform(0, 3000) for _ in range(300))
        stations = [station(mile, rng.uniform(2.5, 4.5)) for mile in miles]

        plan = plan_fuel_stops(stations, total_miles=3000)

        self.assertAlmostEqual(plan.total_gallons, 3000 / 10)
        self.assertTrue(all(stop.gallons <= 50 for stop in plan.stops))
