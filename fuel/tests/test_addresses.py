from django.test import SimpleTestCase

from fuel.services.addresses import Address, Road, parse_address, parse_roads

I44, US69 = Road('I', '44'), Road('US', '69')


class ParseAddressTests(SimpleTestCase):
    def test_exit_on_an_interstate(self):
        self.assertEqual(
            parse_address('I-44, EXIT 283 & US-69'),
            Address(roads=(I44, US69), exit_number='283', exit_road=I44),
        )

    def test_exit_belongs_to_the_interstate_even_when_named_first(self):
        address = parse_address('I-45 & FM 1603, EXIT 238')

        self.assertEqual(address.exit_road, Road('I', '45'))

    def test_mixed_case_and_no_comma(self):
        self.assertEqual(parse_address('I-40 Exit 398').exit_number, '398')

    def test_exit_with_no_recognisable_road(self):
        address = parse_address('NJTP, EXIT 7')

        self.assertEqual((address.exit_number, address.exit_road), ('7', None))

    def test_crossing_roads(self):
        self.assertEqual(
            parse_address('US-281 & SR-29'),
            Address(roads=(Road('US', '281'), Road('STATE', '29'))),
        )

    def test_slash_shorthand_shares_the_prefix(self):
        self.assertEqual(parse_roads('SR-22/39'), (Road('STATE', '22'), Road('STATE', '39')))

    def test_business_route_keeps_its_number(self):
        self.assertEqual(parse_roads('US-60BUS'), (Road('US', '60'),))

    def test_mile_markers_and_street_addresses_are_not_roads(self):
        self.assertEqual(parse_roads('NJTP MM 5 SB'), ())
        self.assertEqual(parse_roads('504 N CREGO RD'), ())


class RoadMatchTests(SimpleTestCase):
    def test_reads_openstreetmap_refs(self):
        self.assertEqual(
            parse_roads('I 44;US 69;OK 66;FM 1472'),
            (I44, US69, Road('STATE', '66'), Road('FARM', '1472')),
        )

    def test_same_number_different_family_does_not_match(self):
        self.assertFalse(Road('I', '44').matches(Road('US', '44')))

    def test_unknown_family_matches_on_number(self):
        self.assertTrue(Road('ANY', '71').matches(Road('US', '71')))
