from django.test import SimpleTestCase

from fuel.services.addresses import parse_address, place_key
from fuel.services.osm import index_exits, index_towns, locate_exit

TOPEKA = (39.04, -95.69)
ELEMENTS = [
    {
        'type': 'node',
        'id': 1,
        'lat': 39.05,
        'lon': -95.70,
        'tags': {'highway': 'motorway_junction', 'ref': '126B'},
    },
    {
        'type': 'node',
        'id': 2,
        'lat': 39.06,
        'lon': -95.60,
        'tags': {'highway': 'motorway_junction', 'ref': '126'},
    },
    {
        'type': 'node',
        'id': 3,
        'lat': 39.10,
        'lon': -95.65,
        'tags': {'highway': 'motorway_junction', 'ref': '9'},
    },
    {
        'type': 'way',
        'id': 10,
        'nodes': [1, 3],
        'tags': {'highway': 'motorway', 'ref': 'I 70;US 40'},
    },
    {'type': 'way', 'id': 11, 'nodes': [2], 'tags': {'highway': 'motorway', 'ref': 'I 470'}},
    {
        'type': 'node',
        'id': 20,
        'lat': 39.04,
        'lon': -95.69,
        'tags': {'place': 'city', 'name': 'Topeka'},
    },
    {
        'type': 'node',
        'id': 21,
        'lat': 38.00,
        'lon': -97.00,
        'tags': {'place': 'hamlet', 'name': 'Topeka'},
    },
    {
        'type': 'node',
        'id': 22,
        'lat': 36.30,
        'lon': -95.31,
        'tags': {'place': 'town', 'name': 'Pryor Creek', 'short_name': 'Pryor'},
    },
    {
        'type': 'node',
        'id': 24,
        'lat': 39.95,
        'lon': -75.05,
        'tags': {'place': 'town', 'name': 'Pennsauken Township'},
    },
    {
        'type': 'node',
        'id': 25,
        'lat': 38.44,
        'lon': -105.23,
        'tags': {'place': 'city', 'name': 'Cañon City'},
    },
    {  # tagged as both a village and an exit, but with no exit number
        'type': 'node',
        'id': 23,
        'lat': 39.20,
        'lon': -95.50,
        'tags': {'place': 'village', 'name': 'Junction', 'highway': 'motorway_junction'},
    },
]


class IndexTests(SimpleTestCase):
    def test_town_names_include_short_names_and_prefer_cities(self):
        towns = index_towns(ELEMENTS)

        self.assertEqual(towns['TOPEKA'], TOPEKA)
        self.assertEqual(towns['PRYOR'], towns['PRYORCREEK'])

    def test_township_suffix_and_accents_are_ignored(self):
        towns = index_towns(ELEMENTS)

        self.assertEqual(towns[place_key('Pennsauken')], (39.95, -75.05))
        self.assertEqual(towns[place_key('Canon City')], (38.44, -105.23))

    def test_exits_are_grouped_by_number_with_their_highways(self):
        exits = index_exits(ELEMENTS)

        self.assertEqual(len(exits['126']), 2)
        self.assertIn(parse_address('I-70').roads[0], exits['126'][0][2])


class LocateExitTests(SimpleTestCase):
    exits = index_exits(ELEMENTS)

    def test_picks_the_exit_on_the_named_highway(self):
        # Exit 126 also exists on I-470, but the address names I-70.
        located = locate_exit(parse_address('I-70, EXIT 126'), TOPEKA, self.exits)

        self.assertEqual(located, (39.05, -95.70))

    def test_missing_interstate_exit_is_treated_as_a_data_error(self):
        self.assertIsNone(locate_exit(parse_address('I-35, EXIT 126'), TOPEKA, self.exits))

    def test_exit_too_far_from_the_town_is_rejected(self):
        far_town = (36.0, -90.0)

        self.assertIsNone(locate_exit(parse_address('I-70, EXIT 126'), far_town, self.exits))

    def test_turnpike_exit_matches_on_number_alone_when_close(self):
        located = locate_exit(parse_address('KS TURNPIKE, EXIT 9'), TOPEKA, self.exits)

        self.assertEqual(located, (39.10, -95.65))

    def test_unknown_town_uses_the_exit_when_the_highway_has_only_one(self):
        located = locate_exit(parse_address('I-70, EXIT 9'), None, self.exits)

        self.assertEqual(located, (39.10, -95.65))

    def test_unknown_town_and_two_far_apart_exits_is_ambiguous(self):
        exits = {
            '126': [(39.0, -95.0, self.exits['126'][0][2]), (39.0, -97.0, self.exits['126'][0][2])]
        }

        self.assertIsNone(locate_exit(parse_address('I-70, EXIT 126'), None, exits))

    def test_address_without_exit(self):
        self.assertIsNone(locate_exit(parse_address('US-281 & SR-29'), TOPEKA, self.exits))
