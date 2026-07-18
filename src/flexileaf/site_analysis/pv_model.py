"""Transparent planning-level photovoltaic power estimator."""

from __future__ import annotations

from typing import Any

import math


def _validate_fraction(name: str, value: float) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be between 0 and 1")


def estimate_surface_pv_power(
    *,
    usable_area_m2: float,
    irradiance_wm2: float,
    module_efficiency: float,
    performance_ratio: float,
    orientation_factor: float,
) -> dict[str, float]:
    """Estimate current DC-equivalent PV power from horizontal irradiation.

    The estimator is deliberately transparent and suitable for early-stage
    scenario comparison. The orientation factor is a user-visible correction
    and does not replace a detailed irradiance transposition or shading model.
    """
    if usable_area_m2 < 0:
        raise ValueError("usable_area_m2 cannot be negative")
    if irradiance_wm2 < 0:
        raise ValueError("irradiance_wm2 cannot be negative")
    _validate_fraction("module_efficiency", module_efficiency)
    _validate_fraction("performance_ratio", performance_ratio)
    _validate_fraction("orientation_factor", orientation_factor)

    dc_capacity_kwp = usable_area_m2 * module_efficiency
    estimated_power_kw = (
        usable_area_m2
        * irradiance_wm2
        * module_efficiency
        * performance_ratio
        * orientation_factor
        / 1000.0
    )
    estimated_power_kw = min(
        max(estimated_power_kw, 0.0),
        dc_capacity_kwp,
    )

    return {
        "usable_area_m2": float(usable_area_m2),
        "dc_capacity_kwp": float(dc_capacity_kwp),
        "estimated_current_power_kw": float(estimated_power_kw),
    }


def estimate_building_pv(
    building: dict[str, Any],
    *,
    irradiance_wm2: float,
    module_efficiency: float = 0.20,
    performance_ratio: float = 0.82,
    roof_orientation_factor: float = 0.90,
    facade_orientation_factor: float = 0.55,
) -> dict[str, float]:
    roof = estimate_surface_pv_power(
        usable_area_m2=float(
            building.get("estimated_roof_usable_m2", 0.0)
        ),
        irradiance_wm2=irradiance_wm2,
        module_efficiency=module_efficiency,
        performance_ratio=performance_ratio,
        orientation_factor=roof_orientation_factor,
    )
    facade = estimate_surface_pv_power(
        usable_area_m2=float(
            building.get("estimated_facade_usable_m2", 0.0)
        ),
        irradiance_wm2=irradiance_wm2,
        module_efficiency=module_efficiency,
        performance_ratio=performance_ratio,
        orientation_factor=facade_orientation_factor,
    )

    return {
        "solar_irradiance_wm2": float(irradiance_wm2),
        "roof_dc_capacity_kwp": roof["dc_capacity_kwp"],
        "facade_dc_capacity_kwp": facade["dc_capacity_kwp"],
        "total_dc_capacity_kwp": (
            roof["dc_capacity_kwp"] + facade["dc_capacity_kwp"]
        ),
        "estimated_roof_current_power_kw": (
            roof["estimated_current_power_kw"]
        ),
        "estimated_facade_current_power_kw": (
            facade["estimated_current_power_kw"]
        ),
        "estimated_total_current_power_kw": (
            roof["estimated_current_power_kw"]
            + facade["estimated_current_power_kw"]
        ),
    }
