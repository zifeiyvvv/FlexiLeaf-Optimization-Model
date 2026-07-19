"""Annual system-configuration dispatch and comparison."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from flexileaf.energy.baseline import calculate_no_storage_baseline
from flexileaf.energy.metrics import (
    calculate_scenario_metrics,
    compare_metrics,
)
from flexileaf.energy.optimizer import (
    BatteryConfig,
    optimise_battery_dispatch,
)


def tariff_profile(
    timestamps: pd.Series,
    tariff: dict[str, float],
) -> np.ndarray:
    hours = pd.to_datetime(timestamps).dt.hour.to_numpy()
    values = np.full(
        len(hours),
        float(tariff["shoulder_hkd_per_kwh"]),
    )
    values[(hours < 7) | (hours >= 23)] = float(
        tariff["off_peak_hkd_per_kwh"]
    )
    values[(hours >= 18) & (hours < 22)] = float(
        tariff["peak_hkd_per_kwh"]
    )
    return values


def _system_pv(
    pv: pd.DataFrame,
    configuration: str,
) -> np.ndarray:
    if configuration == "grid_only":
        return np.zeros(len(pv))
    if configuration == "roof_pv_only":
        return pv["roof_pv_kw"].to_numpy(dtype=float)
    return pv["total_pv_kw"].to_numpy(dtype=float)


def _battery_spec(
    *,
    configuration: str,
    scenario: dict[str, Any],
) -> tuple[float, float]:
    if configuration == "roof_plus_flexileaf_battery":
        return (
            float(scenario["stationary_battery_kwh"]),
            float(scenario["stationary_battery_kw"]),
        )
    if configuration == "full_microgrid_v2g":
        return (
            float(scenario["stationary_battery_kwh"])
            + float(scenario["v2g_equivalent_kwh"]),
            float(scenario["stationary_battery_kw"])
            + float(scenario["v2g_equivalent_kw"]),
        )
    return 0.0, 0.0


def run_configuration(
    *,
    load: pd.DataFrame,
    pv: pd.DataFrame,
    configuration: str,
    scenario: dict[str, Any],
    tariff: dict[str, float],
    carbon_intensity_kg_per_kwh: float,
    peak_penalty_hkd_per_kw_day: float,
    degradation_cost_hkd_per_kwh: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    profile = pd.DataFrame(
        {
            "timestamp": load["timestamp"],
            "date": load["date"],
            "month": load["month"],
            "load_kw": load["total_load_kw"].to_numpy(dtype=float),
            "pv_generation_kw": _system_pv(pv, configuration),
            "buy_tariff_hkd_per_kwh": tariff_profile(
                load["timestamp"], tariff
            ),
            "export_tariff_hkd_per_kwh": float(
                tariff["export_hkd_per_kwh"]
            ),
            "carbon_intensity_kg_per_kwh": float(
                carbon_intensity_kg_per_kwh
            ),
        }
    )

    capacity_kwh, power_kw = _battery_spec(
        configuration=configuration,
        scenario=scenario,
    )

    if capacity_kwh <= 0:
        dispatch = calculate_no_storage_baseline(profile)
        solver_diagnostics = {
            "solver": "not_required",
            "daily_solve_count": 0,
            "maximum_balance_error_kw": 0.0,
            "maximum_simultaneous_charge_discharge_kw": 0.0,
        }
    else:
        daily_results = []
        maximum_balance_error = 0.0
        maximum_simultaneous = 0.0
        solver_messages = set()

        for _, day in profile.groupby("date", sort=True):
            battery = BatteryConfig(
                capacity_kwh=capacity_kwh,
                initial_soc_fraction=0.50,
                minimum_soc_fraction=0.10,
                maximum_soc_fraction=0.90,
                maximum_charge_kw=power_kw,
                maximum_discharge_kw=power_kw,
                charging_efficiency=0.95,
                discharging_efficiency=0.95,
                degradation_cost_hkd_per_kwh=(
                    degradation_cost_hkd_per_kwh
                ),
                peak_demand_penalty_hkd_per_kw=(
                    peak_penalty_hkd_per_kw_day
                ),
                enforce_terminal_soc=True,
            )
            optimised, diagnostics = optimise_battery_dispatch(
                day.reset_index(drop=True),
                battery=battery,
                timestep_hours=1.0,
            )
            optimised["timestamp"] = day["timestamp"].to_numpy()
            optimised["date"] = day["date"].to_numpy()
            optimised["month"] = day["month"].to_numpy()
            daily_results.append(optimised)
            maximum_balance_error = max(
                maximum_balance_error,
                diagnostics["maximum_balance_error_kw"],
            )
            maximum_simultaneous = max(
                maximum_simultaneous,
                diagnostics[
                    "maximum_simultaneous_charge_discharge_kw"
                ],
            )
            solver_messages.add(diagnostics["solver_message"])

        dispatch = pd.concat(daily_results, ignore_index=True)
        solver_diagnostics = {
            "solver": "scipy.optimize.milp / HiGHS",
            "daily_solve_count": int(profile["date"].nunique()),
            "maximum_balance_error_kw": maximum_balance_error,
            "maximum_simultaneous_charge_discharge_kw": (
                maximum_simultaneous
            ),
            "solver_messages": sorted(solver_messages),
            "battery_capacity_kwh": capacity_kwh,
            "battery_power_kw": power_kw,
            "v2g_model": (
                "aggregated equivalent storage"
                if configuration == "full_microgrid_v2g"
                else "not_used"
            ),
        }

    metrics = calculate_scenario_metrics(
        dispatch,
        timestep_hours=1.0,
        degradation_cost_hkd_per_kwh=degradation_cost_hkd_per_kwh,
        peak_demand_penalty_hkd_per_kw=0.0,
    )
    metrics.update(
        {
            "configuration": configuration,
            "battery_capacity_kwh": capacity_kwh,
            "battery_power_kw": power_kw,
            "solver_diagnostics": solver_diagnostics,
        }
    )
    return dispatch, metrics


def compare_to_grid(
    grid_metrics: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, float]:
    comparison = compare_metrics(grid_metrics, metrics)
    return comparison
