# FlexiLeaf

**Open-data-driven urban solar planning and community microgrid optimisation platform for Hong Kong.**

FlexiLeaf combines Hong Kong government open data, building geometry, solar-resource modelling, transparent photovoltaic estimation, battery dispatch optimisation and a fixed annual digital-twin case study. The prototype helps planners, campuses, housing estates and facility managers identify underused roof, facade and public-infrastructure surfaces, compare system configurations and export traceable evidence before costly engineering deployment.

> **Project status:** working student research prototype. All fixed-case results are prospective simulations, not measured operation or certified product performance.

## What is implemented

- Hong Kong Observatory weather and solar-data connectors.
- Lands Department location search and CSDI building WFS integration.
- HK1980/WGS84 coordinate conversion and building-geometry analysis.
- Interactive Streamlit 3D building opportunity map.
- Transparent roof, facade and public-facility PV estimation.
- 24-hour load/PV profiles and no-storage baseline.
- Mixed-integer battery dispatch with SOC, power, energy-balance and terminal-SOC constraints.
- Fixed 2025 design-basis digital twin: 8,760 hourly records, 3 performance scenarios and 5 system configurations.
- CSV, GeoJSON and JSON evidence exports.
- 25 automated tests.

## Fixed 2025 design-basis case

The fixed case combines archived 2025 Hong Kong Observatory daily observations, the proposed FlexiLeaf campus/community blueprint and explicitly documented engineering assumptions.

| Design full-microgrid metric | Simulated result |
|---|---:|
| Annual electricity demand | 11,774 MWh |
| Annual photovoltaic generation | 2,505 MWh |
| Peak grid-demand reduction vs grid-only | 29.4% |
| Scenario energy-cost saving vs grid-only | 21.9% |
| Grid-import / operational-carbon reduction | 20.7% |
| Stationary battery + aggregated V2G capacity | 2,800 kWh |

**Required interpretation:** these figures are prospective model outputs under the recorded design assumptions. They are not field measurements or guaranteed future savings.

## System architecture

```text
Official Hong Kong open data
        ↓
Location and building-data pipeline
        ↓
Urban solar opportunity model
        ↓
Load, PV and tariff scenarios
        ↓
Battery / V2G optimisation
        ↓
Interactive dashboard + reproducible evidence files
```

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
pytest
streamlit run streamlit_app.py
```

Generate the fixed annual case:

```bash
python scripts/generate_design_basis_case.py
```

The evidence package is written to:

```text
data/case_study/design_basis_2025/
```

## Main application pages

1. **Urban Solar Explorer** — search a Hong Kong location, retrieve nearby buildings and inspect preliminary PV opportunities on a 3D map.
2. **Energy Optimisation** — build a 24-hour load/PV scenario and solve battery dispatch.
3. **Design-Basis Case** — review the fixed annual case, scenario comparison, monthly results and validation evidence.

## Reproducibility and evidence

Key fixed-case files:

```text
design_case_8760h.csv
scenario_comparison.csv
monthly_summary.csv
assumption_register.csv
site_and_system_parameters.csv
validation_summary.json
source_manifest.json
```

The repository separates:

- `official_open_data`
- `blueprint_design`
- `engineering_assumption`
- `derived_value`
- `simulation_output`

## Testing

```bash
pytest
```

Current validated suite: **25 tests passed**. Tests cover API parsing, coordinates, geometry, solar modelling, energy conservation, load calibration, MILP dispatch, dashboard helpers and annual digital-twin generation.

## Important limitations

The current prototype does not replace detailed engineering design. It does not yet provide field-validated module performance, structural assessment, detailed facade/window segmentation, bankable shading analysis, utility interconnection approval, real customer billing or measured building smart-meter data. V2G is represented as an aggregated equivalent resource in the fixed case.

## Competition wording

Use:

> In the design-basis prospective digital-twin case, the model estimates...

Do not use:

> The installed system actually achieved...

## Licence and data use

Add the project software licence before final public release. Government-source URLs, archived files, checksums and data classifications are recorded in the fixed evidence package.
