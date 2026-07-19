"""Fixed design-basis annual case-study viewer."""

from __future__ import annotations

from pathlib import Path
import json

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = (
    PROJECT_ROOT / "data" / "case_study" / "design_basis_2025"
)

st.set_page_config(
    page_title="FlexiLeaf Design-Basis Case",
    page_icon="📊",
    layout="wide",
)
st.title("📊 Design-Basis Digital Twin / 設計基準數字孿生")
st.warning(
    "This page presents prospective simulation results. "
    "It does not contain measured operation from an installed system."
)

required = [
    CASE_ROOT / "scenario_comparison.csv",
    CASE_ROOT / "monthly_summary.csv",
    CASE_ROOT / "representative_peak_week.csv",
    CASE_ROOT / "validation_summary.json",
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    st.error(
        "The fixed case has not been generated. Run: "
        "`python scripts/generate_design_basis_case.py`"
    )
    st.code("\n".join(missing))
    st.stop()

comparison = pd.read_csv(CASE_ROOT / "scenario_comparison.csv")
monthly = pd.read_csv(CASE_ROOT / "monthly_summary.csv")
week = pd.read_csv(CASE_ROOT / "representative_peak_week.csv")
validation = json.loads(
    (CASE_ROOT / "validation_summary.json").read_text(
        encoding="utf-8"
    )
)

design = comparison[
    comparison["scenario"] == "design"
].copy()
full = design[
    design["configuration"] == "full_microgrid_v2g"
].iloc[0]

metrics = st.columns(5)
metrics[0].metric(
    "Annual PV",
    f'{full["annual_pv_generation_mwh"]:,.0f} MWh',
)
metrics[1].metric(
    "Peak reduction",
    f'{full["peak_reduction_percent"]:.1f}%',
)
metrics[2].metric(
    "Energy-cost saving",
    f'{full["energy_cost_saving_percent"]:.1f}%',
)
metrics[3].metric(
    "Carbon reduction",
    f'{full["carbon_reduction_percent"]:.1f}%',
)
metrics[4].metric(
    "PV self-consumption",
    f'{full["pv_self_consumption_percent"]:.1f}%',
)

st.subheader("Design configuration comparison")
chart_data = design.set_index("configuration")[
    [
        "peak_reduction_percent",
        "energy_cost_saving_percent",
        "carbon_reduction_percent",
    ]
]
st.bar_chart(chart_data, height=400)

st.subheader("Monthly energy — design full microgrid")
monthly_design = monthly[
    (monthly["scenario"] == "design")
    & (monthly["configuration"] == "full_microgrid_v2g")
].copy()
monthly_design["load_mwh"] = monthly_design["load_kwh"] / 1000
monthly_design["pv_mwh"] = (
    monthly_design["pv_generation_kwh"] / 1000
)
monthly_design["grid_import_mwh"] = (
    monthly_design["grid_import_kwh"] / 1000
)
st.line_chart(
    monthly_design.set_index("month")[
        ["load_mwh", "pv_mwh", "grid_import_mwh"]
    ],
    height=380,
)

st.subheader("Representative peak week")
week["timestamp"] = pd.to_datetime(week["timestamp"])
st.line_chart(
    week.set_index("timestamp")[
        [
            "total_load_kw",
            "pv_generation_kw",
            "grid_import_kw",
            "battery_soc_kwh",
        ]
    ],
    height=450,
)

data_tab, validation_tab, downloads_tab = st.tabs(
    ["Scenario table", "Validation", "Downloads"]
)
with data_tab:
    st.dataframe(comparison, hide_index=True, width="stretch")
with validation_tab:
    st.json(validation)
with downloads_tab:
    for filename in [
        "scenario_comparison.csv",
        "monthly_summary.csv",
        "assumption_register.csv",
        "site_and_system_parameters.csv",
        "validation_summary.json",
    ]:
        path = CASE_ROOT / filename
        st.download_button(
            f"Download {filename}",
            data=path.read_bytes(),
            file_name=filename,
            width="stretch",
        )

st.info(
    "Recommended wording: “In the design-basis prospective digital-twin "
    "case, the model estimates…”"
)
