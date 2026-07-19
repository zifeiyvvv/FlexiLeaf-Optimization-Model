"""Generate transparent end-use load profiles calibrated to blueprint EUI."""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd


def _occupancy_profile(
    building_type: str,
    hour: np.ndarray,
    is_weekend: np.ndarray,
) -> np.ndarray:
    hour = hour.astype(float)
    if building_type == "education":
        weekday = np.where(
            (hour >= 8) & (hour < 19),
            np.sin(np.pi * (hour - 8) / 11) * 0.85 + 0.15,
            0.05,
        )
        weekend = np.where(
            (hour >= 9) & (hour < 17),
            0.20 + 0.25 * np.sin(np.pi * (hour - 9) / 8),
            0.04,
        )
    elif building_type == "residential":
        weekday = (
            0.28
            + 0.48 * np.exp(-((hour - 7.0) / 2.0) ** 2)
            + 0.72 * np.exp(-((hour - 20.0) / 3.0) ** 2)
        )
        weekend = (
            0.38
            + 0.40 * np.exp(-((hour - 9.0) / 3.0) ** 2)
            + 0.55 * np.exp(-((hour - 20.0) / 3.2) ** 2)
        )
    else:
        weekday = np.where(
            (hour >= 7) & (hour < 22),
            0.25 + 0.75 * np.sin(np.pi * (hour - 7) / 15),
            0.10,
        )
        weekend = np.where(
            (hour >= 8) & (hour < 23),
            0.25 + 0.65 * np.sin(np.pi * (hour - 8) / 15),
            0.10,
        )
    return np.where(is_weekend, weekend, weekday)


def _scale_to_energy(
    raw: np.ndarray,
    annual_energy_kwh: float,
) -> np.ndarray:
    raw = np.maximum(np.asarray(raw, dtype=float), 1e-9)
    return raw * (annual_energy_kwh / raw.sum())


def build_annual_load(
    weather: pd.DataFrame,
    *,
    assets: list[dict[str, Any]],
    annual_ev_charging_energy_kwh: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    result = weather[
        [
            "timestamp",
            "date",
            "hour",
            "month",
            "weekday",
            "is_weekend",
            "temperature_c",
            "relative_humidity_percent",
            "global_horizontal_irradiance_wm2",
        ]
    ].copy()

    hour = result["hour"].to_numpy(dtype=float)
    is_weekend = result["is_weekend"].to_numpy(dtype=bool)
    temperature = result["temperature_c"].to_numpy(dtype=float)
    irradiance = result[
        "global_horizontal_irradiance_wm2"
    ].to_numpy(dtype=float)
    darkness = 1.0 - np.clip(irradiance / 650.0, 0.0, 1.0)

    parameter_rows = []
    all_component_columns = []

    for asset in assets:
        asset_id = asset["asset_id"]
        building_type = asset["building_type"]
        occupancy = _occupancy_profile(
            building_type,
            hour,
            is_weekend,
        )
        annual_energy = (
            float(asset["gross_floor_area_m2"])
            * float(asset["annual_eui_kwh_m2"])
        )
        shares = asset["end_use_share"]

        cooling_degree = np.maximum(temperature - 20.0, 0.0)
        heating_degree = np.maximum(16.0 - temperature, 0.0)
        hvac_raw = (
            0.10
            + occupancy
            * (
                0.25
                + (cooling_degree / 8.0) ** 1.25
                + 0.20 * (heating_degree / 6.0)
            )
        )
        lighting_raw = (
            0.12 + occupancy * (0.55 + 0.55 * darkness)
        )
        equipment_raw = 0.20 + occupancy * 0.95
        lifts_raw = 0.15 + occupancy * 0.65
        other_raw = np.ones(len(result))

        raw_map = {
            "hvac": hvac_raw,
            "lighting": lighting_raw,
            "equipment": equipment_raw,
            "lifts_pumps": lifts_raw,
            "other": other_raw,
        }
        asset_columns = []
        for end_use, raw in raw_map.items():
            target = annual_energy * float(shares[end_use])
            column = f"{asset_id}_{end_use}_load_kw"
            result[column] = _scale_to_energy(raw, target)
            asset_columns.append(column)
            all_component_columns.append(column)

        asset_total_column = f"{asset_id}_total_load_kw"
        result[asset_total_column] = result[asset_columns].sum(axis=1)
        parameter_rows.append(
            {
                "asset_id": asset_id,
                "asset_name": asset["asset_name"],
                "building_type": building_type,
                "gross_floor_area_m2": asset["gross_floor_area_m2"],
                "annual_eui_kwh_m2": asset["annual_eui_kwh_m2"],
                "annual_target_energy_kwh": annual_energy,
                "simulated_annual_energy_kwh": float(
                    result[asset_total_column].sum()
                ),
                "source_type": "blueprint_design_and_engineering_assumption",
            }
        )

    # Aggregated EV charging demand: campus daytime plus residential evening.
    weekday = (~is_weekend).astype(float)
    weekend = is_weekend.astype(float)
    ev_raw = (
        weekday
        * (
            0.15
            + 1.00 * np.exp(-((hour - 10.0) / 2.3) ** 2)
            + 0.45 * np.exp(-((hour - 15.0) / 2.0) ** 2)
            + 0.40 * np.exp(-((hour - 20.0) / 2.4) ** 2)
        )
        + weekend
        * (
            0.12
            + 0.35 * np.exp(-((hour - 12.0) / 3.0) ** 2)
            + 0.45 * np.exp(-((hour - 20.0) / 2.6) ** 2)
        )
    )
    result["ev_charging_load_kw"] = _scale_to_energy(
        ev_raw,
        annual_ev_charging_energy_kwh,
    )
    all_component_columns.append("ev_charging_load_kw")
    result["total_load_kw"] = result[all_component_columns].sum(axis=1)

    parameter_rows.append(
        {
            "asset_id": "ev_charging",
            "asset_name": "Aggregated EV charging",
            "building_type": "transport",
            "gross_floor_area_m2": 0,
            "annual_eui_kwh_m2": 0,
            "annual_target_energy_kwh": annual_ev_charging_energy_kwh,
            "simulated_annual_energy_kwh": float(
                result["ev_charging_load_kw"].sum()
            ),
            "source_type": "blueprint_design_and_engineering_assumption",
        }
    )
    return result, pd.DataFrame(parameter_rows)
