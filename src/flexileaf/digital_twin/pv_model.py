"""Annual roof, facade and public-infrastructure photovoltaic model."""

from __future__ import annotations

from typing import Any
import math

import numpy as np
import pandas as pd


ORIENTATION_AZIMUTH_DEG = {
    "north": 0.0,
    "east": 90.0,
    "south": 180.0,
    "west": 270.0,
}


def _plane_of_array(
    *,
    ghi: np.ndarray,
    dhi: np.ndarray,
    dni: np.ndarray,
    sin_elevation: np.ndarray,
    solar_azimuth_deg: np.ndarray,
    tilt_deg: float,
    surface_azimuth_deg: float,
    albedo: float = 0.20,
) -> np.ndarray:
    elevation = np.arcsin(np.clip(sin_elevation, 0.0, 1.0))
    zenith = np.pi / 2.0 - elevation
    beta = math.radians(tilt_deg)
    gamma = np.radians(surface_azimuth_deg)
    solar_azimuth = np.radians(solar_azimuth_deg)

    cos_incidence = (
        np.cos(zenith) * math.cos(beta)
        + np.sin(zenith)
        * math.sin(beta)
        * np.cos(solar_azimuth - gamma)
    )
    beam = dni * np.maximum(cos_incidence, 0.0)
    diffuse = dhi * (1.0 + math.cos(beta)) / 2.0
    reflected = ghi * albedo * (1.0 - math.cos(beta)) / 2.0
    poa = beam + diffuse + reflected
    poa[sin_elevation <= 0] = 0.0
    return np.maximum(poa, 0.0)


def _pv_power(
    *,
    area_m2: float,
    efficiency: float,
    poa_wm2: np.ndarray,
    air_temperature_c: np.ndarray,
    performance_ratio: float,
    availability: float,
    temperature_coefficient_per_c: float = -0.0035,
    noct_c: float = 45.0,
) -> tuple[np.ndarray, float]:
    capacity_kwp = area_m2 * efficiency
    cell_temperature = (
        air_temperature_c + (noct_c - 20.0) / 800.0 * poa_wm2
    )
    temperature_factor = np.clip(
        1.0
        + temperature_coefficient_per_c
        * (cell_temperature - 25.0),
        0.70,
        1.08,
    )
    power = (
        capacity_kwp
        * poa_wm2
        / 1000.0
        * performance_ratio
        * availability
        * temperature_factor
    )
    return np.clip(power, 0.0, capacity_kwp), capacity_kwp


def build_annual_pv(
    weather: pd.DataFrame,
    *,
    assets: list[dict[str, Any]],
    public_infrastructure: dict[str, Any],
    scenario_name: str,
    scenario: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ghi = weather[
        "global_horizontal_irradiance_wm2"
    ].to_numpy(dtype=float)
    dhi = weather[
        "diffuse_horizontal_irradiance_wm2"
    ].to_numpy(dtype=float)
    dni = weather[
        "direct_normal_irradiance_wm2"
    ].to_numpy(dtype=float)
    sin_elevation = weather["solar_elevation_sine"].to_numpy(dtype=float)
    solar_azimuth = weather["solar_azimuth_deg"].to_numpy(dtype=float)
    temperature = weather["temperature_c"].to_numpy(dtype=float)

    result = weather[["timestamp", "date", "hour", "month"]].copy()
    result["scenario"] = scenario_name
    result["roof_pv_kw"] = 0.0
    result["facade_pv_kw"] = 0.0
    result["public_pv_kw"] = 0.0
    parameter_rows = []

    roof_poa = _plane_of_array(
        ghi=ghi,
        dhi=dhi,
        dni=dni,
        sin_elevation=sin_elevation,
        solar_azimuth_deg=solar_azimuth,
        tilt_deg=10.0,
        surface_azimuth_deg=180.0,
    )
    public_poa = _plane_of_array(
        ghi=ghi,
        dhi=dhi,
        dni=dni,
        sin_elevation=sin_elevation,
        solar_azimuth_deg=solar_azimuth,
        tilt_deg=5.0,
        surface_azimuth_deg=180.0,
    )

    for asset in assets:
        roof_area = (
            float(asset["roof_usable_area_m2"])
            * float(scenario["roof_area_multiplier"])
        )
        roof_power, roof_capacity = _pv_power(
            area_m2=roof_area,
            efficiency=float(scenario["module_efficiency"]),
            poa_wm2=roof_poa,
            air_temperature_c=temperature,
            performance_ratio=float(
                scenario["roof_performance_ratio"]
            ),
            availability=float(scenario["availability"]),
        )
        result["roof_pv_kw"] += roof_power
        parameter_rows.append(
            {
                "scenario": scenario_name,
                "asset_id": asset["asset_id"],
                "surface": "roof",
                "usable_area_m2": roof_area,
                "module_efficiency": scenario["module_efficiency"],
                "capacity_kwp": roof_capacity,
                "performance_ratio": scenario[
                    "roof_performance_ratio"
                ],
                "source_type": "blueprint_design_and_engineering_assumption",
            }
        )

        for orientation, share in asset[
            "facade_orientation_share"
        ].items():
            facade_area = (
                float(asset["facade_usable_area_m2"])
                * float(share)
                * float(scenario["facade_area_multiplier"])
            )
            facade_poa = _plane_of_array(
                ghi=ghi,
                dhi=dhi,
                dni=dni,
                sin_elevation=sin_elevation,
                solar_azimuth_deg=solar_azimuth,
                tilt_deg=90.0,
                surface_azimuth_deg=ORIENTATION_AZIMUTH_DEG[
                    orientation
                ],
            )
            facade_power, facade_capacity = _pv_power(
                area_m2=facade_area,
                efficiency=float(scenario["module_efficiency"]),
                poa_wm2=facade_poa,
                air_temperature_c=temperature,
                performance_ratio=float(
                    scenario["facade_performance_ratio"]
                ),
                availability=float(scenario["availability"]),
            )
            result["facade_pv_kw"] += facade_power
            parameter_rows.append(
                {
                    "scenario": scenario_name,
                    "asset_id": asset["asset_id"],
                    "surface": f"facade_{orientation}",
                    "usable_area_m2": facade_area,
                    "module_efficiency": scenario[
                        "module_efficiency"
                    ],
                    "capacity_kwp": facade_capacity,
                    "performance_ratio": scenario[
                        "facade_performance_ratio"
                    ],
                    "source_type": "blueprint_design_and_engineering_assumption",
                }
            )

    public_area = (
        float(public_infrastructure["usable_pv_area_m2"])
        * float(scenario["public_area_multiplier"])
    )
    public_power, public_capacity = _pv_power(
        area_m2=public_area,
        efficiency=float(scenario["module_efficiency"]),
        poa_wm2=public_poa,
        air_temperature_c=temperature,
        performance_ratio=float(
            scenario["public_performance_ratio"]
        ),
        availability=float(scenario["availability"]),
    )
    result["public_pv_kw"] = public_power
    parameter_rows.append(
        {
            "scenario": scenario_name,
            "asset_id": "public_infrastructure",
            "surface": "canopy_and_footbridge",
            "usable_area_m2": public_area,
            "module_efficiency": scenario["module_efficiency"],
            "capacity_kwp": public_capacity,
            "performance_ratio": scenario[
                "public_performance_ratio"
            ],
            "source_type": "blueprint_design_and_engineering_assumption",
        }
    )

    result["flexileaf_pv_kw"] = (
        result["facade_pv_kw"] + result["public_pv_kw"]
    )
    result["total_pv_kw"] = (
        result["roof_pv_kw"]
        + result["facade_pv_kw"]
        + result["public_pv_kw"]
    )
    return result, pd.DataFrame(parameter_rows)
