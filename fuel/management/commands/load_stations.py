import csv
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from fuel.constants import PLACES_CSV, STATION_LOCATIONS_CSV, STATIONS_CSV_PATH
from fuel.models import FuelStation, Place


class Command(BaseCommand):
    help = 'Load fuel prices and the committed station locations and towns into the database.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', nargs='?', type=Path, default=STATIONS_CSV_PATH)

    def handle(self, *args, csv_path, **options):
        locations = _read(STATION_LOCATIONS_CSV)
        locations = {row['opis_id']: row for row in locations}
        stations = {}
        skipped = 0

        with csv_path.open(encoding='utf-8') as f:
            for row in csv.DictReader(f):
                # Canadian rows and the few US towns OpenStreetMap doesn't know have no location.
                location = locations.get(row['OPIS Truckstop ID'])
                if location is None:
                    skipped += 1
                    continue
                opis_id = int(row['OPIS Truckstop ID'])
                price = Decimal(row['Retail Price']).quantize(Decimal('0.001'))
                # The CSV repeats some stations; keep the cheapest listing.
                if opis_id in stations and stations[opis_id].retail_price <= price:
                    continue
                stations[opis_id] = FuelStation(
                    opis_id=opis_id,
                    name=row['Truckstop Name'].strip(),
                    address=row['Address'].strip(),
                    city=row['City'].strip(),
                    state=row['State'],
                    retail_price=price,
                    latitude=float(location['latitude']),
                    longitude=float(location['longitude']),
                    location_source=location['source'],
                )

        places = [
            Place(
                state=row['state'],
                key=row['key'],
                latitude=float(row['latitude']),
                longitude=float(row['longitude']),
            )
            for row in _read(PLACES_CSV)
        ]

        with transaction.atomic():
            FuelStation.objects.all().delete()
            FuelStation.objects.bulk_create(stations.values(), batch_size=1000)
            Place.objects.all().delete()
            Place.objects.bulk_create(places, batch_size=2000)

        at_exits = sum(
            s.location_source == FuelStation.LocationSource.EXIT for s in stations.values()
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Loaded {len(stations)} stations ({at_exits} at highway exits, '
                f'{len(stations) - at_exits} at town centres; {skipped} rows skipped) '
                f'and {len(places)} places.'
            )
        )


def _read(path):
    with path.open(encoding='utf-8') as f:
        return list(csv.DictReader(f))
