from django.test import SimpleTestCase, TestCase

from fuel.models import FuelStation
from fuel.services.geo import haversine_miles, stations_along_route

EXIT = FuelStation.LocationSource.EXIT


def make_station(opis_id, lat, lon, price='3.000', source=FuelStation.LocationSource.TOWN):
    return FuelStation.objects.create(
        opis_id=opis_id,
        name=f'Station {opis_id}',
        address='I-35, EXIT 1',
        city='Town',
        state='TX',
        retail_price=price,
        latitude=lat,
        longitude=lon,
        location_source=source,
    )


class HaversineTests(SimpleTestCase):
    def test_one_degree_of_latitude(self):
        self.assertAlmostEqual(haversine_miles(30, -97, 31, -97), 69.1, delta=0.1)


class StationsAlongRouteTests(TestCase):
    # A straight route due north along longitude -97, about 69 miles long.
    geometry = [(30.0 + i / 100, -97.0) for i in range(101)]

    def test_keeps_nearby_stations_in_route_order(self):
        make_station(1, 30.8, -97.01)
        make_station(2, 30.2, -97.0)

        result = stations_along_route(self.geometry, route_miles=69.1)

        self.assertEqual([rs.station.opis_id for rs in result], [2, 1])
        self.assertAlmostEqual(result[0].mile, 0.2 * 69.1, delta=1)
        self.assertAlmostEqual(result[1].offset_miles, 0.6, delta=0.1)

    def test_drops_stations_outside_corridor(self):
        make_station(1, 30.5, -96.0)  # ~60 miles east of the route

        self.assertEqual(stations_along_route(self.geometry, route_miles=69.1), [])

    def test_exit_stations_get_a_tighter_corridor_than_town_centres(self):
        # Both ~3 miles off the route: fine for a rough town centre, too far for an exact exit.
        make_station(1, 30.5, -96.95)
        make_station(2, 30.6, -96.95, source=EXIT)

        result = stations_along_route(self.geometry, route_miles=69.1)

        self.assertEqual([rs.station.opis_id for rs in result], [1])

    def test_sparse_route_points_are_filled_in(self):
        # The router gave only two points 69 miles apart; an exit halfway must still match.
        make_station(1, 30.5, -97.0, source=EXIT)

        result = stations_along_route([(30.0, -97.0), (31.0, -97.0)], route_miles=69.1)

        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0].mile, 34.5, delta=1)
        self.assertLess(result[0].offset_miles, 0.6)
