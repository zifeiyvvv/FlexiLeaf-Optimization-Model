# FlexiLeaf Step 1 — Hong Kong Open Data API Integration

This folder is designed to be copied directly into the root of the existing
`FlexiLeaf-Optimization-Model` GitHub repository.

## 1. What this step implements

The code currently connects to four official open-data services:

1. Hong Kong Observatory current weather JSON API.
2. Hong Kong Observatory latest solar-radiation CSV.
3. Hong Kong Observatory historical daily global solar-radiation CSV.
4. Lands Department Location Search JSON API.
5. CSDI/Lands Department Building OGC WFS GeoJSON service.

The code preserves two data layers:

- `data/raw/`: immutable, timestamped responses exactly as received.
- `data/processed/`: tidy CSV or GeoJSON files used by later models and the web app.

Every raw download also receives a `.meta.json` file recording the official
source URL, download time, HTTP status and request parameters.

## 2. Exact GitHub locations

After copying the package, the repository should contain:

```text
FlexiLeaf-Optimization-Model/
├── requirements.txt
├── STEP1_API_GUIDE.md
├── scripts/
│   └── fetch_open_data.py
├── src/
│   └── flexileaf/
│       ├── __init__.py
│       └── open_data/
│           ├── __init__.py
│           ├── http_client.py
│           ├── storage.py
│           ├── hko.py
│           ├── landsd.py
│           └── csdi.py
└── data/
    ├── sample/
    │   └── hko_live_solar_example.csv
    ├── raw/
    │   └── .gitkeep
    └── processed/
        └── .gitkeep
```

Do not put Python files inside `data/`.  
Do not put downloaded CSV files inside `src/`.  
`src/` is for reusable program logic; `scripts/` is for commands; `data/` is
for input and output data.

## 3. Copying the files to GitHub using the browser

For the first upload, downloading the ZIP and using GitHub's web interface is
possible, but GitHub does not upload a folder as a folder reliably unless all
files are selected together.

Recommended browser method:

1. Download and unzip `FlexiLeaf_Step1_OpenData_API.zip`.
2. Open the existing GitHub repository.
3. Select **Add file → Upload files**.
4. Open the unzipped folder on the computer.
5. Select `requirements.txt`, `STEP1_API_GUIDE.md`, `scripts`, `src`, and
   `data` together.
6. Drag the selected items into the GitHub upload area.
7. Wait until the complete file list appears.
8. Commit message:

```text
feat: add Hong Kong government open-data connectors
```

9. Select **Commit directly to the main branch** only if nobody else is editing
   the repository. Otherwise create a branch named:

```text
feature/open-data-connectors
```

10. Click **Commit changes**.

A better long-term method is GitHub Desktop, because the project will soon have
many code changes.

## 4. Copying the files using GitHub Desktop

1. Install and open GitHub Desktop.
2. Select **File → Clone repository**.
3. Choose `zifeiyvvv/FlexiLeaf-Optimization-Model`.
4. Choose a local folder and click **Clone**.
5. Open the downloaded Step 1 ZIP and extract it.
6. Copy every item inside the extracted folder into the local repository root.
7. Return to GitHub Desktop.
8. Check that all new files appear in **Changes**.
9. Summary:

```text
feat: add Hong Kong government open-data connectors
```

10. Click **Commit to main**.
11. Click **Push origin**.

## 5. Local Python setup on Windows

Open PowerShell in the repository root.

Check Python:

```powershell
python --version
```

Python 3.11 or 3.12 is recommended.

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation for the current session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 6. First API tests

Run these commands from the repository root.

### Current weather

```powershell
python scripts/fetch_open_data.py weather-current --lang en
```

Expected outputs include:

```text
data/raw/hko/current_weather/<timestamp>.json
data/raw/hko/current_weather/<timestamp>.meta.json
data/processed/hko/current_weather/temperature.csv
data/processed/hko/current_weather/humidity.csv
data/processed/hko/current_weather/rainfall.csv
data/processed/hko/current_weather/summary.csv
```

### Live solar radiation

```powershell
python scripts/fetch_open_data.py solar-live
```

Expected output:

```text
data/processed/hko/latest_solar_radiation/latest_solar_radiation.csv
```

The processed file uses these stable project column names:

```text
timestamp_hkt
station
global_solar_wm2
direct_solar_wm2
diffuse_solar_wm2
```

### Historical daily solar radiation

King's Park, all available years:

```powershell
python scripts/fetch_open_data.py solar-history --station KP --year ALL
```

Kau Sai Chau, all available years:

```powershell
python scripts/fetch_open_data.py solar-history --station KSC --year ALL
```

A specific year:

```powershell
python scripts/fetch_open_data.py solar-history --station KP --year 2026
```

### Location search

```powershell
python scripts/fetch_open_data.py location-search --query "City University of Hong Kong"
```

This will store the full official JSON and create a flattened CSV.

### Building footprints

Example bounding box around part of Kowloon:

```powershell
python scripts/fetch_open_data.py buildings `
  --south-lat 22.332 `
  --west-lon 114.170 `
  --north-lat 22.345 `
  --east-lon 114.185 `
  --count 100
```

Expected outputs:

```text
data/processed/csdi/building_footprints/buildings.geojson
data/processed/csdi/building_footprints/buildings_summary.csv
```

The CSDI WFS limit is 10,000 records per request. Keep the first test at 100.

## 7. Which generated files should be committed?

Commit:

```text
data/sample/hko_live_solar_example.csv
data/raw/.gitkeep
data/processed/.gitkeep
```

For now, do not repeatedly commit every live API download. The raw API data
change frequently and can make the repository unnecessarily large.

Later, select one frozen competition case study and commit it under:

```text
data/case_study/
```

That case-study folder will contain the exact input data required to reproduce
the competition result.

## 8. Common errors

### `ModuleNotFoundError: No module named 'requests'`

Run:

```powershell
pip install -r requirements.txt
```

Make sure `.venv` is activated.

### `Unable to connect to the open-data service`

Check:

1. Internet connection.
2. Whether the official URL opens in a browser.
3. Whether a university/company network is blocking the service.
4. Try again later; the client automatically retries temporary failures.

### HKO CSV schema changed

The program will report which expected columns are missing. Do not silently
rename random columns. Open the latest official dataset page, confirm the new
data dictionary, and update the rename mapping in:

```text
src/flexileaf/open_data/hko.py
```

### CSDI returns no buildings

Reduce or move the bounding box. Also confirm the coordinate order:

```text
south latitude, west longitude, north latitude, east longitude
```

### CSDI returns too many buildings

Reduce the bounding box or paginate using:

```text
--count 1000 --start-index 0
--count 1000 --start-index 1000
```

## 9. Why raw and processed data are separate

`raw/` is evidence. It proves what the government service returned and when.

`processed/` is the model-ready layer. Column names and units are standardised
here so later optimisation code does not depend directly on changing external
schemas.

The future website should call the same client classes rather than duplicating
requests inside Streamlit:

```python
from flexileaf.open_data import HKOClient

client = HKOClient()
resource = client.fetch_latest_solar_radiation()
solar_df = client.parse_latest_solar_radiation(resource.text())
```

## 10. Definition of done for Step 1

Step 1 is complete when all five commands run without error and create files:

```text
weather-current
weather-forecast
solar-live
solar-history
location-search
buildings
```

After that, the next development step is to combine:

- a selected location;
- nearby building footprints;
- solar-radiation observations;
- a transparent photovoltaic generation estimator.

That will turn the open-data connector into the first real FlexiLeaf analytical
workflow.
