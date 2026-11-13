from rest_framework import serializers

from fuel.models import FuelStation


def rounded(places, **kwargs):
    """A float rendered as a JSON number rounded to `places` decimals."""
    return serializers.DecimalField(
        max_digits=12, decimal_places=places, coerce_to_string=False, **kwargs
    )


class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(max_length=200, help_text="'lat,lng', 'City, ST' or address")
    finish = serializers.CharField(max_length=200, help_text="'lat,lng', 'City, ST' or address")


class FuelStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FuelStation
        fields = [
            'opis_id',
            'name',
            'address',
            'city',
            'state',
            'latitude',
            'longitude',
            'location_source',
        ]


class FuelStopSerializer(serializers.Serializer):
    station = FuelStationSerializer(source='at.station')
    mile = rounded(1, source='at.mile')
    offset_miles = rounded(1, source='at.offset_miles')
    price_per_gallon = rounded(3, source='at.price')
    gallons = rounded(2)
    cost = rounded(2)


class TripSerializer(serializers.Serializer):
    start = serializers.ListField(child=serializers.FloatField())
    finish = serializers.ListField(child=serializers.FloatField())
    distance_miles = rounded(1)
    total_gallons = rounded(2, source='plan.total_gallons')
    total_cost = rounded(2, source='plan.total_cost')
    # Fuel to reach the first station from an empty tank, billed at that station's price.
    initial_gallons = rounded(2, source='plan.initial_gallons')
    initial_cost = rounded(2, source='plan.initial_cost')
    fuel_stop_count = serializers.IntegerField(source='plan.stop_count')
    fuel_stops = FuelStopSerializer(source='plan.stops', many=True)
    map = serializers.SerializerMethodField()

    def get_map(self, trip):
        """GeoJSON: the route line plus start, finish and fuel-stop points."""
        stations = [stop.at.station for stop in trip.plan.stops]
        return {
            'type': 'FeatureCollection',
            'features': [
                _feature('LineString', [[lon, lat] for lat, lon in trip.geometry], role='route'),
                _point(*trip.start, role='start', label='Start'),
                _point(*trip.finish, role='finish', label='Finish'),
                *(
                    _point(s.latitude, s.longitude, role='fuel_stop', label=s.name)
                    for s in stations
                ),
            ],
        }


def _point(lat, lon, **properties):
    return _feature('Point', [lon, lat], **properties)  # GeoJSON order is [lon, lat]


def _feature(geometry_type, coordinates, **properties):
    return {
        'type': 'Feature',
        'geometry': {'type': geometry_type, 'coordinates': coordinates},
        'properties': properties,
    }
