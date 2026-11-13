from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from fuel.errors import InvalidLocation, QuotaExceeded, RouteNotFound, RoutingServiceError
from fuel.models import Place
from fuel.services import ors
from fuel.services.locations import resolve_location


def ors_response(status_code, body=None, headers=None):
    return mock.Mock(
        status_code=status_code,
        ok=status_code < 400,
        headers=headers or {},
        json=mock.Mock(return_value=body or {}),
        text='',
    )


class ResolveLocationTests(TestCase):
    def test_parses_lat_lng(self):
        self.assertEqual(resolve_location(' 40.7, -74.0 '), (40.7, -74.0))

    def test_rejects_coordinates_outside_usa(self):
        with self.assertRaises(InvalidLocation):
            resolve_location('48.85,2.35')

    def test_city_and_state_resolve_without_an_api_call(self):
        Place.objects.create(state='MO', key='SAINTLOUIS', latitude=38.63, longitude=-90.2)

        with mock.patch.object(ors, 'geocode') as geocode:
            self.assertEqual(resolve_location('St. Louis, mo'), (38.63, -90.2))
        geocode.assert_not_called()


def route_response(*countries):
    """An ORS directions reply whose road passes through `countries` in order (214 = USA)."""
    return ors_response(
        200,
        {
            'features': [
                {
                    'geometry': {'coordinates': [[-83.0, 42.3], [-83.1, 42.4]]},
                    'properties': {
                        'summary': {'distance': 10.0},
                        'extras': {
                            'countryinfo': {
                                'values': [[i, i + 1, c] for i, c in enumerate(countries)]
                            }
                        },
                    },
                }
            ]
        },
    )


class GetRouteTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def route(self, *countries):
        with mock.patch.object(ors.requests, 'request', return_value=route_response(*countries)):
            return ors.get_route((42.3, -83.0), (42.4, -83.1))

    def test_route_inside_the_usa(self):
        self.assertEqual(self.route(214), ([(42.3, -83.0), (42.4, -83.1)], 10.0))

    def test_route_may_cross_canada_between_two_us_points(self):
        self.assertEqual(self.route(214, 35, 214)[1], 10.0)  # Detroit -> Buffalo

    def test_start_or_finish_outside_the_usa_is_rejected(self):
        for countries in ((35, 214), (214, 35)):  # Windsor -> Detroit, Detroit -> Windsor
            with self.subTest(countries=countries), self.assertRaises(InvalidLocation):
                self.route(*countries)


class OrsRequestTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def call(self, response):
        with mock.patch.object(ors.requests, 'request', return_value=response):
            return ors._request('directions', 'GET', '/x')

    def test_maps_http_errors_to_domain_errors(self):
        cases = [
            (ors_response(429, headers={'Retry-After': '7'}), QuotaExceeded),
            (ors_response(403), RoutingServiceError),
            (ors_response(500), RoutingServiceError),
            (ors_response(404, {'error': {'message': 'No route'}}), RouteNotFound),
        ]
        for response, error in cases:
            with self.subTest(status=response.status_code), self.assertRaises(error):
                self.call(response)

    def test_quota_guard_fails_fast_without_calling_ors(self):
        with (
            mock.patch.dict(ors.ORS_QUOTAS, {'directions': ((2, 60),)}),
            mock.patch.object(ors.requests, 'request', return_value=ors_response(200)) as request,
        ):
            ors._request('directions', 'GET', '/x')
            ors._request('directions', 'GET', '/x')
            with self.assertRaises(QuotaExceeded):
                ors._request('directions', 'GET', '/x')

        self.assertEqual(request.call_count, 2)
