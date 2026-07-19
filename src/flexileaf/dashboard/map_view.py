"""Prepare an interactive 3D building map with transparent result properties."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import math

import pandas as pd
import pydeck as pdk


def _finite_number(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return numeric if math.isfinite(numeric) else default


def prepare_map_geojson(
    payload: dict[str, Any],
    building_frame: pd.DataFrame,
    *,
    selected_rank: int,
) -> dict[str, Any]:
    """Merge calculated metrics into GeoJSON and assign map colours."""
    result = deepcopy(payload)
    features = result.get("features", [])
    if not isinstance(features, list):
        return result

    records = building_frame.to_dict(orient="records")
    by_feature_index = {
        int(_finite_number(record.get("feature_index"), -1)): record
        for record in records
    }
    positive_powers = [
        _finite_number(record.get("estimated_total_current_power_kw"))
        for record in records
    ]
    maximum_power = max(positive_powers, default=0.0)

    for feature_index, feature in enumerate(features):
        if not isinstance(feature, dict):
            continue
        record = by_feature_index.get(feature_index)
        if record is None:
            continue

        rank = int(_finite_number(record.get("building_rank"), -1))
        power_kw = _finite_number(
            record.get("estimated_total_current_power_kw")
        )
        intensity = (
            min(max(power_kw / maximum_power, 0.0), 1.0)
            if maximum_power > 0
            else 0.0
        )

        if rank == int(selected_rank):
            fill_color = [244, 174, 37, 225]
            line_color = [112, 73, 0, 255]
        else:
            fill_color = [
                41,
                int(105 + 105 * intensity),
                int(95 - 35 * intensity),
                170,
            ]
            line_color = [25, 70, 44, 210]

        properties = feature.setdefault("properties", {})
        properties.update(
            {
                "flexileaf_building_rank": rank,
                "flexileaf_building_name": str(
                    record.get("building_name") or "Unnamed building"
                ),
                "flexileaf_distance_m": round(
                    _finite_number(record.get("distance_to_query_m")),
                    1,
                ),
                "flexileaf_pv_area_m2": round(
                    _finite_number(
                        record.get("estimated_total_pv_area_m2")
                    ),
                    1,
                ),
                "flexileaf_current_power_kw": round(power_kw, 2),
                "flexileaf_height_m": max(
                    _finite_number(record.get("height_m"), 1.0),
                    1.0,
                ),
                "flexileaf_fill_color": fill_color,
                "flexileaf_line_color": line_color,
            }
        )
    return result


def build_site_map(
    *,
    map_geojson: dict[str, Any],
    selected_location: dict[str, Any],
    zoom: float = 15.5,
) -> pdk.Deck:
    longitude = _finite_number(selected_location.get("longitude"), 114.17)
    latitude = _finite_number(selected_location.get("latitude"), 22.32)

    buildings = pdk.Layer(
        "GeoJsonLayer",
        id="flexileaf-buildings",
        data=map_geojson,
        pickable=True,
        stroked=True,
        filled=True,
        extruded=True,
        wireframe=True,
        get_fill_color="properties.flexileaf_fill_color",
        get_line_color="properties.flexileaf_line_color",
        get_elevation="properties.flexileaf_height_m",
        elevation_scale=1,
        line_width_min_pixels=1,
        opacity=0.85,
    )
    site_marker = pdk.Layer(
        "ScatterplotLayer",
        id="flexileaf-site-marker",
        data=[
            {
                "longitude": longitude,
                "latitude": latitude,
                "label": (
                    selected_location.get("name_en")
                    or selected_location.get("name_zh")
                    or "Selected location"
                ),
            }
        ],
        get_position="[longitude, latitude]",
        get_radius=14,
        radius_units="meters",
        get_fill_color=[215, 52, 52, 230],
        get_line_color=[255, 255, 255, 255],
        line_width_min_pixels=2,
        stroked=True,
        pickable=True,
    )

    tooltip = {
        "html": (
            "<b>{flexileaf_building_name}</b><br/>"
            "Rank: {flexileaf_building_rank}<br/>"
            "Distance: {flexileaf_distance_m} m<br/>"
            "Estimated PV area: {flexileaf_pv_area_m2} m²<br/>"
            "Estimated current power: "
            "{flexileaf_current_power_kw} kW"
        ),
        "style": {
            "backgroundColor": "#17321F",
            "color": "white",
            "fontSize": "13px",
        },
    }

    return pdk.Deck(
        map_style=None,
        initial_view_state=pdk.ViewState(
            longitude=longitude,
            latitude=latitude,
            zoom=zoom,
            pitch=45,
            bearing=0,
        ),
        layers=[buildings, site_marker],
        tooltip=tooltip,
    )
