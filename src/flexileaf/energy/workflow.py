"""Reproducible site-linked 24-hour energy simulation workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import json
import re

import pandas as pd

from flexileaf.dashboard.artifacts import load_run_artifacts

from .baseline import calculate_no_storage_baseline
from .metrics import calculate_scenario_metrics, compare_metrics
from .optimizer import BatteryConfig, optimise_battery_dispatch
from .profiles import build_hourly_energy_profile


HK_TZ = ZoneInfo("Asia/Hong_Kong")


@dataclass(frozen=True)
class EnergySimulationConfig:
    timestep_hours: float = 1.0
    load_archetype: str = "education"
    peak_load_kw: float = 350.0
    daily_solar_mj_m2: float = 18.0
    sunrise_hour: float = 6.0
    sunset_hour: float = 18.5
    solar_shape_exponent: float = 1.45
    battery_capacity_kwh: float = 500.0
    initial_soc_fraction: float = 0.5
    minimum_soc_fraction: float = 0.1
    maximum_soc_fraction: float = 0.9
    maximum_charge_kw: float = 150.0
    maximum_discharge_kw: float = 150.0
    charging_efficiency: float = 0.95
    discharging_efficiency: float = 0.95
    degradation_cost_hkd_per_kwh: float = 0.05
    off_peak_tariff_hkd_per_kwh: float = 1.05
    shoulder_tariff_hkd_per_kwh: float = 1.35
    peak_tariff_hkd_per_kwh: float = 1.75
    export_tariff_hkd_per_kwh: float = 0.50
    peak_demand_penalty_hkd_per_kw: float = 4.0
    carbon_intensity_kg_per_kwh: float = 0.39
    enforce_terminal_soc: bool = True

    @classmethod
    def from_json(cls, path: str | Path) -> "EnergySimulationConfig":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**payload)


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower().strip())
    return value.strip("-")[:50] or "energy"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def run_energy_simulation(
    *,
    site_run_directory: str | Path,
    building_rank: int,
    config: EnergySimulationConfig,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    artifacts = load_run_artifacts(site_run_directory)
    buildings = artifacts["buildings"]
    matches = buildings[
        buildings["building_rank"].astype(int) == int(building_rank)
    ]
    if matches.empty:
        raise ValueError(f"Building rank {building_rank} does not exist.")
    building = matches.iloc[0].to_dict()

    site_summary = artifacts["summary"]
    site_config = site_summary.get("config") or {}
    profile = build_hourly_energy_profile(
        building=building,
        site_config=site_config,
        load_archetype=config.load_archetype,
        peak_load_kw=config.peak_load_kw,
        daily_solar_mj_m2=config.daily_solar_mj_m2,
        sunrise_hour=config.sunrise_hour,
        sunset_hour=config.sunset_hour,
        solar_shape_exponent=config.solar_shape_exponent,
        off_peak_tariff_hkd_per_kwh=(
            config.off_peak_tariff_hkd_per_kwh
        ),
        shoulder_tariff_hkd_per_kwh=(
            config.shoulder_tariff_hkd_per_kwh
        ),
        peak_tariff_hkd_per_kwh=config.peak_tariff_hkd_per_kwh,
        export_tariff_hkd_per_kwh=(
            config.export_tariff_hkd_per_kwh
        ),
        carbon_intensity_kg_per_kwh=(
            config.carbon_intensity_kg_per_kwh
        ),
        timestep_hours=config.timestep_hours,
    )

    battery = BatteryConfig(
        capacity_kwh=config.battery_capacity_kwh,
        initial_soc_fraction=config.initial_soc_fraction,
        minimum_soc_fraction=config.minimum_soc_fraction,
        maximum_soc_fraction=config.maximum_soc_fraction,
        maximum_charge_kw=config.maximum_charge_kw,
        maximum_discharge_kw=config.maximum_discharge_kw,
        charging_efficiency=config.charging_efficiency,
        discharging_efficiency=config.discharging_efficiency,
        degradation_cost_hkd_per_kwh=(
            config.degradation_cost_hkd_per_kwh
        ),
        peak_demand_penalty_hkd_per_kw=(
            config.peak_demand_penalty_hkd_per_kw
        ),
        enforce_terminal_soc=config.enforce_terminal_soc,
    )

    baseline_dispatch = calculate_no_storage_baseline(profile)
    optimised_dispatch, diagnostics = optimise_battery_dispatch(
        profile,
        battery=battery,
        timestep_hours=config.timestep_hours,
    )

    baseline_metrics = calculate_scenario_metrics(
        baseline_dispatch,
        timestep_hours=config.timestep_hours,
        degradation_cost_hkd_per_kwh=(
            config.degradation_cost_hkd_per_kwh
        ),
        peak_demand_penalty_hkd_per_kw=(
            config.peak_demand_penalty_hkd_per_kw
        ),
    )
    optimised_metrics = calculate_scenario_metrics(
        optimised_dispatch,
        timestep_hours=config.timestep_hours,
        degradation_cost_hkd_per_kwh=(
            config.degradation_cost_hkd_per_kwh
        ),
        peak_demand_penalty_hkd_per_kw=(
            config.peak_demand_penalty_hkd_per_kw
        ),
    )
    improvement = compare_metrics(
        baseline_metrics,
        optimised_metrics,
    )

    dispatch = profile.copy()
    for column in (
        "grid_import_kw",
        "grid_export_kw",
        "battery_charge_kw",
        "battery_discharge_kw",
        "battery_soc_kwh",
        "battery_mode",
    ):
        dispatch[f"baseline_{column}"] = baseline_dispatch[column]
        dispatch[f"optimised_{column}"] = optimised_dispatch[column]

    timestamp = datetime.now(HK_TZ).strftime("%Y%m%dT%H%M%S%z")
    building_name = str(building.get("building_name") or "building")
    run_id = f"{_slug(building_name)}-{timestamp}"
    if output_root is None:
        run_directory = (
            Path(site_run_directory)
            / "energy_simulations"
            / run_id
        )
    else:
        run_directory = Path(output_root) / run_id
    run_directory.mkdir(parents=True, exist_ok=True)

    dispatch_path = run_directory / "dispatch.csv"
    summary_path = run_directory / "energy_summary.json"
    dispatch.to_csv(
        dispatch_path,
        index=False,
        encoding="utf-8-sig",
    )

    summary = {
        "run_id": run_id,
        "generated_at_hkt": timestamp,
        "source_site_run": str(site_run_directory),
        "source_site_summary": str(
            artifacts["paths"]["summary"]
        ),
        "selected_building": _json_safe(building),
        "config": asdict(config),
        "baseline": baseline_metrics,
        "optimised": optimised_metrics,
        "improvement": improvement,
        "solver_diagnostics": diagnostics,
        "interpretation": {
            "solar_profile": (
                "Daily HKO or user-provided irradiation is disaggregated "
                "to an hourly daylight curve. It is not measured hourly data."
            ),
            "load_profile": (
                "The default profile is a synthetic archetype scaled to a "
                "user-specified peak. A measured CSV should replace it for "
                "a final engineering case study."
            ),
            "tariff": (
                "Tariffs are visible scenario inputs, not an official bill "
                "calculation unless explicitly replaced with a verified tariff."
            ),
            "optimisation": (
                "A mixed-integer model prevents simultaneous battery charging "
                "and discharging and enforces energy balance, SOC limits, "
                "power limits and terminal SOC."
            ),
        },
    }
    summary_path.write_text(
        json.dumps(_json_safe(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary["output_directory"] = str(run_directory)
    summary["dispatch_path"] = str(dispatch_path)
    summary["summary_path"] = str(summary_path)
    return summary
