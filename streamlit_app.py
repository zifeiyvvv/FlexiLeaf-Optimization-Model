"""FlexiLeaf open-data urban solar explorer."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import sys
import traceback

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from flexileaf.dashboard import (
    build_site_map,
    format_building_option,
    format_location_option,
    load_run_artifacts,
    prepare_map_geojson,
)
from flexileaf.open_data import LandsDClient, OpenDataError
from flexileaf.site_analysis.location import location_candidates
from flexileaf.site_analysis.offline import run_offline_site_analysis
from flexileaf.site_analysis.workflow import (
    SiteAnalysisConfig,
    run_site_analysis,
)


st.set_page_config(
    page_title="FlexiLeaf Urban Solar Explorer",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.2rem; padding-bottom: 2.5rem;}
      [data-testid="stMetricValue"] {font-size: 1.55rem;}
      .flexi-eyebrow {
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #2F7D4A;
        font-weight: 700;
        font-size: 0.78rem;
      }
      .flexi-subtitle {
        color: #486653;
        font-size: 1.05rem;
        max-width: 850px;
      }
      .flexi-badge {
        display: inline-block;
        padding: 0.25rem 0.55rem;
        border-radius: 999px;
        background: #E2F0E5;
        color: #205A35;
        margin-right: 0.35rem;
        margin-bottom: 0.35rem;
        font-size: 0.82rem;
        font-weight: 600;
      }
      .flexi-note {
        border-left: 4px solid #2F7D4A;
        background: #EEF7F0;
        padding: 0.75rem 0.9rem;
        border-radius: 0.25rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600, show_spinner=False)
def search_locations(query: str) -> pd.DataFrame:
    resource = LandsDClient().search_location(query)
    return location_candidates(resource.json())


@st.cache_data(show_spinner=False)
def cached_load_run(run_directory: str) -> dict:
    return load_run_artifacts(run_directory)


def reset_result() -> None:
    st.session_state.pop("run_directory", None)
    st.session_state.pop("building_selector", None)


def config_from_widgets() -> SiteAnalysisConfig:
    return SiteAnalysisConfig(
        search_radius_m=float(st.session_state["search_radius_m"]),
        max_buildings=int(st.session_state["max_buildings"]),
        top_buildings=int(st.session_state["top_buildings"]),
        default_building_height_m=float(
            st.session_state["default_height_m"]
        ),
        roof_usable_ratio=float(st.session_state["roof_usable_ratio"]),
        facade_usable_ratio=float(
            st.session_state["facade_usable_ratio"]
        ),
        module_efficiency=float(st.session_state["module_efficiency"]),
        performance_ratio=float(st.session_state["performance_ratio"]),
        roof_orientation_factor=float(
            st.session_state["roof_orientation_factor"]
        ),
        facade_orientation_factor=float(
            st.session_state["facade_orientation_factor"]
        ),
    )


# Header
header_text, header_image = st.columns([2.2, 1], vertical_alignment="center")
with header_text:
    st.markdown(
        '<div class="flexi-eyebrow">Open Data · Urban Solar · '
        "Decision Support</div>",
        unsafe_allow_html=True,
    )
    st.title("FlexiLeaf Urban Solar Explorer")
    st.markdown(
        '<div class="flexi-subtitle">'
        "以香港政府開放數據識別城市建築、估算屋頂與立面光伏潛力，"
        "並生成可追溯的規劃分析。 Search a Hong Kong location, "
        "inspect nearby buildings and compare transparent solar scenarios."
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<span class="flexi-badge">HKO weather & solar</span>'
        '<span class="flexi-badge">LandsD location search</span>'
        '<span class="flexi-badge">CSDI building WFS</span>'
        '<span class="flexi-badge">3D decision map</span>',
        unsafe_allow_html=True,
    )
with header_image:
    leaf_path = PROJECT_ROOT / "assets" / "flexileaf_leaf.png"
    if leaf_path.exists():
        st.image(str(leaf_path), width="stretch")

# Sidebar controls
st.sidebar.header("Analysis controls / 分析設定")
mode = st.sidebar.radio(
    "Data mode / 數據模式",
    ["Live government data / 政府即時數據", "Offline demo / 離線示範"],
    help=(
        "Live mode calls official Hong Kong services. Offline mode uses "
        "bundled synthetic test data and remains available during outages."
    ),
)

if "search_radius_m" not in st.session_state:
    defaults = SiteAnalysisConfig()
    st.session_state.update(
        {
            "search_radius_m": int(defaults.search_radius_m),
            "max_buildings": int(defaults.max_buildings),
            "top_buildings": int(defaults.top_buildings),
            "default_height_m": float(
                defaults.default_building_height_m
            ),
            "roof_usable_ratio": float(defaults.roof_usable_ratio),
            "facade_usable_ratio": float(
                defaults.facade_usable_ratio
            ),
            "module_efficiency": float(defaults.module_efficiency),
            "performance_ratio": float(defaults.performance_ratio),
            "roof_orientation_factor": float(
                defaults.roof_orientation_factor
            ),
            "facade_orientation_factor": float(
                defaults.facade_orientation_factor
            ),
        }
    )

st.sidebar.slider(
    "Search radius / 搜尋半徑 (m)",
    min_value=100,
    max_value=600,
    step=50,
    key="search_radius_m",
)
st.sidebar.slider(
    "Maximum buildings / 建築上限",
    min_value=50,
    max_value=1000,
    step=50,
    key="max_buildings",
)
st.sidebar.slider(
    "Buildings in shortlist / 候選建築數",
    min_value=5,
    max_value=40,
    step=5,
    key="top_buildings",
)

with st.sidebar.expander("Model assumptions / 模型假設"):
    st.number_input(
        "Default height if unavailable (m)",
        min_value=3.0,
        max_value=150.0,
        step=1.0,
        key="default_height_m",
    )
    st.slider(
        "Roof usable ratio",
        min_value=0.05,
        max_value=0.95,
        step=0.05,
        key="roof_usable_ratio",
    )
    st.slider(
        "Facade usable ratio",
        min_value=0.05,
        max_value=0.80,
        step=0.05,
        key="facade_usable_ratio",
    )
    st.slider(
        "Module efficiency",
        min_value=0.10,
        max_value=0.30,
        step=0.01,
        key="module_efficiency",
    )
    st.slider(
        "Performance ratio",
        min_value=0.50,
        max_value=0.95,
        step=0.01,
        key="performance_ratio",
    )
    st.slider(
        "Roof orientation factor",
        min_value=0.30,
        max_value=1.00,
        step=0.05,
        key="roof_orientation_factor",
    )
    st.slider(
        "Facade orientation factor",
        min_value=0.15,
        max_value=0.90,
        step=0.05,
        key="facade_orientation_factor",
    )

if mode.startswith("Live"):
    with st.sidebar.form("location_search_form"):
        query = st.text_input(
            "Location / 地點",
            value=st.session_state.get(
                "last_query",
                "City University of Hong Kong",
            ),
            help=(
                "Use an official building, facility, address or place name."
            ),
        )
        search_submitted = st.form_submit_button(
            "Find locations / 搜尋地點",
            width="stretch",
        )

    if search_submitted:
        reset_result()
        try:
            with st.spinner("Searching Lands Department data..."):
                candidates = search_locations(query.strip())
            if candidates.empty:
                st.sidebar.error("No usable location result was returned.")
                st.session_state.pop("location_candidates", None)
            else:
                st.session_state["location_candidates"] = candidates
                st.session_state["last_query"] = query.strip()
                st.sidebar.success(
                    f"{len(candidates)} candidate(s) found."
                )
        except (OpenDataError, ValueError) as exc:
            st.sidebar.error(str(exc))
            st.session_state.pop("location_candidates", None)

    candidates = st.session_state.get("location_candidates")
    if isinstance(candidates, pd.DataFrame) and not candidates.empty:
        candidate_records = candidates.to_dict(orient="records")
        labels = [
            format_location_option(record)
            for record in candidate_records
        ]
        selected_label = st.sidebar.selectbox(
            "Select candidate / 選擇地點",
            options=labels,
            key="location_candidate_label",
        )
        candidate_index = labels.index(selected_label)

        if st.sidebar.button(
            "Run live analysis / 執行即時分析",
            type="primary",
            width="stretch",
        ):
            reset_result()
            try:
                with st.spinner(
                    "Downloading buildings and live solar data..."
                ):
                    summary = run_site_analysis(
                        query=st.session_state["last_query"],
                        candidate_index=candidate_index,
                        config=config_from_widgets(),
                        data_root=PROJECT_ROOT / "data",
                    )
                st.session_state["run_directory"] = summary[
                    "output_directory"
                ]
                st.session_state["run_mode"] = "live"
                st.sidebar.success("Live analysis completed.")
            except Exception as exc:
                st.sidebar.error(f"Analysis failed: {exc}")
                with st.sidebar.expander("Technical details"):
                    st.code(traceback.format_exc())
    else:
        st.sidebar.info(
            "Search for a location first, then choose the correct candidate."
        )
else:
    st.sidebar.warning(
        "Offline mode uses synthetic building polygons and fixed solar "
        "readings. It is for demonstration and software testing only."
    )
    if st.sidebar.button(
        "Run offline demo / 執行離線示範",
        type="primary",
        width="stretch",
    ):
        reset_result()
        try:
            with st.spinner("Preparing the offline demonstration..."):
                summary = run_offline_site_analysis(
                    project_root=PROJECT_ROOT,
                    config=config_from_widgets(),
                )
            st.session_state["run_directory"] = summary[
                "output_directory"
            ]
            st.session_state["run_mode"] = "offline"
            st.sidebar.success("Offline demonstration completed.")
        except Exception as exc:
            st.sidebar.error(f"Offline demo failed: {exc}")
            with st.sidebar.expander("Technical details"):
                st.code(traceback.format_exc())

run_directory = st.session_state.get("run_directory")
if not run_directory:
    st.divider()
    intro_left, intro_right = st.columns([1.25, 1])
    with intro_left:
        st.subheader("How the prototype works / 原型流程")
        st.markdown(
            """
            1. **Search** an official Hong Kong place or building.
            2. **Resolve** Hong Kong 1980 Grid coordinates.
            3. **Retrieve** surrounding building polygons from CSDI.
            4. **Measure** footprint, perimeter, height and preliminary
               usable surfaces.
            5. **Match** the nearest HKO solar-radiation station.
            6. **Estimate** transparent roof and façade PV potential.
            7. **Export** CSV, GeoJSON and JSON evidence files.
            """
        )
    with intro_right:
        st.subheader("Current scope / 現階段範圍")
        st.info(
            "This stage provides planning-level instantaneous estimates. "
            "Annual generation, detailed shading, electricity demand and "
            "battery optimisation are later model stages."
        )
        st.markdown(
            """
            **Live mode** demonstrates genuine open-data integration.  
            **Offline mode** protects the demo against temporary API or
            internet outages.
            """
        )
    st.stop()

try:
    artifacts = cached_load_run(str(run_directory))
except Exception as exc:
    st.error(f"Unable to load the analysis artifacts: {exc}")
    st.stop()

summary = artifacts["summary"]
buildings = artifacts["buildings"].copy()
top_buildings = artifacts["top_buildings"].copy()
selected_location = summary["selected_location"]
station = summary["nearest_solar_station"]
solar_observation = summary["solar_observation"]
is_offline = summary.get("mode") == "offline_demo"

if is_offline:
    st.warning(
        "OFFLINE DEMONSTRATION: building geometry and solar readings are "
        "bundled test samples, not live government observations."
    )
else:
    st.success(
        "LIVE OPEN DATA: this run used official LandsD, CSDI and HKO "
        "services. Results remain planning estimates rather than field "
        "performance."
    )

# Building selector
records = top_buildings.to_dict(orient="records")
labels = [format_building_option(record) for record in records]
selected_label = st.selectbox(
    "Building shortlist / 建築候選",
    options=labels,
    key="building_selector",
    help=(
        "Buildings are ordered by distance from the selected location. "
        "The highlighted building updates the map and metrics."
    ),
)
selected_position = labels.index(selected_label)
selected_record = records[selected_position]
selected_rank = int(selected_record["building_rank"])

# Main metrics
st.subheader("Site overview / 地點概覽")
metric_columns = st.columns(5)
metric_columns[0].metric(
    "Buildings analysed",
    f"{int(summary['building_count']):,}",
)
metric_columns[1].metric(
    "Solar station",
    station["station_name"],
)
metric_columns[2].metric(
    "Global irradiance",
    f"{float(solar_observation['global_solar_wm2']):,.0f} W/m²",
)
metric_columns[3].metric(
    "Estimated PV area",
    f"{float(selected_record['estimated_total_pv_area_m2']):,.0f} m²",
)
metric_columns[4].metric(
    "Estimated current power",
    f"{float(selected_record['estimated_total_current_power_kw']):,.1f} kW",
)

location_name = (
    selected_location.get("name_en")
    or selected_location.get("name_zh")
    or "Selected location"
)
st.caption(
    f"{location_name} · "
    f"{float(selected_location['latitude']):.6f}, "
    f"{float(selected_location['longitude']):.6f} · "
    f"Generated {summary.get('generated_at_hkt', 'N/A')}"
)

# Map and selected-building detail
map_column, detail_column = st.columns([1.75, 1])
with map_column:
    st.subheader("3D building opportunity map / 3D建築潛力圖")
    map_geojson = prepare_map_geojson(
        artifacts["geojson"],
        buildings,
        selected_rank=selected_rank,
    )
    deck = build_site_map(
        map_geojson=map_geojson,
        selected_location=selected_location,
    )
    st.pydeck_chart(deck, height=590, key="site_map")

with detail_column:
    st.subheader("Selected building / 所選建築")
    st.write(f"**{selected_record['building_name']}**")
    detail_metrics = {
        "Distance from query": (
            f"{float(selected_record['distance_to_query_m']):,.1f} m"
        ),
        "Footprint": (
            f"{float(selected_record['footprint_area_m2']):,.1f} m²"
        ),
        "Height": (
            f"{float(selected_record['height_m']):,.1f} m"
        ),
        "Height source": str(selected_record["height_source"]),
        "Usable roof": (
            f"{float(selected_record['estimated_roof_usable_m2']):,.1f} m²"
        ),
        "Usable façade": (
            f"{float(selected_record['estimated_facade_usable_m2']):,.1f} m²"
        ),
        "Roof capacity": (
            f"{float(selected_record['roof_dc_capacity_kwp']):,.1f} kWp"
        ),
        "Façade capacity": (
            f"{float(selected_record['facade_dc_capacity_kwp']):,.1f} kWp"
        ),
    }
    st.dataframe(
        pd.DataFrame(
            {
                "Metric / 指標": list(detail_metrics.keys()),
                "Value / 數值": list(detail_metrics.values()),
            }
        ),
        hide_index=True,
        width="stretch",
    )
    if str(selected_record["height_source"]).startswith("assumption"):
        st.warning(
            "The building dataset did not expose a recognised height "
            "field. The configured default height was used."
        )

# Comparison charts
st.subheader("Shortlist comparison / 候選建築比較")
chart_frame = top_buildings.head(12).copy()
chart_frame["label"] = chart_frame.apply(
    lambda row: f"#{int(row['building_rank'])} {row['building_name']}",
    axis=1,
)
comparison_left, comparison_right = st.columns(2)
with comparison_left:
    st.markdown("**Estimated PV area (m²)**")
    st.bar_chart(
        chart_frame.set_index("label")[
            ["estimated_roof_usable_m2", "estimated_facade_usable_m2"]
        ],
        height=390,
        x_label="Building",
        y_label="Usable area (m²)",
    )
with comparison_right:
    st.markdown("**Estimated current output (kW)**")
    st.bar_chart(
        chart_frame.set_index("label")[
            [
                "estimated_roof_current_power_kw",
                "estimated_facade_current_power_kw",
            ]
        ],
        height=390,
        x_label="Building",
        y_label="Power (kW)",
    )

# Data table and methodology
data_tab, method_tab, source_tab, download_tab = st.tabs(
    [
        "Building data / 建築數據",
        "Method / 方法",
        "Sources / 數據來源",
        "Downloads / 下載",
    ]
)

with data_tab:
    display_columns = [
        "building_rank",
        "building_name",
        "distance_to_query_m",
        "footprint_area_m2",
        "height_m",
        "height_source",
        "estimated_roof_usable_m2",
        "estimated_facade_usable_m2",
        "total_dc_capacity_kwp",
        "estimated_total_current_power_kw",
    ]
    st.dataframe(
        top_buildings[display_columns],
        hide_index=True,
        width="stretch",
        height=480,
        column_config={
            "building_rank": "Rank",
            "building_name": "Building",
            "distance_to_query_m": st.column_config.NumberColumn(
                "Distance (m)", format="%.1f"
            ),
            "footprint_area_m2": st.column_config.NumberColumn(
                "Footprint (m²)", format="%.1f"
            ),
            "height_m": st.column_config.NumberColumn(
                "Height (m)", format="%.1f"
            ),
            "height_source": "Height source",
            "estimated_roof_usable_m2": st.column_config.NumberColumn(
                "Roof area (m²)", format="%.1f"
            ),
            "estimated_facade_usable_m2": st.column_config.NumberColumn(
                "Façade area (m²)", format="%.1f"
            ),
            "total_dc_capacity_kwp": st.column_config.NumberColumn(
                "Capacity (kWp)", format="%.1f"
            ),
            "estimated_total_current_power_kw": (
                st.column_config.NumberColumn(
                    "Current power (kW)", format="%.2f"
                )
            ),
        },
    )

with method_tab:
    config = summary.get("config", {})
    st.markdown(
        """
        **Area estimation**

        - Roof usable area = building footprint × roof usable ratio.
        - Façade usable area = perimeter × height × façade usable ratio.

        **Instantaneous PV estimate**

        `usable area × horizontal irradiance × module efficiency ×
        performance ratio × orientation factor ÷ 1000`
        """
    )
    st.json(config, expanded=False)
    st.info(
        "The method is intentionally transparent. It does not yet model "
        "detailed façade direction, windows, local obstruction, structural "
        "capacity, electrical connection or annual irradiance."
    )

with source_tab:
    st.markdown(
        """
        - **Lands Department Location Search API:** official place,
          building, address and facility search.
        - **CSDI Building WFS:** building polygons and available attributes.
        - **Hong Kong Observatory:** current solar-radiation observations.
        """
    )
    raw_metadata = artifacts.get("raw_metadata") or {}
    if raw_metadata:
        rows = []
        for source_name, metadata in raw_metadata.items():
            rows.append(
                {
                    "Source": source_name,
                    "Official URL": metadata.get("source_url"),
                    "Downloaded (HKT)": metadata.get(
                        "downloaded_at_hkt"
                    ),
                    "Content type": metadata.get("content_type"),
                }
            )
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption(
            "Offline/sample runs do not have live HTTP provenance metadata."
        )
    st.json(summary.get("method_notes", {}), expanded=False)

with download_tab:
    st.markdown(
        "Download the exact evidence files generated by this run."
    )
    download_columns = st.columns(3)
    download_columns[0].download_button(
        "Download summary JSON",
        data=artifacts["paths"]["summary"].read_text(encoding="utf-8"),
        file_name="flexileaf_site_summary.json",
        mime="application/json",
        width="stretch",
    )
    download_columns[1].download_button(
        "Download building CSV",
        data=artifacts["paths"]["buildings"].read_bytes(),
        file_name="flexileaf_building_analysis.csv",
        mime="text/csv",
        width="stretch",
    )
    download_columns[2].download_button(
        "Download analysed GeoJSON",
        data=artifacts["paths"]["geojson"].read_text(encoding="utf-8"),
        file_name="flexileaf_analysed_buildings.geojson",
        mime="application/geo+json",
        width="stretch",
    )

st.divider()
st.caption(
    "FlexiLeaf is currently a planning and decision-support prototype. "
    "All estimates must be validated through detailed engineering, shading, "
    "structural, electrical and regulatory assessment before installation."
)
