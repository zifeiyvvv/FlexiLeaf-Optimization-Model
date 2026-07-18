import json
from pathlib import Path

from flexileaf.site_analysis.buildings import analyse_buildings


def test_building_metrics_are_positive():
    project_root = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (
            project_root
            / "data"
            / "sample"
            / "synthetic_buildings_example.geojson"
        ).read_text(encoding="utf-8")
    )
    frame = analyse_buildings(
        payload,
        query_x_hk1980=835599.0,
        query_y_hk1980=817190.0,
    )
    assert len(frame) == 2
    assert (frame["footprint_area_m2"] > 0).all()
    assert (frame["estimated_total_pv_area_m2"] > 0).all()
    assert frame.iloc[0]["distance_to_query_m"] <= frame.iloc[1][
        "distance_to_query_m"
    ]
