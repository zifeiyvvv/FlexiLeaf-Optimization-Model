"""Coordinate transformation and GeoJSON axis-order utilities."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from pyproj import Transformer


_HK1980_TO_WGS84 = Transformer.from_crs(
    "EPSG:2326",
    "EPSG:4326",
    always_xy=True,
)
_WGS84_TO_HK1980 = Transformer.from_crs(
    "EPSG:4326",
    "EPSG:2326",
    always_xy=True,
)


def hk1980_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Convert Hong Kong 1980 Grid metres to WGS84 longitude/latitude."""
    longitude, latitude = _HK1980_TO_WGS84.transform(float(x), float(y))
    return float(longitude), float(latitude)


def wgs84_to_hk1980(longitude: float, latitude: float) -> tuple[float, float]:
    """Convert WGS84 longitude/latitude to Hong Kong 1980 Grid metres."""
    x, y = _WGS84_TO_HK1980.transform(
        float(longitude),
        float(latitude),
    )
    return float(x), float(y)


def make_wgs84_bbox_from_hk1980(
    *,
    centre_x: float,
    centre_y: float,
    radius_m: float,
) -> dict[str, float]:
    """Create a WFS-compatible WGS84 bounding box around an HK1980 point.

    CSDI's WFS 2.0 EPSG:4326 examples use latitude/longitude axis order in
    the BBOX request. The returned dictionary therefore has explicit names
    instead of a positional tuple.
    """
    if radius_m <= 0:
        raise ValueError("radius_m must be positive")

    corners_xy = [
        (centre_x - radius_m, centre_y - radius_m),
        (centre_x - radius_m, centre_y + radius_m),
        (centre_x + radius_m, centre_y - radius_m),
        (centre_x + radius_m, centre_y + radius_m),
    ]
    corners_lon_lat = [hk1980_to_wgs84(x, y) for x, y in corners_xy]
    longitudes = [point[0] for point in corners_lon_lat]
    latitudes = [point[1] for point in corners_lon_lat]

    return {
        "south_lat": min(latitudes),
        "west_lon": min(longitudes),
        "north_lat": max(latitudes),
        "east_lon": max(longitudes),
    }


def _first_coordinate_pair(value: Any) -> tuple[float, float] | None:
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        return float(value[0]), float(value[1])

    if isinstance(value, list):
        for item in value:
            result = _first_coordinate_pair(item)
            if result is not None:
                return result
    return None


def _swap_coordinate_pairs(value: Any) -> Any:
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        swapped = [value[1], value[0]]
        if len(value) > 2:
            swapped.extend(value[2:])
        return swapped

    if isinstance(value, list):
        return [_swap_coordinate_pairs(item) for item in value]
    return value


def normalise_geojson_axis_order(payload: dict[str, Any]) -> dict[str, Any]:
    """Return GeoJSON with standard longitude/latitude coordinate order.

    WFS 2.0 with EPSG:4326 can expose latitude/longitude axis order, while
    GeoJSON conventionally uses longitude/latitude. This function inspects
    the first coordinate and swaps all geometry coordinate pairs only when
    the response clearly looks like Hong Kong latitude followed by longitude.
    """
    result = deepcopy(payload)
    features = result.get("features", [])
    if not isinstance(features, list):
        return result

    first_pair = None
    for feature in features:
        geometry = feature.get("geometry") if isinstance(feature, dict) else None
        if isinstance(geometry, dict):
            first_pair = _first_coordinate_pair(geometry.get("coordinates"))
            if first_pair is not None:
                break

    if first_pair is None:
        return result

    first, second = first_pair
    looks_lat_lon = 20.0 <= first <= 24.0 and 112.0 <= second <= 116.0
    looks_lon_lat = 112.0 <= first <= 116.0 and 20.0 <= second <= 24.0

    if looks_lat_lon and not looks_lon_lat:
        for feature in features:
            if not isinstance(feature, dict):
                continue
            geometry = feature.get("geometry")
            if isinstance(geometry, dict) and "coordinates" in geometry:
                geometry["coordinates"] = _swap_coordinate_pairs(
                    geometry["coordinates"]
                )
    return result
