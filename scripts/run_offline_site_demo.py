#!/usr/bin/env python3
"""Run the Step 2 analysis functions against bundled offline samples."""

from __future__ import annotations

from pathlib import Path
import json
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from flexileaf.open_data.hko import HKOClient
from flexileaf.site_analysis.buildings import analyse_buildings
from flexileaf.site_analysis.location import (
    location_candidates,
    select_location_candidate,
)
from flexileaf.site_analysis.pv_model import estimate_building_pv
from flexileaf.site_analysis.solar import (
    choose_nearest_solar_station,
    select_solar_observation,
)


def main() -> int:
    sample_root = PROJECT_ROOT / "data" / "sample"
    output = PROJECT_ROOT / "data" / "processed" / "offline_site_demo"
    output.mkdir(parents=True, exist_ok=True)

    location_payload = json.loads(
        (sample_root / "location_search_example.json").read_text(
            encoding="utf-8"
        )
    )
    building_payload = json.loads(
        (sample_root / "synthetic_buildings_example.geojson").read_text(
            encoding="utf-8"
        )
    )
    solar_text = (
        sample_root / "hko_live_solar_example.csv"
    ).read_text(encoding="utf-8")

    candidates = location_candidates(location_payload)
    location = select_location_candidate(candidates, 0)
    buildings = analyse_buildings(
        building_payload,
        query_x_hk1980=location["x_hk1980"],
        query_y_hk1980=location["y_hk1980"],
    )
    solar = HKOClient.parse_latest_solar_radiation(solar_text)
    station = choose_nearest_solar_station(
        longitude=location["longitude"],
        latitude=location["latitude"],
    )
    observation = select_solar_observation(
        solar,
        station["station_code"],
    )

    pv_rows = [
        estimate_building_pv(
            row,
            irradiance_wm2=float(observation["global_solar_wm2"]),
        )
        for row in buildings.to_dict(orient="records")
    ]
    results = pd.concat(
        [buildings, pd.DataFrame(pv_rows)],
        axis=1,
    )

    candidates.to_csv(
        output / "location_candidates.csv",
        index=False,
        encoding="utf-8-sig",
    )
    results.to_csv(
        output / "building_analysis.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary = {
        "note": (
            "Offline demonstration only. Building polygons are synthetic; "
            "the first location record follows the official LandsD example."
        ),
        "selected_location": location,
        "selected_station": station,
        "solar_observation": {
            key: (
                value.isoformat()
                if isinstance(value, pd.Timestamp)
                else value
            )
            for key, value in observation.items()
        },
        "nearest_building": results.iloc[0].to_dict(),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print("Offline site demo completed.")
    print(f"Output: {output}")
    print(results[
        [
            "building_rank",
            "building_name",
            "distance_to_query_m",
            "estimated_total_pv_area_m2",
            "estimated_total_current_power_kw",
        ]
    ].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
