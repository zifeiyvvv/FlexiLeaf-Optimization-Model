#!/usr/bin/env python3
"""Generate the fixed 2025 FlexiLeaf prospective digital-twin dataset."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from flexileaf.digital_twin.case_study import (
    generate_design_basis_case,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default=str(
            PROJECT_ROOT
            / "configs"
            / "design_basis_case_2025.json"
        ),
    )
    parser.add_argument(
        "--solar",
        default=str(
            PROJECT_ROOT
            / "data"
            / "source"
            / "hko"
            / "daily_KP_GSR_2025.csv"
        ),
    )
    parser.add_argument(
        "--humidity",
        default=str(
            PROJECT_ROOT
            / "data"
            / "source"
            / "hko"
            / "daily_KP_RH_2025.csv"
        ),
    )
    parser.add_argument(
        "--sunshine",
        default=str(
            PROJECT_ROOT
            / "data"
            / "source"
            / "hko"
            / "daily_KP_SUN_2025.csv"
        ),
    )
    parser.add_argument(
        "--output",
        default=str(
            PROJECT_ROOT
            / "data"
            / "case_study"
            / "design_basis_2025"
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = generate_design_basis_case(
            config_path=args.config,
            source_solar_path=args.solar,
            source_humidity_path=args.humidity,
            source_sunshine_path=args.sunshine,
            output_directory=args.output,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    headline = result["headline"]
    print("\nFlexiLeaf design-basis case generated")
    print("------------------------------------")
    print("Output:", result["output_directory"])
    print(
        "Design full-microgrid annual PV:",
        f'{headline["annual_pv_generation_mwh"]:.1f} MWh',
    )
    print(
        "Peak reduction vs grid-only:",
        f'{headline["peak_reduction_percent"]:.1f}%',
    )
    print(
        "Energy cost saving vs grid-only:",
        f'{headline["energy_cost_saving_percent"]:.1f}%',
    )
    print(
        "Carbon reduction vs grid-only:",
        f'{headline["carbon_reduction_percent"]:.1f}%',
    )
    print(
        "PV self-consumption:",
        f'{headline["pv_self_consumption_percent"]:.1f}%',
    )
    print(
        "Disclosure: prospective simulation, not measured operation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
