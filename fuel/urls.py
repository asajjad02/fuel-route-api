from django.urls import path

from fuel.views import RouteMapView, RouteView

urlpatterns = [
    path('route/', RouteView.as_view(), name='route'),
    path('route/map/', RouteMapView.as_view(), name='route-map'),
]
