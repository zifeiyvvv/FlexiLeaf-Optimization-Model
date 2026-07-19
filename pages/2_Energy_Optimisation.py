"""Interactive 24-hour energy and battery optimisation page."""

from __future__ import annotations

from pathlib import Path
import json
import sys
import traceback

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from flexileaf.dashboard import (
    format_building_option,
    load_run_artifacts,
)
from flexileaf.energy.hko_daily import (
    latest_complete_daily_solar,
    parse_hko_daily_solar_csv,
)
from flexileaf.energy.workflow import (
    EnergySimulationConfig,
    run_energy_simulation,
)
from flexileaf.open_data import HKOClient, OpenDataError
from flexileaf.site_analysis.offline import run_offline_site_analysis


st.set_page_config(
    page_title="FlexiLeaf Energy Optimisation",
    page_icon="🔋",
    layout="wide",
)

st.title("🔋 Energy Optimisation / 能源優化")
st.markdown(
    """
    将选定建筑转化为24小时能源情景，比较**无储能基准**与
    **电池混合整数优化**。当前负荷和电价均为公开、可调整的情景输入，
    不伪装成实测数据或正式账单。
    """
)


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_latest_daily_solar(
    station_code: str,
) -> dict:
    resource = HKOClient().fetch_daily_solar_radiation(
        station=station_code,
        year="ALL",
    )
    frame = parse_hko_daily_solar_csv(resource.text())
    row = latest_complete_daily_solar(frame)
    row["source_url"] = resource.url
    return row


def load_dispatch(summary: dict) -> pd.DataFrame:
    return pd.read_csv(summary["dispatch_path"])


run_directory = st.session_state.get("run_directory")
if not run_directory:
    st.info(
        "No site-analysis run is active. Return to the main page for a live "
        "search, or prepare the bundled offline site demonstration."
    )
    if st.button("Prepare offline site demo / 建立離線地點", type="primary"):
        site_summary = run_offline_site_analysis(
            project_root=PROJECT_ROOT
        )
        st.session_state["run_directory"] = site_summary[
            "output_directory"
        ]
        st.session_state["run_mode"] = "offline"
        st.rerun()
    try:
        st.page_link(
            "streamlit_app.py",
            label="← Open Urban Solar Explorer / 返回地點分析",
        )
    except (KeyError, RuntimeError):
        st.caption(
            "Return to the main Streamlit page to create a site analysis."
        )
    st.stop()

try:
    artifacts = load_run_artifacts(run_directory)
except Exception as exc:
    st.error(f"Unable to load site-analysis data: {exc}")
    st.stop()

site_summary = artifacts["summary"]
top_buildings = artifacts["top_buildings"]
station = site_summary["nearest_solar_station"]
is_offline = site_summary.get("mode") == "offline_demo"

if is_offline:
    st.warning(
        "The active site is an offline software-test demonstration. "
        "Building geometry is synthetic."
    )
else:
    st.success(
        "The active site originated from the live open-data workflow."
    )

building_records = top_buildings.to_dict(orient="records")
building_labels = [
    format_building_option(record)
    for record in building_records
]
selected_label = st.selectbox(
    "Building / 建築",
    options=building_labels,
)
selected_record = building_records[
    building_labels.index(selected_label)
]
building_rank = int(selected_record["building_rank"])

controls_left, controls_middle, controls_right = st.columns(3)

with controls_left:
    st.subheader("Demand / 用電負荷")
    load_archetype = st.selectbox(
        "Synthetic archetype",
        options=["education", "office", "residential", "mixed_use"],
        index=0,
    )
    suggested_peak = max(
        80.0,
        float(selected_record["total_dc_capacity_kwp"]) * 0.85,
    )
    peak_load_kw = st.number_input(
        "Peak load (kW)",
        min_value=20.0,
        max_value=5000.0,
        value=float(round(suggested_peak, 1)),
        step=10.0,
    )
    st.caption(
        "Replace this synthetic archetype with measured hourly load data "
        "before presenting a final engineering case."
    )

with controls_middle:
    st.subheader("Solar / 太陽輻射")
    solar_source = st.radio(
        "Daily irradiation source",
        [
            "Manual scenario",
            "Latest complete HKO daily observation",
        ],
    )
    daily_solar_mj_m2 = st.number_input(
        "Daily global solar radiation (MJ/m²)",
        min_value=0.0,
        max_value=40.0,
        value=18.0,
        step=0.5,
        key="daily_solar_input",
    )
    if solar_source.startswith("Latest"):
        if st.button("Fetch HKO daily value"):
            try:
                with st.spinner("Reading HKO historical solar data..."):
                    solar_row = fetch_latest_daily_solar(
                        station["station_code"]
                    )
                st.session_state["hko_daily_solar"] = solar_row
                st.session_state["daily_solar_input"] = float(
                    solar_row["global_solar_mj_m2"]
                )
                st.rerun()
            except Exception as exc:
                st.error(f"HKO daily data could not be loaded: {exc}")
        solar_row = st.session_state.get("hko_daily_solar")
        if solar_row:
            st.caption(
                f'{station["station_name"]}: '
                f'{solar_row["date"]}, '
                f'{solar_row["global_solar_mj_m2"]:.2f} MJ/m², '
                f'completeness={solar_row["data_completeness"]}'
            )
    sunrise_hour = st.slider(
        "Sunrise hour",
        min_value=4.5,
        max_value=8.0,
        value=6.0,
        step=0.25,
    )
    sunset_hour = st.slider(
        "Sunset hour",
        min_value=16.0,
        max_value=20.5,
        value=18.5,
        step=0.25,
    )

with controls_right:
    st.subheader("Battery / 儲能")
    battery_capacity_kwh = st.number_input(
        "Capacity (kWh)",
        min_value=20.0,
        max_value=10000.0,
        value=500.0,
        step=50.0,
    )
    maximum_charge_kw = st.number_input(
        "Maximum charge power (kW)",
        min_value=5.0,
        max_value=5000.0,
        value=150.0,
        step=10.0,
    )
    maximum_discharge_kw = st.number_input(
        "Maximum discharge power (kW)",
        min_value=5.0,
        max_value=5000.0,
        value=150.0,
        step=10.0,
    )
    efficiency = st.slider(
        "One-way efficiency",
        min_value=0.75,
        max_value=1.0,
        value=0.95,
        step=0.01,
    )

with st.expander("Tariff, carbon and model assumptions"):
    tariff_columns = st.columns(4)
    off_peak = tariff_columns[0].number_input(
        "Off-peak HKD/kWh",
        min_value=0.0,
        value=1.05,
        step=0.05,
    )
    shoulder = tariff_columns[1].number_input(
        "Shoulder HKD/kWh",
        min_value=0.0,
        value=1.35,
        step=0.05,
    )
    peak_tariff = tariff_columns[2].number_input(
        "Peak HKD/kWh",
        min_value=0.0,
        value=1.75,
        step=0.05,
    )
    export_tariff = tariff_columns[3].number_input(
        "Export HKD/kWh",
        min_value=0.0,
        value=0.50,
        step=0.05,
    )
    assumption_columns = st.columns(3)
    peak_penalty = assumption_columns[0].number_input(
        "Peak penalty HKD/kW",
        min_value=0.0,
        value=4.0,
        step=0.5,
    )
    degradation_cost = assumption_columns[1].number_input(
        "Battery cycle cost HKD/kWh",
        min_value=0.0,
        value=0.05,
        step=0.01,
    )
    carbon_intensity = assumption_columns[2].number_input(
        "Grid carbon kg/kWh",
        min_value=0.0,
        value=0.39,
        step=0.01,
    )
    st.caption(
        "These tariff and carbon values are scenario assumptions. "
        "They are not labelled as current official utility rates."
    )

if st.button(
    "Run battery optimisation / 執行儲能優化",
    type="primary",
    width="stretch",
):
    try:
        config = EnergySimulationConfig(
            load_archetype=load_archetype,
            peak_load_kw=peak_load_kw,
            daily_solar_mj_m2=float(
                st.session_state["daily_solar_input"]
            ),
            sunrise_hour=sunrise_hour,
            sunset_hour=sunset_hour,
            battery_capacity_kwh=battery_capacity_kwh,
            maximum_charge_kw=maximum_charge_kw,
            maximum_discharge_kw=maximum_discharge_kw,
            charging_efficiency=efficiency,
            discharging_efficiency=efficiency,
            degradation_cost_hkd_per_kwh=degradation_cost,
            off_peak_tariff_hkd_per_kwh=off_peak,
            shoulder_tariff_hkd_per_kwh=shoulder,
            peak_tariff_hkd_per_kwh=peak_tariff,
            export_tariff_hkd_per_kwh=export_tariff,
            peak_demand_penalty_hkd_per_kw=peak_penalty,
            carbon_intensity_kg_per_kwh=carbon_intensity,
        )
        with st.spinner("Solving mixed-integer battery dispatch..."):
            result = run_energy_simulation(
                site_run_directory=run_directory,
                building_rank=building_rank,
                config=config,
            )
        st.session_state["energy_result"] = result
    except Exception as exc:
        st.error(f"Energy optimisation failed: {exc}")
        with st.expander("Technical details"):
            st.code(traceback.format_exc())

result = st.session_state.get("energy_result")
if not result:
    st.divider()
    st.markdown(
        """
        **Model constraints**

        - hourly electricity balance;
        - battery state-of-charge transition;
        - minimum and maximum SOC;
        - maximum charge and discharge power;
        - binary charge/discharge mode;
        - equal initial and terminal SOC;
        - explicit peak-grid-import variable.
        """
    )
    st.stop()

dispatch = load_dispatch(result)
baseline = result["baseline"]
optimised = result["optimised"]
improvement = result["improvement"]
diagnostics = result["solver_diagnostics"]

st.divider()
st.subheader("Result summary / 結果摘要")
metric_columns = st.columns(5)
metric_columns[0].metric(
    "Peak reduction",
    f'{improvement["peak_reduction_percent"]:.1f}%',
    f'{baseline["peak_grid_import_kw"]:.1f} → '
    f'{optimised["peak_grid_import_kw"]:.1f} kW',
)
metric_columns[1].metric(
    "Energy-cost saving",
    f'{improvement["energy_cost_saving_percent"]:.1f}%',
    f'HKD {baseline["net_energy_cost_hkd"]:.0f} → '
    f'{optimised["net_energy_cost_hkd"]:.0f}',
)
metric_columns[2].metric(
    "Grid import reduction",
    f'{improvement["grid_import_reduction_percent"]:.1f}%',
    f'{baseline["grid_import_kwh"]:.0f} → '
    f'{optimised["grid_import_kwh"]:.0f} kWh',
)
metric_columns[3].metric(
    "PV self-consumption",
    f'{optimised["pv_self_consumption_fraction"] * 100:.1f}%',
    f'{improvement["self_consumption_gain_percentage_points"]:+.1f} pp',
)
metric_columns[4].metric(
    "Carbon reduction",
    f'{improvement["carbon_reduction_percent"]:.1f}%',
    f'{baseline["carbon_emissions_kg"]:.0f} → '
    f'{optimised["carbon_emissions_kg"]:.0f} kg',
)

chart_left, chart_right = st.columns([1.55, 1])
with chart_left:
    st.markdown("**Load, PV and optimised grid import**")
    plot = dispatch.set_index("timestamp")[
        [
            "load_kw",
            "pv_generation_kw",
            "optimised_grid_import_kw",
        ]
    ]
    st.line_chart(
        plot,
        height=420,
        y_label="Power (kW)",
    )
with chart_right:
    st.markdown("**Battery power and state of charge**")
    battery_plot = dispatch.set_index("timestamp")[
        [
            "optimised_battery_charge_kw",
            "optimised_battery_discharge_kw",
            "optimised_battery_soc_kwh",
        ]
    ]
    st.line_chart(
        battery_plot,
        height=420,
    )

st.markdown("**Baseline versus optimised grid import**")
st.line_chart(
    dispatch.set_index("timestamp")[
        ["baseline_grid_import_kw", "optimised_grid_import_kw"]
    ],
    height=350,
    y_label="Grid import (kW)",
)

result_tab, dispatch_tab, validation_tab, download_tab = st.tabs(
    [
        "Comparison",
        "Hourly dispatch",
        "Validation",
        "Downloads",
    ]
)

with result_tab:
    comparison = pd.DataFrame(
        {
            "Metric": [
                "Peak grid import (kW)",
                "Grid import (kWh)",
                "Grid export (kWh)",
                "Net energy cost (HKD)",
                "Objective cost (HKD)",
                "Carbon emissions (kg)",
                "PV self-consumption (%)",
                "Load self-sufficiency (%)",
            ],
            "Baseline": [
                baseline["peak_grid_import_kw"],
                baseline["grid_import_kwh"],
                baseline["grid_export_kwh"],
                baseline["net_energy_cost_hkd"],
                baseline["objective_cost_hkd"],
                baseline["carbon_emissions_kg"],
                baseline["pv_self_consumption_fraction"] * 100,
                baseline["load_self_sufficiency_fraction"] * 100,
            ],
            "Optimised": [
                optimised["peak_grid_import_kw"],
                optimised["grid_import_kwh"],
                optimised["grid_export_kwh"],
                optimised["net_energy_cost_hkd"],
                optimised["objective_cost_hkd"],
                optimised["carbon_emissions_kg"],
                optimised["pv_self_consumption_fraction"] * 100,
                optimised["load_self_sufficiency_fraction"] * 100,
            ],
        }
    )
    st.dataframe(comparison, hide_index=True, width="stretch")

with dispatch_tab:
    st.dataframe(dispatch, hide_index=True, width="stretch", height=500)

with validation_tab:
    st.json(diagnostics, expanded=True)
    if diagnostics["maximum_balance_error_kw"] < 1e-6:
        st.success("Hourly energy-balance validation passed.")
    else:
        st.error("Energy-balance error exceeds tolerance.")
    if (
        diagnostics[
            "maximum_simultaneous_charge_discharge_kw"
        ]
        < 1e-6
    ):
        st.success("No simultaneous battery charging and discharging.")
    else:
        st.error("Simultaneous charge/discharge was detected.")
    st.info(
        "The 24-hour solar curve is derived from a daily total and the load "
        "is a synthetic archetype. These must be replaced or validated for "
        "a final real-building case study."
    )

with download_tab:
    download_columns = st.columns(2)
    download_columns[0].download_button(
        "Download dispatch CSV",
        data=Path(result["dispatch_path"]).read_bytes(),
        file_name="flexileaf_energy_dispatch.csv",
        mime="text/csv",
        width="stretch",
    )
    download_columns[1].download_button(
        "Download summary JSON",
        data=Path(result["summary_path"]).read_text(encoding="utf-8"),
        file_name="flexileaf_energy_summary.json",
        mime="application/json",
        width="stretch",
    )

try:
    st.page_link(
        "streamlit_app.py",
        label="← Return to Urban Solar Explorer / 返回地點分析",
    )
except (KeyError, RuntimeError):
    st.caption("Return to the main Streamlit page for site analysis.")
