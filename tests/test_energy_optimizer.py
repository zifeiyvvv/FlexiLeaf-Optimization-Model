import numpy as np
import pandas as pd

from flexileaf.energy.baseline import calculate_no_storage_baseline
from flexileaf.energy.metrics import calculate_scenario_metrics
from flexileaf.energy.optimizer import (
    BatteryConfig,
    optimise_battery_dispatch,
)


def make_profile():
    hours = np.arange(24)
    load = np.where((hours >= 18) & (hours < 22), 180.0, 90.0)
    pv = np.where((hours >= 9) & (hours < 16), 160.0, 0.0)
    tariff = np.where((hours >= 18) & (hours < 22), 2.0, 1.0)
    return pd.DataFrame(
        {
            "load_kw": load,
            "pv_generation_kw": pv,
            "buy_tariff_hkd_per_kwh": tariff,
            "export_tariff_hkd_per_kwh": 0.3,
            "carbon_intensity_kg_per_kwh": 0.4,
        }
    )


def test_optimiser_respects_balance_and_binary_mode():
    profile = make_profile()
    result, diagnostics = optimise_battery_dispatch(
        profile,
        battery=BatteryConfig(
            capacity_kwh=300,
            maximum_charge_kw=100,
            maximum_discharge_kw=100,
            peak_demand_penalty_hkd_per_kw=5,
        ),
    )
    assert diagnostics["maximum_balance_error_kw"] < 1e-6
    assert (
        diagnostics["maximum_simultaneous_charge_discharge_kw"]
        < 1e-6
    )
    assert abs(diagnostics["terminal_soc_kwh"] - 150) < 1e-6


def test_optimised_objective_is_no_worse_than_baseline():
    profile = make_profile()
    battery = BatteryConfig(
        capacity_kwh=300,
        maximum_charge_kw=100,
        maximum_discharge_kw=100,
        peak_demand_penalty_hkd_per_kw=5,
    )
    optimised, _ = optimise_battery_dispatch(
        profile,
        battery=battery,
    )
    baseline = calculate_no_storage_baseline(profile)

    base_metrics = calculate_scenario_metrics(
        baseline,
        timestep_hours=1,
        degradation_cost_hkd_per_kwh=(
            battery.degradation_cost_hkd_per_kwh
        ),
        peak_demand_penalty_hkd_per_kw=(
            battery.peak_demand_penalty_hkd_per_kw
        ),
    )
    optimised_metrics = calculate_scenario_metrics(
        optimised,
        timestep_hours=1,
        degradation_cost_hkd_per_kwh=(
            battery.degradation_cost_hkd_per_kwh
        ),
        peak_demand_penalty_hkd_per_kw=(
            battery.peak_demand_penalty_hkd_per_kw
        ),
    )
    assert (
        optimised_metrics["objective_cost_hkd"]
        <= base_metrics["objective_cost_hkd"] + 1e-6
    )
