"""Domain errors. Each carries its HTTP status, so DRF's default handler renders it directly."""

from rest_framework import status
from rest_framework.exceptions import APIException


class InvalidLocation(APIException):
    """The start or finish could not be resolved to a US location."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'invalid_location'


class RouteNotFound(APIException):
    """The routing service rejected the trip, e.g. no road connects the two points."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = 'route_not_found'


class NoStationInRange(APIException):
    """The route has a stretch longer than the vehicle's range with no fuel station."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = 'no_station_in_range'

    def __init__(self, mile):
        super().__init__(f'No fuel station within range after mile {mile:.0f} of the route.')
        self.mile = mile


class RoutingServiceError(APIException):
    """The routing service is unreachable, misconfigured or failing."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_code = 'routing_service_error'


class QuotaExceeded(APIException):
    """The ORS quota is used up. DRF sends `wait` as the Retry-After header."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = 'quota_exceeded'

    def __init__(self, retry_after):
        super().__init__('Routing service quota exceeded, please retry later.')
        self.wait = retry_after
