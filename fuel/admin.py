from django.contrib import admin

from fuel.models import FuelStation


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    list_display = (
        'opis_id',
        'name',
        'address',
        'city',
        'state',
        'retail_price',
        'location_source',
    )
    list_filter = ('location_source', 'state')
    search_fields = ('name', 'city')
