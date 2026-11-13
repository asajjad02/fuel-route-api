import tempfile
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from fuel.models import FuelStation, Place

PRICES = """OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price
7,PILOT #1,"I-70, EXIT 126",Topeka,KS,1,3.2
7,PILOT #1 DUP,"I-70, EXIT 126",Topeka,KS,1,3.1
8,LOVES #2,US-281 & SR-29,Topeka,KS,1,3.3
9,PETRO CANADA,HWY 1,Calgary,AB,1,1.5
"""
LOCATIONS = """opis_id,latitude,longitude,source
7,39.05,-95.7,exit
8,39.04,-95.69,town
"""
PLACES = """state,key,latitude,longitude
KS,TOPEKA,39.04,-95.69
"""


class LoadStationsTests(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.paths = {}
        for name, text in {'prices': PRICES, 'locations': LOCATIONS, 'places': PLACES}.items():
            self.paths[name] = Path(directory.name) / f'{name}.csv'
            self.paths[name].write_text(text, encoding='utf-8')

    def test_loads_cheapest_listing_at_its_committed_location(self):
        with (
            mock.patch(
                'fuel.management.commands.load_stations.STATION_LOCATIONS_CSV',
                self.paths['locations'],
            ),
            mock.patch('fuel.management.commands.load_stations.PLACES_CSV', self.paths['places']),
        ):
            call_command('load_stations', self.paths['prices'], stdout=mock.Mock())

        stations = {s.opis_id: s for s in FuelStation.objects.all()}
        self.assertEqual(set(stations), {7, 8})  # the Canadian row has no location
        self.assertEqual(stations[7].retail_price, Decimal('3.100'))
        self.assertEqual(
            (stations[7].latitude, stations[7].longitude, stations[7].location_source),
            (39.05, -95.7, FuelStation.LocationSource.EXIT),
        )
        self.assertEqual(stations[8].location_source, FuelStation.LocationSource.TOWN)
        self.assertTrue(Place.objects.filter(state='KS', key='TOPEKA').exists())
