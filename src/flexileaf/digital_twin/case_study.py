"""Generate the fixed FlexiLeaf design-basis digital-twin case study."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import shutil

import numpy as np
import pandas as pd

from .annual_dispatch import compare_to_grid, run_configuration
from .load_model import build_annual_load
from .pv_model import build_annual_pv
from .weather import build_hourly_weather, combine_daily_weather


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assumption_register(
    config: dict[str, Any],
) -> pd.DataFrame:
    rows = [
        {
            "parameter": "2025 daily global solar radiation",
            "value": "365 daily observations",
            "unit": "MJ/m²/day",
            "type": "official_open_data",
            "source": (
                "https://data.weather.gov.hk/weatherAPI/cis/csvfile/"
                "KP/2025/daily_KP_GSR_2025.csv"
            ),
            "reason": "Constrains annual solar resource using HKO observations.",
            "uncertainty_range": "official daily values; hourly shape modelled",
            "validation_status": "archived_and_checksum_verified",
        },
        {
            "parameter": "2025 daily mean relative humidity",
            "value": "365 daily observations",
            "unit": "%",
            "type": "official_open_data",
            "source": (
                "https://data.weather.gov.hk/weatherAPI/cis/csvfile/"
                "KP/2025/daily_KP_RH_2025.csv"
            ),
            "reason": "Informs hourly humidity and temperature variation.",
            "uncertainty_range": "official daily values; hourly shape modelled",
            "validation_status": "archived_and_checksum_verified",
        },
        {
            "parameter": "2025 daily bright sunshine",
            "value": "365 daily observations",
            "unit": "hours/day",
            "type": "official_open_data",
            "source": (
                "https://data.weather.gov.hk/weatherAPI/cis/csvfile/"
                "KP/2025/daily_KP_SUN_2025.csv"
            ),
            "reason": "Controls hourly cloud-shape modulation.",
            "uncertainty_range": "official daily values; hourly cloud pattern modelled",
            "validation_status": "archived_and_checksum_verified",
        },
        {
            "parameter": "2025 annual mean temperature",
            "value": config["annual_mean_temperature_target_c"],
            "unit": "°C",
            "type": "official_annual_statistic_plus_derived_profile",
            "source": "https://www.hko.gov.hk/en/wxinfo/pastwx/2025/ywx2025.htm",
            "reason": "Calibrates the synthetic hourly temperature series.",
            "uncertainty_range": "hourly profile is model-derived",
            "validation_status": "annual_mean_matched",
        },
        {
            "parameter": "Grid carbon intensity",
            "value": config["grid_carbon_intensity_kg_per_kwh"],
            "unit": "kgCO2e/kWh",
            "type": "official_company_statistic",
            "source": (
                "https://www.clp.com.hk/content/dam/clphk/documents/"
                "about-clp-site/media-site/resources-site/publications-site/"
                "2025/CLP-Information-Kit-English.pdf"
            ),
            "reason": "Estimates avoided operational emissions.",
            "uncertainty_range": "reporting-year and supplier specific",
            "validation_status": "source_recorded",
        },
        {
            "parameter": "Electricity tariff",
            "value": json.dumps(config["tariff"]),
            "unit": "HKD/kWh",
            "type": "engineering_assumption",
            "source": "project scenario; not an official customer bill",
            "reason": "Enables transparent cost comparison.",
            "uncertainty_range": "must be replaced for a real customer category",
            "validation_status": "clearly_labelled_assumption",
        },
        {
            "parameter": "V2G resource",
            "value": "aggregate equivalent capacity and power",
            "unit": "kWh and kW",
            "type": "blueprint_design_assumption",
            "source": "FlexiLeaf proposal V2G concept",
            "reason": "Represents participating EV fleet at planning level.",
            "uncertainty_range": "fleet availability and user participation not field-tested",
            "validation_status": "scenario_only",
        },
    ]

    for asset in config["assets"]:
        rows.extend(
            [
                {
                    "parameter": f"{asset['asset_id']} gross floor area",
                    "value": asset["gross_floor_area_m2"],
                    "unit": "m²",
                    "type": "blueprint_design",
                    "source": "FlexiLeaf planned demonstration-site blueprint",
                    "reason": "Defines annual load calibration.",
                    "uncertainty_range": "±10% during detailed design",
                    "validation_status": "design_basis",
                },
                {
                    "parameter": f"{asset['asset_id']} roof usable area",
                    "value": asset["roof_usable_area_m2"],
                    "unit": "m²",
                    "type": "blueprint_design",
                    "source": "FlexiLeaf planned demonstration-site blueprint",
                    "reason": "Defines roof PV capacity.",
                    "uncertainty_range": "scenario multipliers applied",
                    "validation_status": "design_basis",
                },
                {
                    "parameter": f"{asset['asset_id']} facade usable area",
                    "value": asset["facade_usable_area_m2"],
                    "unit": "m²",
                    "type": "blueprint_design",
                    "source": "FlexiLeaf planned demonstration-site blueprint",
                    "reason": "Defines flexible facade PV capacity.",
                    "uncertainty_range": "scenario multipliers applied",
                    "validation_status": "design_basis",
                },
                {
                    "parameter": f"{asset['asset_id']} annual EUI",
                    "value": asset["annual_eui_kwh_m2"],
                    "unit": "kWh/m²/year",
                    "type": "engineering_assumption",
                    "source": (
                        "informed by EMSD energy end-use and building "
                        "benchmarking resources; not a measured building value"
                    ),
                    "reason": "Calibrates synthetic annual building demand.",
                    "uncertainty_range": "±15% recommended sensitivity range",
                    "validation_status": "scenario_assumption",
                },
            ]
        )
    return pd.DataFrame(rows)


def generate_design_basis_case(
    *,
    config_path: str | Path,
    source_solar_path: str | Path,
    source_humidity_path: str | Path,
    source_sunshine_path: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    config_path = Path(config_path)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    source_dir = output / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    source_paths = {
        "solar": Path(source_solar_path),
        "humidity": Path(source_humidity_path),
        "sunshine": Path(source_sunshine_path),
    }
    copied_sources = {}
    for key, path in source_paths.items():
        destination = source_dir / path.name
        shutil.copy2(path, destination)
        copied_sources[key] = destination

    source_manifest = {
        key: {
            "file": str(path.relative_to(output)),
            "sha256": _sha256(path),
            "source_type": "official_open_data",
        }
        for key, path in copied_sources.items()
    }
    (output / "source_manifest.json").write_text(
        json.dumps(source_manifest, indent=2),
        encoding="utf-8",
    )
    shutil.copy2(config_path, output / config_path.name)

    daily_weather = combine_daily_weather(
        solar_path=copied_sources["solar"],
        humidity_path=copied_sources["humidity"],
        sunshine_path=copied_sources["sunshine"],
        simulation_year=int(config["simulation_year"]),
    )
    hourly_weather = build_hourly_weather(
        daily_weather,
        latitude=float(config["latitude"]),
        random_seed=int(config["random_seed"]),
        annual_mean_temperature_target_c=float(
            config["annual_mean_temperature_target_c"]
        ),
    )
    load, load_calibration = build_annual_load(
        hourly_weather,
        assets=config["assets"],
        annual_ev_charging_energy_kwh=float(
            config["public_infrastructure"][
                "annual_ev_charging_energy_kwh"
            ]
        ),
    )

    daily_weather.to_csv(
        output / "weather_2025_daily.csv",
        index=False,
        encoding="utf-8-sig",
    )
    hourly_weather.to_csv(
        output / "weather_2025_hourly.csv",
        index=False,
        encoding="utf-8-sig",
    )
    load.to_csv(
        output / "load_2025_hourly.csv",
        index=False,
        encoding="utf-8-sig",
    )
    load_calibration.to_csv(
        output / "load_calibration.csv",
        index=False,
        encoding="utf-8-sig",
    )

    assumptions = _assumption_register(config)
    assumptions.to_csv(
        output / "assumption_register.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pv_parameters = []
    scenario_rows = []
    monthly_rows = []
    design_dispatch_rows = []
    validation_rows = []
    design_full_dispatch = None
    design_full_summary = None

    for scenario_name, scenario in config[
        "performance_scenarios"
    ].items():
        pv, params = build_annual_pv(
            hourly_weather,
            assets=config["assets"],
            public_infrastructure=config["public_infrastructure"],
            scenario_name=scenario_name,
            scenario=scenario,
        )
        pv_parameters.append(params)
        grid_metrics = None

        for configuration in config["system_configurations"]:
            dispatch, metrics = run_configuration(
                load=load,
                pv=pv,
                configuration=configuration,
                scenario=scenario,
                tariff=config["tariff"],
                carbon_intensity_kg_per_kwh=float(
                    config["grid_carbon_intensity_kg_per_kwh"]
                ),
                peak_penalty_hkd_per_kw_day=float(
                    config["peak_penalty_hkd_per_kw_day"]
                ),
                degradation_cost_hkd_per_kwh=float(
                    config["battery_degradation_hkd_per_kwh"]
                ),
            )
            if configuration == "grid_only":
                grid_metrics = metrics
            comparison = compare_to_grid(grid_metrics, metrics)

            scenario_rows.append(
                {
                    "scenario": scenario_name,
                    "configuration": configuration,
                    "annual_load_mwh": (
                        metrics["load_energy_kwh"] / 1000.0
                    ),
                    "annual_pv_generation_mwh": (
                        metrics["pv_generation_kwh"] / 1000.0
                    ),
                    "grid_import_mwh": (
                        metrics["grid_import_kwh"] / 1000.0
                    ),
                    "grid_export_mwh": (
                        metrics["grid_export_kwh"] / 1000.0
                    ),
                    "peak_grid_import_kw": metrics[
                        "peak_grid_import_kw"
                    ],
                    "net_energy_cost_hkd": metrics[
                        "net_energy_cost_hkd"
                    ],
                    "carbon_emissions_tco2e": (
                        metrics["carbon_emissions_kg"] / 1000.0
                    ),
                    "pv_self_consumption_percent": (
                        metrics["pv_self_consumption_fraction"] * 100.0
                    ),
                    "load_self_sufficiency_percent": (
                        metrics["load_self_sufficiency_fraction"] * 100.0
                    ),
                    "battery_capacity_kwh": metrics[
                        "battery_capacity_kwh"
                    ],
                    "battery_power_kw": metrics["battery_power_kw"],
                    **comparison,
                }
            )

            dispatch = dispatch.copy()
            dispatch["scenario"] = scenario_name
            dispatch["configuration"] = configuration
            dispatch["roof_pv_kw"] = pv["roof_pv_kw"].to_numpy()
            dispatch["facade_pv_kw"] = pv[
                "facade_pv_kw"
            ].to_numpy()
            dispatch["public_pv_kw"] = pv[
                "public_pv_kw"
            ].to_numpy()
            dispatch["total_available_pv_kw"] = pv[
                "total_pv_kw"
            ].to_numpy()
            dispatch["total_load_kw"] = load[
                "total_load_kw"
            ].to_numpy()

            monthly = (
                dispatch.groupby("month")
                .agg(
                    load_kwh=("load_kw", "sum"),
                    pv_generation_kwh=("pv_generation_kw", "sum"),
                    grid_import_kwh=("grid_import_kw", "sum"),
                    grid_export_kwh=("grid_export_kw", "sum"),
                    peak_grid_import_kw=("grid_import_kw", "max"),
                    battery_charge_kwh=("battery_charge_kw", "sum"),
                    battery_discharge_kwh=("battery_discharge_kw", "sum"),
                )
                .reset_index()
            )
            monthly["scenario"] = scenario_name
            monthly["configuration"] = configuration
            monthly_rows.append(monthly)

            diagnostics = metrics["solver_diagnostics"]
            validation_rows.append(
                {
                    "scenario": scenario_name,
                    "configuration": configuration,
                    "row_count": len(dispatch),
                    "maximum_balance_error_kw": diagnostics[
                        "maximum_balance_error_kw"
                    ],
                    "maximum_simultaneous_charge_discharge_kw": (
                        diagnostics[
                            "maximum_simultaneous_charge_discharge_kw"
                        ]
                    ),
                    "solver": diagnostics["solver"],
                    "daily_solve_count": diagnostics[
                        "daily_solve_count"
                    ],
                }
            )

            if scenario_name == "design":
                design_dispatch_rows.append(dispatch)
                if configuration == "full_microgrid_v2g":
                    design_full_dispatch = dispatch.copy()
                    design_full_summary = scenario_rows[-1]

    pv_parameter_frame = pd.concat(
        pv_parameters, ignore_index=True
    )
    pv_parameter_frame.to_csv(
        output / "pv_system_parameters.csv",
        index=False,
        encoding="utf-8-sig",
    )

    scenario_comparison = pd.DataFrame(scenario_rows)
    scenario_comparison.to_csv(
        output / "scenario_comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )
    monthly_summary = pd.concat(
        monthly_rows, ignore_index=True
    )
    monthly_summary.to_csv(
        output / "monthly_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    validation_frame = pd.DataFrame(validation_rows)
    validation_frame.to_csv(
        output / "validation_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    design_configurations = pd.concat(
        design_dispatch_rows, ignore_index=True
    )
    design_configurations.to_csv(
        output / "design_configurations_8760h.csv",
        index=False,
        encoding="utf-8-sig",
    )

    if design_full_dispatch is None:
        raise RuntimeError("Design full-microgrid dispatch was not generated.")

    detailed = load.merge(
        hourly_weather[
            [
                "timestamp",
                "global_solar_daily_mj_m2",
                "bright_sunshine_hours",
                "temperature_c",
                "relative_humidity_percent",
                "global_horizontal_irradiance_wm2",
                "diffuse_horizontal_irradiance_wm2",
                "direct_normal_irradiance_wm2",
            ]
        ],
        on="timestamp",
        how="left",
        suffixes=("", "_weather"),
    )
    dispatch_columns = [
        "timestamp",
        "pv_generation_kw",
        "grid_import_kw",
        "grid_export_kw",
        "battery_charge_kw",
        "battery_discharge_kw",
        "battery_soc_kwh",
        "roof_pv_kw",
        "facade_pv_kw",
        "public_pv_kw",
        "total_available_pv_kw",
    ]
    detailed = detailed.merge(
        design_full_dispatch[dispatch_columns],
        on="timestamp",
        how="left",
    )
    detailed["electricity_purchase_cost_hkd"] = (
        design_full_dispatch["grid_import_kw"].to_numpy()
        * design_full_dispatch[
            "buy_tariff_hkd_per_kwh"
        ].to_numpy()
    )
    detailed["export_revenue_hkd"] = (
        design_full_dispatch["grid_export_kw"].to_numpy()
        * design_full_dispatch[
            "export_tariff_hkd_per_kwh"
        ].to_numpy()
    )
    detailed["operational_carbon_kg"] = (
        design_full_dispatch["grid_import_kw"].to_numpy()
        * float(config["grid_carbon_intensity_kg_per_kwh"])
    )
    detailed["data_classification"] = (
        "prospective_design_basis_simulation"
    )
    detailed.to_csv(
        output / "design_case_8760h.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Representative week containing the annual maximum load.
    max_index = int(detailed["total_load_kw"].idxmax())
    centre_date = pd.Timestamp(detailed.loc[max_index, "date"])
    week_start = centre_date - pd.Timedelta(
        days=int(centre_date.dayofweek)
    )
    representative = detailed[
        (pd.to_datetime(detailed["date"]) >= week_start)
        & (
            pd.to_datetime(detailed["date"])
            < week_start + pd.Timedelta(days=7)
        )
    ].copy()
    representative.to_csv(
        output / "representative_peak_week.csv",
        index=False,
        encoding="utf-8-sig",
    )

    blueprint_rows = []
    for asset in config["assets"]:
        blueprint_rows.append(
            {
                "asset_id": asset["asset_id"],
                "asset_name": asset["asset_name"],
                "building_type": asset["building_type"],
                "footprint_m2": asset["footprint_m2"],
                "gross_floor_area_m2": asset[
                    "gross_floor_area_m2"
                ],
                "height_m": asset["height_m"],
                "roof_usable_area_m2": asset[
                    "roof_usable_area_m2"
                ],
                "facade_usable_area_m2": asset[
                    "facade_usable_area_m2"
                ],
                "annual_eui_kwh_m2": asset[
                    "annual_eui_kwh_m2"
                ],
                "annual_load_target_mwh": (
                    asset["gross_floor_area_m2"]
                    * asset["annual_eui_kwh_m2"]
                    / 1000.0
                ),
                "source_type": "blueprint_design",
            }
        )
    blueprint_rows.append(
        {
            "asset_id": "public_infrastructure",
            "asset_name": config["public_infrastructure"][
                "asset_name"
            ],
            "building_type": "public_facility",
            "footprint_m2": 0,
            "gross_floor_area_m2": 0,
            "height_m": 0,
            "roof_usable_area_m2": config[
                "public_infrastructure"
            ]["usable_pv_area_m2"],
            "facade_usable_area_m2": 0,
            "annual_eui_kwh_m2": 0,
            "annual_load_target_mwh": (
                config["public_infrastructure"][
                    "annual_ev_charging_energy_kwh"
                ]
                / 1000.0
            ),
            "source_type": "blueprint_design",
        }
    )
    pd.DataFrame(blueprint_rows).to_csv(
        output / "site_and_system_parameters.csv",
        index=False,
        encoding="utf-8-sig",
    )

    validation = {
        "case_id": config["case_id"],
        "hourly_row_count": int(len(hourly_weather)),
        "daily_weather_row_count": int(len(daily_weather)),
        "scenario_configuration_count": int(
            len(scenario_comparison)
        ),
        "maximum_daily_solar_energy_error_mj_m2": (
            hourly_weather.attrs[
                "maximum_daily_solar_energy_error_mj_m2"
            ]
        ),
        "annual_mean_temperature_c": float(
            hourly_weather["temperature_c"].mean()
        ),
        "annual_load_target_kwh": float(
            load_calibration["annual_target_energy_kwh"].sum()
        ),
        "annual_load_simulated_kwh": float(
            load["total_load_kw"].sum()
        ),
        "annual_load_calibration_error_percent": float(
            (
                load["total_load_kw"].sum()
                - load_calibration[
                    "annual_target_energy_kwh"
                ].sum()
            )
            / load_calibration[
                "annual_target_energy_kwh"
            ].sum()
            * 100.0
        ),
        "maximum_dispatch_balance_error_kw": float(
            validation_frame[
                "maximum_balance_error_kw"
            ].max()
        ),
        "maximum_simultaneous_charge_discharge_kw": float(
            validation_frame[
                "maximum_simultaneous_charge_discharge_kw"
            ].max()
        ),
        "design_full_microgrid_result": design_full_summary,
        "data_status": (
            "Design-basis prospective simulation, not measured operation"
        ),
    }
    (output / "validation_summary.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    case_summary = {
        "case_id": config["case_id"],
        "case_name": config["case_name"],
        "simulation_year": config["simulation_year"],
        "location_status": (
            "planned Hong Kong campus/community demonstration archetype"
        ),
        "data_layers": {
            "official_open_data": [
                "HKO daily global solar radiation",
                "HKO daily relative humidity",
                "HKO daily bright sunshine",
                "HKO 2025 annual mean temperature statistic",
                "CLP 2024 electricity carbon intensity",
            ],
            "blueprint_design": [
                "three planned buildings",
                "roof/facade/public PV area",
                "storage and V2G capacities",
            ],
            "engineering_assumptions": [
                "building EUI",
                "hourly load shapes",
                "daily-to-hourly weather disaggregation",
                "tariff scenario",
            ],
            "simulation_outputs": [
                "8,760-hour energy balance",
                "15 scenario/configuration comparisons",
                "battery dispatch",
                "cost and carbon estimates",
            ],
        },
        "headline_design_result": design_full_summary,
        "mandatory_disclosure": (
            "All results are prospective digital-twin outputs. "
            "They are not field measurements, certified performance, "
            "or guaranteed future savings."
        ),
    }
    (output / "case_study_summary.json").write_text(
        json.dumps(case_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    readme = f"""# FlexiLeaf Design-Basis Digital Twin Case Study

This folder is a prospective simulation of the planned FlexiLeaf campus and
community microgrid. It is **not measured operational data**.

## Fixed evidence layers

- HKO King's Park 2025 daily global solar radiation.
- HKO King's Park 2025 daily relative humidity.
- HKO King's Park 2025 daily bright sunshine.
- Blueprint-defined buildings, PV surfaces, storage and V2G resources.
- Explicit engineering assumptions recorded in `assumption_register.csv`.

## Main files

- `design_case_8760h.csv`: detailed design/full-microgrid hourly case.
- `design_configurations_8760h.csv`: five design configurations.
- `scenario_comparison.csv`: 3 performance scenarios × 5 configurations.
- `monthly_summary.csv`: monthly metrics for every scenario/configuration.
- `assumption_register.csv`: provenance and uncertainty classification.
- `validation_summary.json`: numerical checks and headline result.

## Required wording

Use:

> In the design-basis prospective digital-twin case, the model estimates...

Do not use:

> The installed system actually achieved...

Generated case ID: `{config["case_id"]}`
"""
    (output / "README.md").write_text(readme, encoding="utf-8")

    return {
        "output_directory": str(output),
        "scenario_comparison_path": str(
            output / "scenario_comparison.csv"
        ),
        "design_case_path": str(output / "design_case_8760h.csv"),
        "validation_path": str(output / "validation_summary.json"),
        "case_summary_path": str(output / "case_study_summary.json"),
        "headline": design_full_summary,
    }
