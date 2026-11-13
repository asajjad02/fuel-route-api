import csv
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand

from fuel.constants import PLACES_CSV, STATION_LOCATIONS_CSV, STATIONS_CSV_PATH, US_STATES
from fuel.services.addresses import parse_address, place_key
from fuel.services.osm import fetch_state, index_exits, index_towns, locate_exit


class Command(BaseCommand):
    help = (
        'Place every station at the highway exit its address names, or else at its town centre, '
        'using OpenStreetMap. Writes fuel/data/station_locations.csv and fuel/data/places.csv.'
    )

    def handle(self, *args, **options):
        stations_by_state = defaultdict(dict)
        with STATIONS_CSV_PATH.open(encoding='utf-8') as f:
            for row in csv.DictReader(f):
                if row['State'] in US_STATES:
                    stations_by_state[row['State']].setdefault(row['OPIS Truckstop ID'], row)

        locations, places, counts = [], [], Counter()
        for state, stations in sorted(stations_by_state.items()):
            elements = fetch_state(state)
            towns, exits = index_towns(elements), index_exits(elements)
            places += [
                (state, key, round(lat, 6), round(lon, 6)) for key, (lat, lon) in towns.items()
            ]

            for opis_id, row in stations.items():
                town = towns.get(place_key(row['City']))
                exit_coords = locate_exit(parse_address(row['Address']), town, exits)
                if not (exit_coords or town):
                    counts['skipped'] += 1
                    self.stderr.write(f'Not placed {opis_id}: {row["Address"]}, {row["City"]}')
                    continue
                lat, lon = exit_coords or town
                source = 'exit' if exit_coords else 'town'
                locations.append((opis_id, round(lat, 6), round(lon, 6), source))
                counts[source] += 1
            self.stdout.write(f'{state}: {len(stations)} stations')

        _write(STATION_LOCATIONS_CSV, ('opis_id', 'latitude', 'longitude', 'source'), locations)
        _write(PLACES_CSV, ('state', 'key', 'latitude', 'longitude'), places)
        self.stdout.write(
            self.style.SUCCESS(
                f'{counts["exit"]} stations at highway exits, {counts["town"]} at town centres, '
                f'{counts["skipped"]} skipped. {len(places)} places.'
            )
        )


def _write(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
