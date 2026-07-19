"""Mixed-integer battery dispatch optimisation using SciPy HiGHS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix


@dataclass(frozen=True)
class BatteryConfig:
    capacity_kwh: float
    initial_soc_fraction: float = 0.5
    minimum_soc_fraction: float = 0.1
    maximum_soc_fraction: float = 0.9
    maximum_charge_kw: float = 150.0
    maximum_discharge_kw: float = 150.0
    charging_efficiency: float = 0.95
    discharging_efficiency: float = 0.95
    degradation_cost_hkd_per_kwh: float = 0.05
    peak_demand_penalty_hkd_per_kw: float = 4.0
    enforce_terminal_soc: bool = True

    def validate(self) -> None:
        if self.capacity_kwh <= 0:
            raise ValueError("battery capacity must be positive")
        fractions = (
            self.initial_soc_fraction,
            self.minimum_soc_fraction,
            self.maximum_soc_fraction,
        )
        if any(not 0 <= value <= 1 for value in fractions):
            raise ValueError("SOC fractions must be between zero and one")
        if not (
            self.minimum_soc_fraction
            <= self.initial_soc_fraction
            <= self.maximum_soc_fraction
        ):
            raise ValueError("initial SOC must be within SOC limits")
        if self.maximum_charge_kw <= 0 or self.maximum_discharge_kw <= 0:
            raise ValueError("charge/discharge power must be positive")
        if not 0 < self.charging_efficiency <= 1:
            raise ValueError("charging efficiency must be in (0, 1]")
        if not 0 < self.discharging_efficiency <= 1:
            raise ValueError("discharging efficiency must be in (0, 1]")
        if self.degradation_cost_hkd_per_kwh < 0:
            raise ValueError("degradation cost cannot be negative")
        if self.peak_demand_penalty_hkd_per_kw < 0:
            raise ValueError("peak penalty cannot be negative")


def optimise_battery_dispatch(
    profile: pd.DataFrame,
    *,
    battery: BatteryConfig,
    timestep_hours: float = 1.0,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Optimise grid, battery and peak demand with binary charge mode."""
    battery.validate()
    if timestep_hours <= 0:
        raise ValueError("timestep_hours must be positive")

    required = {
        "load_kw",
        "pv_generation_kw",
        "buy_tariff_hkd_per_kwh",
        "export_tariff_hkd_per_kwh",
    }
    missing = required.difference(profile.columns)
    if missing:
        raise ValueError(
            f"Energy profile is missing columns: {sorted(missing)}"
        )

    load = profile["load_kw"].to_numpy(dtype=float)
    pv = profile["pv_generation_kw"].to_numpy(dtype=float)
    buy = profile["buy_tariff_hkd_per_kwh"].to_numpy(dtype=float)
    sell = profile["export_tariff_hkd_per_kwh"].to_numpy(dtype=float)
    if any(array.shape != load.shape for array in (pv, buy, sell)):
        raise ValueError("Energy-profile arrays must have equal lengths")
    if np.any(load < 0) or np.any(pv < 0):
        raise ValueError("Load and PV generation cannot be negative")

    interval_count = len(profile)
    if interval_count == 0:
        raise ValueError("Energy profile cannot be empty")

    offset_import = 0
    offset_export = offset_import + interval_count
    offset_charge = offset_export + interval_count
    offset_discharge = offset_charge + interval_count
    offset_soc = offset_discharge + interval_count
    offset_mode = offset_soc + interval_count + 1
    index_peak = offset_mode + interval_count
    variable_count = index_peak + 1

    objective = np.zeros(variable_count, dtype=float)
    objective[
        offset_import : offset_import + interval_count
    ] = buy * timestep_hours
    objective[
        offset_export : offset_export + interval_count
    ] = -sell * timestep_hours
    cycle_cost = (
        battery.degradation_cost_hkd_per_kwh * timestep_hours
    )
    objective[
        offset_charge : offset_charge + interval_count
    ] = cycle_cost
    objective[
        offset_discharge : offset_discharge + interval_count
    ] = cycle_cost
    objective[index_peak] = battery.peak_demand_penalty_hkd_per_kw

    lower = np.zeros(variable_count, dtype=float)
    upper = np.full(variable_count, np.inf, dtype=float)

    lower[offset_charge : offset_charge + interval_count] = 0.0
    upper[
        offset_charge : offset_charge + interval_count
    ] = battery.maximum_charge_kw
    lower[offset_discharge : offset_discharge + interval_count] = 0.0
    upper[
        offset_discharge : offset_discharge + interval_count
    ] = battery.maximum_discharge_kw

    minimum_soc = (
        battery.capacity_kwh * battery.minimum_soc_fraction
    )
    maximum_soc = (
        battery.capacity_kwh * battery.maximum_soc_fraction
    )
    initial_soc = (
        battery.capacity_kwh * battery.initial_soc_fraction
    )
    lower[offset_soc : offset_soc + interval_count + 1] = minimum_soc
    upper[offset_soc : offset_soc + interval_count + 1] = maximum_soc
    lower[offset_soc] = initial_soc
    upper[offset_soc] = initial_soc
    if battery.enforce_terminal_soc:
        lower[offset_soc + interval_count] = initial_soc
        upper[offset_soc + interval_count] = initial_soc

    lower[offset_mode : offset_mode + interval_count] = 0.0
    upper[offset_mode : offset_mode + interval_count] = 1.0
    lower[index_peak] = 0.0

    integrality = np.zeros(variable_count, dtype=int)
    integrality[offset_mode : offset_mode + interval_count] = 1

    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    constraint_lower: list[float] = []
    constraint_upper: list[float] = []
    row_index = 0

    def add(
        coefficients: dict[int, float],
        lower_bound: float,
        upper_bound: float,
    ) -> None:
        nonlocal row_index
        for column, value in coefficients.items():
            rows.append(row_index)
            columns.append(column)
            values.append(float(value))
        constraint_lower.append(float(lower_bound))
        constraint_upper.append(float(upper_bound))
        row_index += 1

    for t in range(interval_count):
        # Grid balance:
        # import - export - charge + discharge = load - PV
        add(
            {
                offset_import + t: 1.0,
                offset_export + t: -1.0,
                offset_charge + t: -1.0,
                offset_discharge + t: 1.0,
            },
            load[t] - pv[t],
            load[t] - pv[t],
        )

        # SOC transition.
        add(
            {
                offset_soc + t + 1: 1.0,
                offset_soc + t: -1.0,
                offset_charge + t: (
                    -battery.charging_efficiency * timestep_hours
                ),
                offset_discharge + t: (
                    timestep_hours / battery.discharging_efficiency
                ),
            },
            0.0,
            0.0,
        )

        # Binary mode: mode=1 allows charge; mode=0 allows discharge.
        add(
            {
                offset_charge + t: 1.0,
                offset_mode + t: -battery.maximum_charge_kw,
            },
            -np.inf,
            0.0,
        )
        add(
            {
                offset_discharge + t: 1.0,
                offset_mode + t: battery.maximum_discharge_kw,
            },
            -np.inf,
            battery.maximum_discharge_kw,
        )

        # Peak grid import.
        add(
            {
                offset_import + t: 1.0,
                index_peak: -1.0,
            },
            -np.inf,
            0.0,
        )

    matrix = coo_matrix(
        (values, (rows, columns)),
        shape=(row_index, variable_count),
    ).tocsr()
    constraints = LinearConstraint(
        matrix,
        np.asarray(constraint_lower),
        np.asarray(constraint_upper),
    )

    result = milp(
        c=objective,
        integrality=integrality,
        bounds=Bounds(lower, upper),
        constraints=constraints,
        options={"time_limit": 30.0, "mip_rel_gap": 1e-7},
    )
    if not result.success or result.x is None:
        raise RuntimeError(
            "Battery optimisation failed. "
            f"Status={result.status}; message={result.message}"
        )

    solution = result.x
    output = profile.copy()
    output["grid_import_kw"] = solution[
        offset_import : offset_import + interval_count
    ]
    output["grid_export_kw"] = solution[
        offset_export : offset_export + interval_count
    ]
    output["battery_charge_kw"] = solution[
        offset_charge : offset_charge + interval_count
    ]
    output["battery_discharge_kw"] = solution[
        offset_discharge : offset_discharge + interval_count
    ]
    output["battery_soc_kwh"] = solution[
        offset_soc : offset_soc + interval_count
    ]
    output["battery_mode"] = np.rint(
        solution[offset_mode : offset_mode + interval_count]
    ).astype(int)

    balance_error = (
        output["grid_import_kw"]
        - output["grid_export_kw"]
        - output["battery_charge_kw"]
        + output["battery_discharge_kw"]
        - (output["load_kw"] - output["pv_generation_kw"])
    )
    simultaneous = np.minimum(
        output["battery_charge_kw"],
        output["battery_discharge_kw"],
    )

    diagnostics = {
        "solver": "scipy.optimize.milp / HiGHS",
        "solver_status": int(result.status),
        "solver_message": str(result.message),
        "objective_hkd": float(result.fun),
        "peak_grid_import_kw": float(solution[index_peak]),
        "maximum_balance_error_kw": float(
            np.max(np.abs(balance_error))
        ),
        "maximum_simultaneous_charge_discharge_kw": float(
            np.max(simultaneous)
        ),
        "terminal_soc_kwh": float(
            solution[offset_soc + interval_count]
        ),
        "mip_gap": (
            float(result.mip_gap)
            if getattr(result, "mip_gap", None) is not None
            else None
        ),
    }
    return output, diagnostics
