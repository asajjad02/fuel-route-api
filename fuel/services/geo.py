"""Matching fuel stations to positions along a route. Coordinates are (lat, lon) in degrees."""

from dataclasses import dataclass

import numpy as np

from fuel.constants import (
    COARSE_SAMPLE_STEP,
    EARTH_RADIUS_MILES,
    EXIT_CORRIDOR_MILES,
    MILES_PER_DEGREE_LAT,
    ROUTE_SAMPLE_MILES,
    STATION_CHUNK_SIZE,
    TOWN_CORRIDOR_MILES,
)
from fuel.models import FuelStation


@dataclass(frozen=True)
class RouteStation:
    station: FuelStation
    mile: float  # distance along the route to the point nearest the station
    offset_miles: float  # straight-line distance from the route to the station

    @property
    def price(self):
        return float(self.station.retail_price)


def haversine_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance; accepts scalars or numpy arrays (broadcast)."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(a))


def stations_along_route(geometry, route_miles):
    """Return stations close enough to the route to count as on it, sorted by mile along it."""
    points = np.asarray(geometry)
    samples, sample_miles = _sample_route(points, route_miles)
    stations = _stations_in_bbox(points)
    if not stations:
        return []

    # Coarse pass against every 25th mile of road (plus the last point). Every road point is
    # within half that spacing of one of them, so no station the exact pass would keep is lost.
    coords = np.array([(s.latitude, s.longitude) for s in stations])
    coarse = np.vstack((samples[::COARSE_SAMPLE_STEP], samples[-1:]))
    _, coarse_offsets = _nearest_samples(coords, coarse)
    close = coarse_offsets <= TOWN_CORRIDOR_MILES + COARSE_SAMPLE_STEP * ROUTE_SAMPLE_MILES / 2
    stations, coords = [s for s, keep in zip(stations, close, strict=True) if keep], coords[close]
    if not stations:
        return []

    nearest, offsets = _nearest_samples(coords, samples)
    return sorted(
        (
            RouteStation(station, float(sample_miles[idx]), float(offset))
            for station, idx, offset in zip(stations, nearest, offsets, strict=True)
            if offset <= _corridor_miles(station)
        ),
        key=lambda rs: rs.mile,
    )


def _corridor_miles(station):
    if station.location_source == FuelStation.LocationSource.EXIT:
        return EXIT_CORRIDOR_MILES
    return TOWN_CORRIDOR_MILES


def _sample_route(points, route_miles):
    """Resample the route every ROUTE_SAMPLE_MILES; return (points, mile of each)."""
    lat, lon = points[:, 0], points[:, 1]
    cumulative = np.concatenate(
        ([0.0], np.cumsum(haversine_miles(lat[:-1], lon[:-1], lat[1:], lon[1:])))
    )
    if cumulative[-1] > 0:
        # Scale to the router's road distance so stop miles add up to the reported total.
        cumulative *= route_miles / cumulative[-1]
    # Router points can be miles apart on straight highways; interpolating keeps every sample
    # within half a mile of the road, which the tight exit corridor depends on.
    miles = np.append(np.arange(0, cumulative[-1], ROUTE_SAMPLE_MILES), cumulative[-1])
    samples = np.column_stack(
        (np.interp(miles, cumulative, lat), np.interp(miles, cumulative, lon))
    )
    return samples, miles


def _stations_in_bbox(points):
    lat_pad = TOWN_CORRIDOR_MILES / MILES_PER_DEGREE_LAT
    lon_pad = lat_pad / np.cos(np.radians(np.abs(points[:, 0]).max()))
    (min_lat, min_lon), (max_lat, max_lon) = points.min(axis=0), points.max(axis=0)
    return list(
        FuelStation.objects.filter(
            latitude__range=(min_lat - lat_pad, max_lat + lat_pad),
            longitude__range=(min_lon - lon_pad, max_lon + lon_pad),
        )
    )


def _nearest_samples(coords, samples):
    """For each station, the index of its nearest route sample and the distance to it."""
    # Equirectangular approximation: accurate at corridor scale and avoids trig per pair.
    sample_lat, sample_lon = samples[:, 0], samples[:, 1]
    lon_scale = MILES_PER_DEGREE_LAT * np.cos(np.radians(sample_lat))
    nearest, offsets = [], []
    for chunk in np.array_split(coords, -(-len(coords) // STATION_CHUNK_SIZE)):
        dy = (chunk[:, :1] - sample_lat) * MILES_PER_DEGREE_LAT
        dx = (chunk[:, 1:] - sample_lon) * lon_scale
        dist_sq = dx**2 + dy**2
        idx = dist_sq.argmin(axis=1)
        nearest.append(idx)
        offsets.append(np.sqrt(dist_sq[np.arange(len(chunk)), idx]))
    return np.concatenate(nearest), np.concatenate(offsets)
