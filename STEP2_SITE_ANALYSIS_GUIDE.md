# FlexiLeaf Step 2 — Location-to-Building Solar Site Analysis

This is an **incremental package**. Step 1 must already exist in the repository,
because Step 2 imports the API clients from:

```text
src/flexileaf/open_data/
```

A full Step 1 + Step 2 combined ZIP is also supplied.

---

## 1. What this step achieves

A single command now performs this chain:

```text
Hong Kong place/building query
        ↓
LandsD Location Search API
        ↓
HK1980 x/y coordinates
        ↓
Automatic 250 m search box
        ↓
CSDI Building WFS
        ↓
Footprint, perimeter, height and distance analysis
        ↓
Nearest HKO solar-radiation station
        ↓
Planning-level roof + facade PV potential
        ↓
CSV + GeoJSON + JSON evidence package
```

This is the first complete analytical workflow in the project.

---

## 2. Files to add or replace

Copy the **contents** of this Step 2 folder into the root of the existing
repository.

### Replace

```text
requirements.txt
```

Step 2 adds `pyproj`, `shapely` and `pytest`.

### Add

```text
pytest.ini
configs/site_analysis.json
scripts/analyse_site.py
scripts/run_offline_site_demo.py
src/flexileaf/site_analysis/
data/sample/location_search_example.json
data/sample/synthetic_buildings_example.geojson
tests/
STEP2_SITE_ANALYSIS_GUIDE.md
```

If `data/sample/hko_live_solar_example.csv` already exists, replace it with the
Step 2 version. The values in this file are a fixed test sample, not live data.

Do not delete:

```text
src/flexileaf/open_data/
scripts/fetch_open_data.py
```

Those are required by Step 2.

---

## 3. Recommended GitHub Desktop procedure

1. Open GitHub Desktop.
2. Select the local `FlexiLeaf-Optimization-Model` repository.
3. Extract `FlexiLeaf_Step2_Site_Analysis.zip`.
4. Copy every item **inside** the extracted folder into the local repository
   root.
5. Allow Windows to merge folders.
6. When asked about `requirements.txt`, choose **Replace**.
7. Return to GitHub Desktop.
8. Review the file list.
9. Commit summary:

```text
feat: add location-to-building solar site analysis
```

10. Click **Commit to main**.
11. Click **Push origin**.

The GitHub root should look like:

```text
FlexiLeaf-Optimization-Model/
├── requirements.txt
├── pytest.ini
├── STEP1_API_GUIDE.md
├── STEP2_SITE_ANALYSIS_GUIDE.md
├── configs/
│   └── site_analysis.json
├── scripts/
│   ├── fetch_open_data.py
│   ├── analyse_site.py
│   └── run_offline_site_demo.py
├── src/
│   └── flexileaf/
│       ├── open_data/
│       └── site_analysis/
├── data/
│   └── sample/
└── tests/
```

---

## 4. Update the local Python environment

Open PowerShell in the repository root.

Activate the existing virtual environment:

```powershell
.venv\Scripts\Activate.ps1
```

Install the updated dependency list:

```powershell
pip install -r requirements.txt
```

The new packages are:

```text
pyproj   coordinate conversion
shapely  polygon area, perimeter, centroid and distance
pytest   automated tests
```

---

## 5. Run the offline demonstration first

This test does not contact any government website:

```powershell
python scripts/run_offline_site_demo.py
```

Expected output folder:

```text
data/processed/offline_site_demo/
├── location_candidates.csv
├── building_analysis.csv
└── summary.json
```

Important:

- The first location record follows the LandsD official example format.
- Building polygons are explicitly synthetic and only test geometry code.
- Solar observations are a fixed sample.
- These outputs must not be presented as competition results.

---

## 6. Run all automated tests

```powershell
pytest
```

Expected result:

```text
9 passed
```

The tests cover:

```text
HK1980 → WGS84 conversion
bounding-box order
location result normalisation
building footprint and distance calculations
zero-irradiance behaviour
PV output bounds
nearest solar-station selection
```

If all tests pass, the local program logic is functioning before any live API
dependency is introduced.

---

## 7. Run a live CityU analysis

```powershell
python scripts/analyse_site.py `
  --query "City University of Hong Kong"
```

One-line version:

```powershell
python scripts/analyse_site.py --query "City University of Hong Kong"
```

The program initially selects candidate index 0.

If the first search result is not the intended building, inspect:

```text
data/processed/site_analysis/<run-id>/location_candidates.csv
```

Then run, for example:

```powershell
python scripts/analyse_site.py `
  --query "City University of Hong Kong" `
  --candidate-index 2
```

Candidate indices start at zero.

---

## 8. Live output structure

Each run receives its own folder:

```text
data/processed/site_analysis/
└── city-university-of-hong-kong-20260719T123456+0800/
    ├── location_candidates.csv
    ├── solar_observations.csv
    ├── building_analysis.csv
    ├── top_buildings.csv
    ├── analysed_buildings.geojson
    └── site_summary.json
```

### `location_candidates.csv`

Contains:

```text
candidate_rank
name_en / name_zh
address_en / address_zh
district_en / district_zh
x_hk1980 / y_hk1980
longitude / latitude
```

The LandsD API returns Hong Kong 1980 Grid x/y. The code converts them with
EPSG:2326 → EPSG:4326.

### `building_analysis.csv`

Contains:

```text
distance_to_query_m
footprint_area_m2
perimeter_m
height_m
height_source
estimated_roof_usable_m2
estimated_facade_usable_m2
estimated_total_pv_area_m2
roof_dc_capacity_kwp
facade_dc_capacity_kwp
estimated_total_current_power_kw
```

### `analysed_buildings.geojson`

This is the future website map layer. Each building feature is enriched with
FlexiLeaf result properties.

### `site_summary.json`

This is the machine-readable evidence file. It records:

```text
query
selected location
WFS bounding box
configuration
nearest solar station
solar observation
selected building
raw source paths
method notes and limitations
```

---

## 9. Configuration

Edit:

```text
configs/site_analysis.json
```

Default values:

```json
{
  "search_radius_m": 250.0,
  "max_buildings": 300,
  "top_buildings": 15,
  "default_building_height_m": 30.0,
  "roof_usable_ratio": 0.65,
  "facade_usable_ratio": 0.25,
  "module_efficiency": 0.20,
  "performance_ratio": 0.82,
  "roof_orientation_factor": 0.90,
  "facade_orientation_factor": 0.55
}
```

These are scenario assumptions, not certified product specifications.

### Important interpretation

`roof_usable_ratio = 0.65` means the planning model treats 65% of the footprint
as potentially usable roof area.

`facade_usable_ratio = 0.25` means the model uses:

```text
building perimeter × building height × 25%
```

as a preliminary facade area.

It does not yet identify windows, north/south orientation, fire access,
maintenance access, detailed shadows or structural restrictions.

---

## 10. Current PV formula

For each surface:

```text
current power (kW)
=
usable area (m²)
× horizontal irradiance (W/m²)
× module efficiency
× performance ratio
× orientation factor
÷ 1000
```

The result is:

```text
a planning-level instantaneous estimate
```

It is not:

```text
annual energy generation
field-measured performance
PVsyst certification
structural approval
electrical design approval
```

The model deliberately states these limits in `site_summary.json`.

---

## 11. Which files should be committed?

Commit all source code, tests, configuration and sample files.

Do not commit every generated live run. Generated folders change constantly.

Recommended `.gitignore` additions later:

```gitignore
.venv/
__pycache__/
.pytest_cache/
data/raw/**/*.json
data/raw/**/*.csv
data/raw/**/*.geojson
data/raw/**/*.meta.json
data/processed/site_analysis/
data/processed/offline_site_demo/
```

When the final competition case study is selected, copy one frozen and reviewed
run into:

```text
data/case_study/
```

That final case should be committed so judges can reproduce the stated result.

---

## 12. Common errors

### `ModuleNotFoundError: No module named 'pyproj'`

```powershell
pip install -r requirements.txt
```

### No location results

Try a more specific official English or Chinese place name:

```powershell
python scripts/analyse_site.py --query "香港城市大學"
```

### Wrong location selected

Open `location_candidates.csv` and rerun with `--candidate-index`.

### No building polygons

Increase the radius in `configs/site_analysis.json` from 250 to 400 metres, but
avoid unnecessarily large requests.

### More than 300 buildings are needed

Increase `max_buildings`, up to the official WFS request limit. For the first
prototype, a compact local search is preferable.

### Height source says `assumption:default`

The returned feature did not expose a recognised positive height field. The
model used `default_building_height_m`. This is transparently recorded rather
than silently presenting the estimate as observed data.

### Solar radiation is low or zero

This may be correct at night or under poor weather. Run the analysis during
daylight or use the offline sample to verify program behaviour.

---

## 13. Definition of done

Step 2 is complete when:

```powershell
python scripts/run_offline_site_demo.py
pytest
python scripts/analyse_site.py --query "City University of Hong Kong"
```

all run successfully, and the live run produces:

```text
location_candidates.csv
building_analysis.csv
analysed_buildings.geojson
site_summary.json
```

The next step will use these outputs to build an interactive map and selection
interface, where the user chooses a location and building before running the
analysis.
