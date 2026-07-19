#!/usr/bin/env python3
"""Run a site-linked 24-hour FlexiLeaf energy optimisation."""

from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from flexileaf.energy.workflow import (
    EnergySimulationConfig,
    run_energy_simulation,
)
from flexileaf.site_analysis.offline import run_offline_site_analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a 24-hour load/PV profile, calculate a no-storage "
            "baseline and optimise battery dispatch."
        )
    )
    parser.add_argument(
        "--site-run",
        help="Path to a completed Step 2/3 site-analysis run.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Create and use the bundled offline site demonstration.",
    )
    parser.add_argument("--building-rank", type=int, default=0)
    parser.add_argument(
        "--config",
        default=str(
            PROJECT_ROOT / "configs" / "energy_simulation.json"
        ),
    )
    parser.add_argument("--load-archetype")
    parser.add_argument("--peak-load-kw", type=float)
    parser.add_argument("--daily-solar-mj-m2", type=float)
    parser.add_argument("--battery-capacity-kwh", type=float)
    parser.add_argument("--maximum-charge-kw", type=float)
    parser.add_argument("--maximum-discharge-kw", type=float)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.offline and not args.site_run:
        print("ERROR: provide --site-run or use --offline", file=sys.stderr)
        return 2

    try:
        config_payload = json.loads(
            Path(args.config).read_text(encoding="utf-8")
        )
        overrides = {
            "load_archetype": args.load_archetype,
            "peak_load_kw": args.peak_load_kw,
            "daily_solar_mj_m2": args.daily_solar_mj_m2,
            "battery_capacity_kwh": args.battery_capacity_kwh,
            "maximum_charge_kw": args.maximum_charge_kw,
            "maximum_discharge_kw": args.maximum_discharge_kw,
        }
        for key, value in overrides.items():
            if value is not None:
                config_payload[key] = value
        config = EnergySimulationConfig(**config_payload)

        if args.offline:
            site_summary = run_offline_site_analysis(
                project_root=PROJECT_ROOT,
            )
            site_run = site_summary["output_directory"]
        else:
            site_run = args.site_run

        summary = run_energy_simulation(
            site_run_directory=site_run,
            building_rank=args.building_rank,
            config=config,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    baseline = summary["baseline"]
    optimised = summary["optimised"]
    improvement = summary["improvement"]
    diagnostics = summary["solver_diagnostics"]

    print("\nFlexiLeaf energy simulation completed")
    print("-------------------------------------")
    print(
        "Building:",
        summary["selected_building"].get("building_name"),
    )
    print(
        "PV generation:",
        f'{optimised["pv_generation_kwh"]:.1f} kWh/day',
    )
    print(
        "Baseline peak:",
        f'{baseline["peak_grid_import_kw"]:.1f} kW',
    )
    print(
        "Optimised peak:",
        f'{optimised["peak_grid_import_kw"]:.1f} kW',
    )
    print(
        "Peak reduction:",
        f'{improvement["peak_reduction_percent"]:.1f}%',
    )
    print(
        "Net energy-cost saving:",
        f'{improvement["energy_cost_saving_percent"]:.1f}%',
    )
    print(
        "PV self-consumption:",
        f'{baseline["pv_self_consumption_fraction"] * 100:.1f}% -> '
        f'{optimised["pv_self_consumption_fraction"] * 100:.1f}%',
    )
    print(
        "Maximum balance error:",
        f'{diagnostics["maximum_balance_error_kw"]:.3e} kW',
    )
    print("Output:", summary["output_directory"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
