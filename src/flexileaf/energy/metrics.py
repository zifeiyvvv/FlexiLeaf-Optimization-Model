"""Comparable baseline and optimised energy-system metrics."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def calculate_scenario_metrics(
    dispatch: pd.DataFrame,
    *,
    timestep_hours: float,
    degradation_cost_hkd_per_kwh: float,
    peak_demand_penalty_hkd_per_kw: float,
) -> dict[str, float]:
    required = {
        "load_kw",
        "pv_generation_kw",
        "grid_import_kw",
        "grid_export_kw",
        "battery_charge_kw",
        "battery_discharge_kw",
        "buy_tariff_hkd_per_kwh",
        "export_tariff_hkd_per_kwh",
        "carbon_intensity_kg_per_kwh",
    }
    missing = required.difference(dispatch.columns)
    if missing:
        raise ValueError(
            f"Dispatch table is missing columns: {sorted(missing)}"
        )

    load_kwh = float(dispatch["load_kw"].sum() * timestep_hours)
    pv_kwh = float(
        dispatch["pv_generation_kw"].sum() * timestep_hours
    )
    import_kwh = float(
        dispatch["grid_import_kw"].sum() * timestep_hours
    )
    export_kwh = float(
        dispatch["grid_export_kw"].sum() * timestep_hours
    )
    charge_kwh = float(
        dispatch["battery_charge_kw"].sum() * timestep_hours
    )
    discharge_kwh = float(
        dispatch["battery_discharge_kw"].sum() * timestep_hours
    )

    purchase_cost = float(
        (
            dispatch["grid_import_kw"]
            * dispatch["buy_tariff_hkd_per_kwh"]
        ).sum()
        * timestep_hours
    )
    export_revenue = float(
        (
            dispatch["grid_export_kw"]
            * dispatch["export_tariff_hkd_per_kwh"]
        ).sum()
        * timestep_hours
    )
    cycle_cost = float(
        (charge_kwh + discharge_kwh)
        * degradation_cost_hkd_per_kwh
    )
    peak_kw = float(dispatch["grid_import_kw"].max())
    peak_penalty = peak_kw * peak_demand_penalty_hkd_per_kw
    net_energy_cost = purchase_cost - export_revenue
    objective_cost = net_energy_cost + cycle_cost + peak_penalty

    carbon_kg = float(
        (
            dispatch["grid_import_kw"]
            * dispatch["carbon_intensity_kg_per_kwh"]
        ).sum()
        * timestep_hours
    )
    self_consumed_pv_kwh = max(pv_kwh - export_kwh, 0.0)
    self_consumption = (
        self_consumed_pv_kwh / pv_kwh if pv_kwh > 0 else 0.0
    )
    self_sufficiency = (
        max(load_kwh - import_kwh, 0.0) / load_kwh
        if load_kwh > 0
        else 0.0
    )

    return {
        "load_energy_kwh": load_kwh,
        "pv_generation_kwh": pv_kwh,
        "grid_import_kwh": import_kwh,
        "grid_export_kwh": export_kwh,
        "battery_charge_kwh": charge_kwh,
        "battery_discharge_kwh": discharge_kwh,
        "peak_grid_import_kw": peak_kw,
        "electricity_purchase_hkd": purchase_cost,
        "export_revenue_hkd": export_revenue,
        "battery_cycle_cost_hkd": cycle_cost,
        "peak_penalty_hkd": peak_penalty,
        "net_energy_cost_hkd": net_energy_cost,
        "objective_cost_hkd": objective_cost,
        "carbon_emissions_kg": carbon_kg,
        "pv_self_consumption_fraction": self_consumption,
        "load_self_sufficiency_fraction": self_sufficiency,
    }


def compare_metrics(
    baseline: dict[str, float],
    optimised: dict[str, float],
) -> dict[str, float]:
    def reduction(key: str) -> float:
        base = float(baseline[key])
        improved = float(optimised[key])
        return (base - improved) / base * 100.0 if base > 0 else 0.0

    return {
        "peak_reduction_percent": reduction("peak_grid_import_kw"),
        "grid_import_reduction_percent": reduction("grid_import_kwh"),
        "energy_cost_saving_percent": reduction("net_energy_cost_hkd"),
        "objective_cost_saving_percent": reduction("objective_cost_hkd"),
        "carbon_reduction_percent": reduction("carbon_emissions_kg"),
        "self_consumption_gain_percentage_points": (
            optimised["pv_self_consumption_fraction"]
            - baseline["pv_self_consumption_fraction"]
        )
        * 100.0,
        "self_sufficiency_gain_percentage_points": (
            optimised["load_self_sufficiency_fraction"]
            - baseline["load_self_sufficiency_fraction"]
        )
        * 100.0,
    }
