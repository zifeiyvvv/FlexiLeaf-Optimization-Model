import json
from pathlib import Path

import pandas as pd

from flexileaf.dashboard.formatting import (
    format_building_option,
    format_location_option,
)
from flexileaf.dashboard.map_view import prepare_map_geojson


def test_location_option_contains_rank_and_name():
    label = format_location_option(
        {
            "candidate_rank": 2,
            "name_en": "Example Place",
            "address_en": "1 Example Road",
            "district_en": "Example District",
        }
    )
    assert "#2" in label
    assert "Example Place" in label


def test_building_option_contains_metrics():
    label = format_building_option(
        {
            "building_rank": 1,
            "building_name": "Building A",
            "distance_to_query_m": 42.3,
            "estimated_total_pv_area_m2": 500,
            "estimated_total_current_power_kw": 50.2,
        }
    )
    assert "#1" in label
    assert "500 m²" in label
    assert "50.2 kW" in label


def test_selected_building_receives_highlight_colour():
    project_root = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (
            project_root
            / "data"
            / "sample"
            / "synthetic_buildings_example.geojson"
        ).read_text(encoding="utf-8")
    )
    frame = pd.DataFrame(
        [
            {
                "feature_index": 0,
                "building_rank": 0,
                "building_name": "A",
                "distance_to_query_m": 1,
                "estimated_total_pv_area_m2": 100,
                "estimated_total_current_power_kw": 20,
                "height_m": 30,
            },
            {
                "feature_index": 1,
                "building_rank": 1,
                "building_name": "B",
                "distance_to_query_m": 10,
                "estimated_total_pv_area_m2": 80,
                "estimated_total_current_power_kw": 15,
                "height_m": 20,
            },
        ]
    )
    enriched = prepare_map_geojson(
        payload,
        frame,
        selected_rank=1,
    )
    selected_properties = enriched["features"][1]["properties"]
    assert selected_properties["flexileaf_fill_color"] == [
        244,
        174,
        37,
        225,
    ]
    assert selected_properties["flexileaf_building_name"] == "B"
