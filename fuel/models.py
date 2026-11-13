from django.db import models


class FuelStation(models.Model):
    class LocationSource(models.TextChoices):
        EXIT = 'exit', 'Highway exit'
        TOWN = 'town', 'Town centre'

    opis_id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    retail_price = models.DecimalField(max_digits=6, decimal_places=3)
    latitude = models.FloatField()
    longitude = models.FloatField()
    location_source = models.CharField(
        max_length=4, choices=LocationSource.choices, default=LocationSource.TOWN
    )

    class Meta:
        indexes = [models.Index(fields=['latitude', 'longitude'])]

    def __str__(self):
        return f'{self.name} ({self.city}, {self.state}) ${self.retail_price}'


class Place(models.Model):
    """A US town, so "City, ST" input resolves without an API call."""

    state = models.CharField(max_length=2)
    key = models.CharField(max_length=100)  # place_key() of the town's name
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['state', 'key'], name='unique_place')]

    def __str__(self):
        return f'{self.key}, {self.state}'
