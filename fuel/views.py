from urllib.parse import urlencode

from django.urls import reverse
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from fuel.serializers import RouteRequestSerializer, TripSerializer
from fuel.services.trip import plan_trip


class RouteView(APIView):
    """POST {"start", "finish"}: cheapest fuel stops, total cost and a GeoJSON map of the route."""

    def post(self, request):
        params = _validated(request.data)
        data = TripSerializer(plan_trip(**params)).data
        data['map_url'] = request.build_absolute_uri(f'{reverse("route-map")}?{urlencode(params)}')
        return Response(data)


class RouteMapView(APIView):
    """GET ?start=&finish=: the same plan drawn on an interactive map."""

    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'fuel/map.html'

    def get(self, request):
        params = _validated(request.query_params)
        return Response({'trip': TripSerializer(plan_trip(**params)).data, **params})


def _validated(data):
    serializer = RouteRequestSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data
