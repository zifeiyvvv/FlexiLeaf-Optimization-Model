"""Transparent 24-hour load, solar and tariff profile generators."""

from __future__ import annotations

from typing import Any

import math
import numpy as np
import pandas as pd


_LOAD_SHAPES = {
    "education": [
        0.22, 0.20, 0.19, 0.18, 0.18, 0.20,
        0.27, 0.45, 0.72, 0.90, 0.97, 1.00,
        0.96, 0.93, 0.95, 0.91, 0.83, 0.69,
        0.52, 0.41, 0.34, 0.29, 0.26, 0.23,
    ],
    "office": [
        0.20, 0.18, 0.17, 0.16, 0.16, 0.18,
        0.24, 0.39, 0.66, 0.88, 0.97, 1.00,
        0.96, 0.94, 0.97, 0.95, 0.88, 0.74,
        0.55, 0.40, 0.32, 0.27, 0.24, 0.21,
    ],
    "residential": [
        0.48, 0.42, 0.38, 0.35, 0.34, 0.38,
        0.53, 0.70, 0.66, 0.52, 0.46, 0.43,
        0.45, 0.47, 0.50, 0.57, 0.68, 0.82,
        0.96, 1.00, 0.94, 0.83, 0.68, 0.56,
    ],
    "mixed_use": [
        0.36, 0.32, 0.29, 0.27, 0.27, 0.30,
        0.39, 0.57, 0.72, 0.85, 0.91, 0.94,
        0.92, 0.90, 0.91, 0.90, 0.88, 0.86,
        0.88, 1.00, 0.95, 0.80, 0.63, 0.47,
    ],
}


def generate_load_profile(
    *,
    archetype: str,
    peak_load_kw: float,
) -> np.ndarray:
    archetype = archetype.lower().strip()
    if archetype not in _LOAD_SHAPES:
        raise ValueError(
            "archetype must be one of: "
            + ", ".join(sorted(_LOAD_SHAPES))
        )
    if peak_load_kw <= 0:
        raise ValueError("peak_load_kw must be positive")

    shape = np.asarray(_LOAD_SHAPES[archetype], dtype=float)
    return shape / shape.max() * float(peak_load_kw)


def generate_solar_irradiance_profile(
    *,
    daily_solar_mj_m2: float,
    sunrise_hour: float = 6.0,
    sunset_hour: float = 18.5,
    shape_exponent: float = 1.45,
    timestep_hours: float = 1.0,
) -> np.ndarray:
    """Disaggregate daily irradiation into a transparent daylight curve.

    The output is average irradiance in W/m² for each interval. The integrated
    profile exactly equals the requested daily total, subject to floating-point
    precision.
    """
    if daily_solar_mj_m2 < 0:
        raise ValueError("daily_solar_mj_m2 cannot be negative")
    if not 0 <= sunrise_hour < sunset_hour <= 24:
        raise ValueError("sunrise/sunset must satisfy 0 <= sunrise < sunset <= 24")
    if shape_exponent <= 0:
        raise ValueError("shape_exponent must be positive")
    if timestep_hours <= 0 or 24 % timestep_hours != 0:
        raise ValueError("timestep_hours must divide 24 hours exactly")

    interval_count = int(round(24 / timestep_hours))
    centres = (
        np.arange(interval_count, dtype=float) * timestep_hours
        + timestep_hours / 2
    )
    weights = np.zeros(interval_count, dtype=float)
    daylight = (centres > sunrise_hour) & (centres < sunset_hour)
    phase = (
        (centres[daylight] - sunrise_hour)
        / (sunset_hour - sunrise_hour)
    )
    weights[daylight] = np.sin(np.pi * phase) ** shape_exponent

    if daily_solar_mj_m2 == 0:
        return weights
    if weights.sum() <= 0:
        raise ValueError("No daylight interval exists for this configuration.")

    daily_solar_kwh_m2 = float(daily_solar_mj_m2) / 3.6
    interval_energy_kwh_m2 = (
        daily_solar_kwh_m2 * weights / weights.sum()
    )
    irradiance_kw_m2 = interval_energy_kwh_m2 / timestep_hours
    return irradiance_kw_m2 * 1000.0


def generate_tariff_profile(
    *,
    off_peak_hkd_per_kwh: float,
    shoulder_hkd_per_kwh: float,
    peak_hkd_per_kwh: float,
    timestep_hours: float = 1.0,
) -> np.ndarray:
    """Create an illustrative TOU tariff profile.

    The profile is a user-configured scenario and is not presented as an
    official utility tariff.
    """
    values = [
        off_peak_hkd_per_kwh,
        shoulder_hkd_per_kwh,
        peak_hkd_per_kwh,
    ]
    if any(value < 0 for value in values):
        raise ValueError("Tariff values cannot be negative")
    if timestep_hours <= 0 or 24 % timestep_hours != 0:
        raise ValueError("timestep_hours must divide 24 hours exactly")

    interval_count = int(round(24 / timestep_hours))
    centres = (
        np.arange(interval_count, dtype=float) * timestep_hours
        + timestep_hours / 2
    )
    tariff = np.full(interval_count, shoulder_hkd_per_kwh, dtype=float)
    tariff[(centres < 8) | (centres >= 23)] = off_peak_hkd_per_kwh
    tariff[(centres >= 18) & (centres < 22)] = peak_hkd_per_kwh
    return tariff


def build_hourly_energy_profile(
    *,
    building: dict[str, Any],
    site_config: dict[str, Any],
    load_archetype: str,
    peak_load_kw: float,
    daily_solar_mj_m2: float,
    sunrise_hour: float,
    sunset_hour: float,
    solar_shape_exponent: float,
    off_peak_tariff_hkd_per_kwh: float,
    shoulder_tariff_hkd_per_kwh: float,
    peak_tariff_hkd_per_kwh: float,
    export_tariff_hkd_per_kwh: float,
    carbon_intensity_kg_per_kwh: float,
    timestep_hours: float = 1.0,
) -> pd.DataFrame:
    load_kw = generate_load_profile(
        archetype=load_archetype,
        peak_load_kw=peak_load_kw,
    )
    irradiance_wm2 = generate_solar_irradiance_profile(
        daily_solar_mj_m2=daily_solar_mj_m2,
        sunrise_hour=sunrise_hour,
        sunset_hour=sunset_hour,
        shape_exponent=solar_shape_exponent,
        timestep_hours=timestep_hours,
    )
    buy_tariff = generate_tariff_profile(
        off_peak_hkd_per_kwh=off_peak_tariff_hkd_per_kwh,
        shoulder_hkd_per_kwh=shoulder_tariff_hkd_per_kwh,
        peak_hkd_per_kwh=peak_tariff_hkd_per_kwh,
        timestep_hours=timestep_hours,
    )

    roof_capacity_kwp = float(building.get("roof_dc_capacity_kwp", 0.0))
    facade_capacity_kwp = float(
        building.get("facade_dc_capacity_kwp", 0.0)
    )
    performance_ratio = float(site_config.get("performance_ratio", 0.82))
    roof_orientation = float(
        site_config.get("roof_orientation_factor", 0.90)
    )
    facade_orientation = float(
        site_config.get("facade_orientation_factor", 0.55)
    )

    roof_pv_kw = (
        roof_capacity_kwp
        * irradiance_wm2
        / 1000.0
        * performance_ratio
        * roof_orientation
    )
    facade_pv_kw = (
        facade_capacity_kwp
        * irradiance_wm2
        / 1000.0
        * performance_ratio
        * facade_orientation
    )
    pv_kw = roof_pv_kw + facade_pv_kw

    count = len(load_kw)
    interval_start = np.arange(count, dtype=float) * timestep_hours
    timestamp = pd.Timestamp("2026-06-21") + pd.to_timedelta(
        interval_start,
        unit="h",
    )

    return pd.DataFrame(
        {
            "timestamp": timestamp,
            "hour": interval_start,
            "load_kw": load_kw,
            "solar_irradiance_wm2": irradiance_wm2,
            "roof_pv_kw": roof_pv_kw,
            "facade_pv_kw": facade_pv_kw,
            "pv_generation_kw": pv_kw,
            "buy_tariff_hkd_per_kwh": buy_tariff,
            "export_tariff_hkd_per_kwh": float(
                export_tariff_hkd_per_kwh
            ),
            "carbon_intensity_kg_per_kwh": float(
                carbon_intensity_kg_per_kwh
            ),
        }
    )
