#!/usr/bin/env python3
"""Run location-to-building live solar potential analysis."""

from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from flexileaf.open_data.http_client import OpenDataError
from flexileaf.site_analysis.workflow import (
    SiteAnalysisConfig,
    run_site_analysis,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve a Hong Kong location, download nearby buildings, "
            "select the nearest HKO solar station and estimate current "
            "photovoltaic potential."
        )
    )
    parser.add_argument("--query", required=True)
    parser.add_argument("--candidate-index", type=int, default=0)
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "configs" / "site_analysis.json"),
    )
    parser.add_argument(
        "--data-root",
        default=str(PROJECT_ROOT / "data"),
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Optional custom directory for processed run folders.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        config = SiteAnalysisConfig.from_json(args.config)
        summary = run_site_analysis(
            query=args.query,
            candidate_index=args.candidate_index,
            config=config,
            data_root=args.data_root,
            output_root=args.output_root,
        )
    except (OpenDataError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    selected_location = summary["selected_location"]
    selected_building = summary["selected_building"]
    station = summary["nearest_solar_station"]
    observation = summary["solar_observation"]

    print("\nFlexiLeaf site analysis completed")
    print("--------------------------------")
    print(
        "Location:",
        selected_location.get("name_en")
        or selected_location.get("name_zh"),
    )
    print(
        "Coordinates:",
        f'{selected_location["latitude"]:.6f}, '
        f'{selected_location["longitude"]:.6f}',
    )
    print(
        "Solar station:",
        f'{station["station_name"]} '
        f'({station["distance_to_site_m"] / 1000:.2f} km)',
    )
    print(
        "Global solar radiation:",
        f'{float(observation["global_solar_wm2"]):.1f} W/m²',
    )
    print("Buildings analysed:", summary["building_count"])
    print(
        "Nearest building:",
        selected_building.get("building_name"),
    )
    print(
        "Estimated PV area:",
        f'{float(selected_building["estimated_total_pv_area_m2"]):.1f} m²',
    )
    print(
        "Estimated current power:",
        f'{float(selected_building["estimated_total_current_power_kw"]):.2f} kW',
    )
    print("Output:", summary["output_directory"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
