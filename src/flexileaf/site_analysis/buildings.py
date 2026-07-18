"""Analyse CSDI building polygons in metric Hong Kong coordinates."""

from __future__ import annotations

import math
import re
from typing import Any, Iterable

import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform as transform_geometry

from .geo import normalise_geojson_axis_order


_WGS84_TO_HK1980 = Transformer.from_crs(
    "EPSG:4326",
    "EPSG:2326",
    always_xy=True,
)
_HK1980_TO_WGS84 = Transformer.from_crs(
    "EPSG:2326",
    "EPSG:4326",
    always_xy=True,
)


_PREFERRED_NAME_KEYS = (
    "BUILDING_NAME_EN",
    "BLDG_NAME_EN",
    "NAME_EN",
    "NAMEEN",
    "ENGLISH_NAME",
    "BUILDING_NAME",
    "BLDG_NAME",
    "NAME",
)

_PREFERRED_HEIGHT_KEYS = (
    "BUILDING_HEIGHT",
    "BLDG_HEIGHT",
    "HEIGHT_M",
    "HEIGHT",
    "BHEIGHT",
    "TOP_HEIGHT",
)


def _first_numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None

    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    if not match:
        return None
    numeric = float(match.group())
    return numeric if math.isfinite(numeric) else None


def _property_lookup(
    properties: dict[str, Any],
    preferred_keys: Iterable[str],
) -> tuple[Any, str | None]:
    uppercase_map = {str(key).upper(): key for key in properties}
    for candidate in preferred_keys:
        original_key = uppercase_map.get(candidate.upper())
        if original_key is not None:
            return properties.get(original_key), str(original_key)
    return None, None


def _extract_height(
    properties: dict[str, Any],
    default_height_m: float,
) -> tuple[float, str]:
    value, key = _property_lookup(properties, _PREFERRED_HEIGHT_KEYS)
    numeric = _first_numeric(value)
    if numeric is not None and numeric > 0:
        return numeric, f"dataset:{key}"

    for original_key, original_value in properties.items():
        key_upper = str(original_key).upper()
        if "HEIGHT" not in key_upper:
            continue
        numeric = _first_numeric(original_value)
        if numeric is not None and numeric > 0:
            return numeric, f"dataset:{original_key}"

    return float(default_height_m), "assumption:default"


def _extract_name(properties: dict[str, Any], feature_id: Any) -> str:
    value, _ = _property_lookup(properties, _PREFERRED_NAME_KEYS)
    if value not in (None, ""):
        return str(value)

    for key, candidate in properties.items():
        if "NAME" in str(key).upper() and candidate not in (None, ""):
            return str(candidate)
    return str(feature_id or "Unnamed building")


def analyse_buildings(
    payload: dict[str, Any],
    *,
    query_x_hk1980: float,
    query_y_hk1980: float,
    default_height_m: float = 30.0,
    roof_usable_ratio: float = 0.65,
    facade_usable_ratio: float = 0.25,
) -> pd.DataFrame:
    """Calculate footprint, perimeter, distance and usable PV area.

    `estimated_facade_usable_m2` is a planning assumption:
    perimeter × height × facade_usable_ratio. It is not a façade survey and
    does not account for windows, orientation, shading, access or fire codes.
    """
    if default_height_m <= 0:
        raise ValueError("default_height_m must be positive")
    if not 0 <= roof_usable_ratio <= 1:
        raise ValueError("roof_usable_ratio must be between 0 and 1")
    if not 0 <= facade_usable_ratio <= 1:
        raise ValueError("facade_usable_ratio must be between 0 and 1")

    normalised = normalise_geojson_axis_order(payload)
    features = normalised.get("features", [])
    if not isinstance(features, list):
        raise ValueError("GeoJSON does not contain a feature list.")

    query_point = Point(float(query_x_hk1980), float(query_y_hk1980))
    rows: list[dict[str, Any]] = []

    for feature_index, feature in enumerate(features):
        if not isinstance(feature, dict):
            continue
        geometry_payload = feature.get("geometry")
        if not isinstance(geometry_payload, dict):
            continue

        try:
            geometry_wgs84 = shape(geometry_payload)
        except Exception:
            continue
        if geometry_wgs84.is_empty:
            continue

        geometry_hk1980 = transform_geometry(
            _WGS84_TO_HK1980.transform,
            geometry_wgs84,
        )
        if geometry_hk1980.is_empty or not geometry_hk1980.is_valid:
            geometry_hk1980 = geometry_hk1980.buffer(0)
        if geometry_hk1980.is_empty:
            continue

        properties = feature.get("properties") or {}
        if not isinstance(properties, dict):
            properties = {}

        feature_id = feature.get("id", feature_index)
        building_name = _extract_name(properties, feature_id)
        height_m, height_source = _extract_height(
            properties,
            default_height_m,
        )

        footprint_area_m2 = float(geometry_hk1980.area)
        perimeter_m = float(geometry_hk1980.length)
        centroid = geometry_hk1980.centroid
        centroid_lon, centroid_lat = _HK1980_TO_WGS84.transform(
            centroid.x,
            centroid.y,
        )
        distance_m = float(geometry_hk1980.distance(query_point))

        roof_usable_m2 = footprint_area_m2 * roof_usable_ratio
        facade_gross_m2 = perimeter_m * height_m
        facade_usable_m2 = facade_gross_m2 * facade_usable_ratio

        rows.append(
            {
                "feature_index": feature_index,
                "feature_id": feature_id,
                "building_name": building_name,
                "geometry_type": geometry_wgs84.geom_type,
                "centroid_longitude": float(centroid_lon),
                "centroid_latitude": float(centroid_lat),
                "distance_to_query_m": distance_m,
                "footprint_area_m2": footprint_area_m2,
                "perimeter_m": perimeter_m,
                "height_m": height_m,
                "height_source": height_source,
                "estimated_roof_usable_m2": roof_usable_m2,
                "estimated_facade_gross_m2": facade_gross_m2,
                "estimated_facade_usable_m2": facade_usable_m2,
                "estimated_total_pv_area_m2": (
                    roof_usable_m2 + facade_usable_m2
                ),
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame

    frame = frame.sort_values(
        by=["distance_to_query_m", "footprint_area_m2"],
        ascending=[True, False],
    ).reset_index(drop=True)
    frame.insert(0, "building_rank", range(len(frame)))
    return frame
