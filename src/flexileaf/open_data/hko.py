"""Hong Kong Observatory open-data connector and parsers."""

from __future__ import annotations

from io import StringIO
from typing import Any

import pandas as pd

from .http_client import DownloadedResource, GovernmentHTTPClient, OpenDataError


class HKOClient:
    """Client for weather and solar-radiation resources from the HKO."""

    WEATHER_API_URL = (
        "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"
    )
    LIVE_SOLAR_CSV_URL = (
        "https://data.weather.gov.hk/weatherAPI/"
        "hko_data/regional-weather/latest_1min_solar.csv"
    )
    DAILY_SOLAR_CSV_TEMPLATE = (
        "https://data.weather.gov.hk/weatherAPI/cis/csvfile/"
        "{station}/{year}/daily_{station}_GSR_{year}.csv"
    )

    VALID_LANGUAGES = {"en", "tc", "sc"}
    VALID_SOLAR_STATIONS = {"KP", "KSC"}

    def __init__(self, http_client: GovernmentHTTPClient | None = None) -> None:
        self.http = http_client or GovernmentHTTPClient()

    def fetch_current_weather(self, lang: str = "en") -> DownloadedResource:
        lang = lang.lower()
        if lang not in self.VALID_LANGUAGES:
            raise ValueError("lang must be one of: en, tc, sc")
        return self.http.get(
            self.WEATHER_API_URL,
            params={"dataType": "rhrread", "lang": lang},
        )

    def fetch_nine_day_forecast(self, lang: str = "en") -> DownloadedResource:
        lang = lang.lower()
        if lang not in self.VALID_LANGUAGES:
            raise ValueError("lang must be one of: en, tc, sc")
        return self.http.get(
            self.WEATHER_API_URL,
            params={"dataType": "fnd", "lang": lang},
        )

    def fetch_latest_solar_radiation(self) -> DownloadedResource:
        return self.http.get(self.LIVE_SOLAR_CSV_URL)

    def fetch_daily_solar_radiation(
        self,
        *,
        station: str = "KP",
        year: str | int = "ALL",
    ) -> DownloadedResource:
        station = station.upper()
        if station not in self.VALID_SOLAR_STATIONS:
            raise ValueError("station must be KP (King's Park) or KSC (Kau Sai Chau)")

        year_text = str(year).upper()
        if year_text != "ALL":
            if not (year_text.isdigit() and len(year_text) == 4):
                raise ValueError("year must be a four-digit year or ALL")

        url = self.DAILY_SOLAR_CSV_TEMPLATE.format(
            station=station,
            year=year_text,
        )
        return self.http.get(url)

    @staticmethod
    def parse_current_weather(payload: dict[str, Any]) -> dict[str, pd.DataFrame]:
        """Convert the current-weather JSON into tidy tables."""
        tables: dict[str, pd.DataFrame] = {}

        for key in ("temperature", "humidity", "rainfall", "uvindex"):
            block = payload.get(key)
            if not isinstance(block, dict):
                continue

            rows = block.get("data", [])
            if not isinstance(rows, list) or not rows:
                continue

            frame = pd.json_normalize(rows)
            for metadata_key in (
                "recordTime",
                "startTime",
                "endTime",
                "updateTime",
            ):
                if metadata_key in block:
                    frame[metadata_key] = block[metadata_key]
            tables[key] = frame

        summary = {
            "updateTime": payload.get("updateTime"),
            "iconUpdateTime": payload.get("iconUpdateTime"),
            "warningMessage": payload.get("warningMessage"),
            "tcmessage": payload.get("tcmessage"),
        }
        tables["summary"] = pd.DataFrame([summary])
        return tables

    @staticmethod
    def parse_nine_day_forecast(payload: dict[str, Any]) -> pd.DataFrame:
        rows = payload.get("weatherForecast", [])
        if not isinstance(rows, list):
            raise OpenDataError("Unexpected HKO forecast response structure.")
        frame = pd.json_normalize(rows)
        frame["updateTime"] = payload.get("updateTime")
        return frame

    @staticmethod
    def parse_latest_solar_radiation(csv_text: str) -> pd.DataFrame:
        frame = pd.read_csv(StringIO(csv_text))
        frame.columns = [column.strip() for column in frame.columns]

        rename_map = {
            "Date time": "timestamp_hkt",
            "Automatic Weather Station": "station",
            "Global Solar Radiation(watt/square meter)": "global_solar_wm2",
            "Direct Solar Radiation(watt/square meter)": "direct_solar_wm2",
            "Diffuse Radiation(watt/square meter)": "diffuse_solar_wm2",
        }
        frame = frame.rename(columns=rename_map)

        required = {
            "timestamp_hkt",
            "station",
            "global_solar_wm2",
            "direct_solar_wm2",
            "diffuse_solar_wm2",
        }
        missing = required.difference(frame.columns)
        if missing:
            raise OpenDataError(
                "The HKO live solar CSV schema has changed. "
                f"Missing columns: {sorted(missing)}"
            )

        frame["timestamp_hkt"] = pd.to_datetime(
            frame["timestamp_hkt"].astype(str),
            format="%Y%m%d%H%M",
            errors="coerce",
        )
        numeric_columns = [
            "global_solar_wm2",
            "direct_solar_wm2",
            "diffuse_solar_wm2",
        ]
        for column in numeric_columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame

    @staticmethod
    def parse_daily_solar_radiation(csv_text: str) -> pd.DataFrame:
        """Parse the HKO historical daily solar CSV without assuming a fixed year."""
        frame = pd.read_csv(StringIO(csv_text))
        frame.columns = [str(column).strip() for column in frame.columns]
        frame = frame.dropna(how="all")
        return frame
