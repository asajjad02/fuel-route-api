from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from fuel.errors import QuotaExceeded
from fuel.services.geo import haversine_miles
from fuel.tests.test_geo import make_station

# A straight route due north along longitude -97, ~345 miles, with a station every ~35 miles.
GEOMETRY = [(30.0 + i / 100, -97.0) for i in range(501)]
ROUTE_MILES = float(haversine_miles(30, -97, 35, -97))
START, FINISH = '30,-97', '35,-97'


class RouteApiTests(TestCase):
    def setUp(self):
        cache.clear()
        for i in range(10):
            make_station(i + 1, 30.0 + i / 2, -97.0, price=f'{3 + i / 10:.3f}')
        self.client = APIClient()
        patcher = mock.patch('fuel.services.trip.get_route', return_value=(GEOMETRY, ROUTE_MILES))
        self.get_route = patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, **body):
        return self.client.post(reverse('route'), body, format='json')

    def test_returns_plan_covering_the_whole_route(self):
        response = self.post(start=START, finish=FINISH)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertAlmostEqual(data['total_gallons'], ROUTE_MILES / 10, places=1)
        # Prices rise northward, so one fill-up at the cheapest (first) station covers the trip.
        self.assertEqual([s['station']['opis_id'] for s in data['fuel_stops']], [1])
        self.assertEqual(data['fuel_stop_count'], 1)
        self.assertEqual(data['map']['type'], 'FeatureCollection')
        self.assertIn('/api/route/map/?start=30%2C-97', data['map_url'])

    def test_repeat_request_is_served_from_cache(self):
        self.post(start=START, finish=FINISH)
        self.post(start=' 30.0000, -97.0000 ', finish=FINISH)

        self.get_route.assert_called_once()

    def test_missing_finish_is_rejected(self):
        response = self.post(start=START)

        self.assertEqual(response.status_code, 400)
        self.assertIn('finish', response.json())

    def test_location_outside_usa_is_rejected(self):
        response = self.post(start='48.85,2.35', finish=FINISH)

        self.assertEqual(response.status_code, 400)
        self.assertIn('outside the USA', response.json()['detail'])

    def test_same_start_and_finish_is_rejected(self):
        self.assertEqual(self.post(start=START, finish=START).status_code, 400)

    def test_route_without_stations_returns_422(self):
        self.get_route.return_value = ([(40.0, -110.0), (41.0, -110.0)], 69.0)

        response = self.post(start='40,-110', finish='41,-110')

        self.assertEqual(response.status_code, 422)

    def test_quota_exceeded_returns_503_with_retry_after(self):
        self.get_route.side_effect = QuotaExceeded(retry_after=42)

        response = self.post(start=START, finish=FINISH)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response['Retry-After'], '42')

    def test_map_page_renders(self):
        response = self.client.get(reverse('route-map'), {'start': START, 'finish': FINISH})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'leaflet')
        self.assertContains(response, 'Station 1')
