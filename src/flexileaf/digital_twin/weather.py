"""Build a deterministic 8,760-hour weather series from official daily data."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any
import math

import numpy as np
import pandas as pd


MONTHLY_NORMAL_MEAN_TEMP_C = {
    1: 16.5, 2: 17.1, 3: 19.5, 4: 23.0,
    5: 26.3, 6: 28.3, 7: 28.9, 8: 28.7,
    9: 27.9, 10: 25.7, 11: 22.2, 12: 18.2,
}


def parse_hko_daily_csv(
    path: str | Path,
    *,
    value_name: str,
) -> pd.DataFrame:
    text = Path(path).read_text(encoding="utf-8-sig")
    lines = text.replace("\r\n", "\n").splitlines()
    header_index = None
    for index, line in enumerate(lines):
        if "Year" in line and "Month" in line and "Day" in line:
            header_index = index
            break
    if header_index is None:
        raise ValueError(f"Header not found in {path}")

    frame = pd.read_csv(StringIO("\n".join(lines[header_index:])))
    frame = frame.iloc[:, :5].copy()
    frame.columns = [
        "year", "month", "day", value_name, "data_completeness"
    ]
    for col in ("year", "month", "day", value_name):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["data_completeness"] = (
        frame["data_completeness"].astype(str).str.strip()
    )
    frame["date"] = pd.to_datetime(
        {
            "year": frame["year"],
            "month": frame["month"],
            "day": frame["day"],
        },
        errors="coerce",
    )
    frame = frame.dropna(subset=["date", value_name]).copy()
    return frame[
        ["date", value_name, "data_completeness"]
    ].sort_values("date").reset_index(drop=True)


def combine_daily_weather(
    *,
    solar_path: str | Path,
    humidity_path: str | Path,
    sunshine_path: str | Path,
    simulation_year: int,
) -> pd.DataFrame:
    solar = parse_hko_daily_csv(
        solar_path,
        value_name="global_solar_mj_m2",
    )
    humidity = parse_hko_daily_csv(
        humidity_path,
        value_name="mean_relative_humidity_percent",
    )
    sunshine = parse_hko_daily_csv(
        sunshine_path,
        value_name="bright_sunshine_hours",
    )

    frame = solar.merge(humidity, on="date", how="outer").merge(
        sunshine, on="date", how="outer"
    )
    frame = frame[
        frame["date"].dt.year == simulation_year
    ].sort_values("date").reset_index(drop=True)

    expected_dates = pd.DataFrame(
        {
            "date": pd.date_range(
                f"{simulation_year}-01-01",
                f"{simulation_year}-12-31",
                freq="D",
            )
        }
    )
    frame = expected_dates.merge(frame, on="date", how="left")
    value_columns = [
        "global_solar_mj_m2",
        "mean_relative_humidity_percent",
        "bright_sunshine_hours",
    ]
    for column in value_columns:
        frame[column] = frame[column].interpolate(
            limit_direction="both"
        )
    if frame[value_columns].isna().any().any():
        raise ValueError("Daily weather inputs contain unresolved gaps.")

    frame["solar_source_type"] = "official_open_data"
    frame["humidity_source_type"] = "official_open_data"
    frame["sunshine_source_type"] = "official_open_data"
    return frame


def _solar_geometry(
    latitude_deg: float,
    day_of_year: int,
    hour_decimal: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    lat = math.radians(latitude_deg)
    declination = math.radians(
        23.45 * math.sin(
            2 * math.pi * (284 + day_of_year) / 365.0
        )
    )
    hour_angle = np.radians(15.0 * (hour_decimal - 12.0))
    sin_elevation = (
        math.sin(lat) * math.sin(declination)
        + math.cos(lat) * math.cos(declination) * np.cos(hour_angle)
    )
    sin_elevation = np.clip(sin_elevation, 0.0, 1.0)
    elevation = np.arcsin(sin_elevation)

    # Solar azimuth from north, clockwise.
    azimuth = np.full_like(hour_decimal, 180.0, dtype=float)
    valid = sin_elevation > 1e-8
    cos_elev = np.maximum(np.cos(elevation[valid]), 1e-8)
    sin_az = -np.sin(hour_angle[valid]) * math.cos(declination) / cos_elev
    cos_az = (
        math.sin(declination)
        - np.sin(elevation[valid]) * math.sin(lat)
    ) / (cos_elev * math.cos(lat))
    azimuth[valid] = (
        np.degrees(np.arctan2(sin_az, cos_az)) + 360.0
    ) % 360.0

    cos_h0 = -math.tan(lat) * math.tan(declination)
    cos_h0 = min(max(cos_h0, -1.0), 1.0)
    daylight_hours = 2 * math.degrees(math.acos(cos_h0)) / 15.0
    return sin_elevation, azimuth, daylight_hours


def build_hourly_weather(
    daily: pd.DataFrame,
    *,
    latitude: float,
    random_seed: int,
    annual_mean_temperature_target_c: float,
) -> pd.DataFrame:
    rng = np.random.default_rng(random_seed)
    daily = daily.copy()
    daily["month"] = daily["date"].dt.month
    daily["day_of_year"] = daily["date"].dt.dayofyear

    monthly_group = daily.groupby("month")[
        "global_solar_mj_m2"
    ]
    solar_month_mean = monthly_group.transform("mean")
    solar_month_std = monthly_group.transform("std").replace(0, 1)
    solar_anomaly = (
        daily["global_solar_mj_m2"] - solar_month_mean
    ) / solar_month_std

    humidity_month_mean = daily.groupby("month")[
        "mean_relative_humidity_percent"
    ].transform("mean")
    humidity_anomaly = (
        daily["mean_relative_humidity_percent"]
        - humidity_month_mean
    )

    noise = pd.Series(
        rng.normal(0.0, 0.9, len(daily))
    ).rolling(3, center=True, min_periods=1).mean().to_numpy()

    daily["mean_temperature_c"] = (
        daily["month"].map(MONTHLY_NORMAL_MEAN_TEMP_C).astype(float)
        + 0.8
        + 0.30 * solar_anomaly.to_numpy()
        - 0.025 * humidity_anomaly.to_numpy()
        + noise
    )
    daily["mean_temperature_c"] += (
        annual_mean_temperature_target_c
        - daily["mean_temperature_c"].mean()
    )

    rows: list[pd.DataFrame] = []
    hour_centres = np.arange(24, dtype=float) + 0.5

    for day_index, day in daily.iterrows():
        sin_elev, solar_azimuth, daylight_hours = _solar_geometry(
            latitude,
            int(day["day_of_year"]),
            hour_centres,
        )
        sunshine_fraction = float(
            np.clip(
                day["bright_sunshine_hours"]
                / max(daylight_hours, 0.1),
                0.0,
                1.0,
            )
        )

        shape_exponent = 1.05 + 1.45 * (1.0 - sunshine_fraction)
        weights = np.power(sin_elev, shape_exponent)

        day_rng = np.random.default_rng(
            random_seed + int(day["day_of_year"]) * 7919
        )
        cloud_noise = day_rng.normal(0.0, 1.0, 24)
        cloud_noise = np.convolve(
            cloud_noise,
            np.array([0.2, 0.6, 0.2]),
            mode="same",
        )
        modulation = np.clip(
            1.0
            + cloud_noise
            * 0.30
            * (1.0 - sunshine_fraction),
            0.10,
            1.80,
        )
        weights *= modulation
        weights[sin_elev <= 0] = 0.0

        daily_kwh_m2 = float(day["global_solar_mj_m2"]) / 3.6
        if weights.sum() > 0:
            hourly_energy_kwh_m2 = daily_kwh_m2 * weights / weights.sum()
        else:
            hourly_energy_kwh_m2 = np.zeros(24)
        ghi_wm2 = hourly_energy_kwh_m2 * 1000.0

        diffuse_fraction = np.clip(
            0.76 - 0.54 * sunshine_fraction,
            0.20,
            0.82,
        )
        dhi_wm2 = ghi_wm2 * diffuse_fraction
        beam_horizontal_wm2 = np.maximum(ghi_wm2 - dhi_wm2, 0.0)
        dni_wm2 = np.divide(
            beam_horizontal_wm2,
            sin_elev,
            out=np.zeros_like(beam_horizontal_wm2),
            where=sin_elev > 0.04,
        )
        dni_wm2 = np.clip(dni_wm2, 0.0, 1100.0)

        amplitude = (
            2.8
            + 2.5 * sunshine_fraction
            + 0.012
            * (80.0 - float(day["mean_relative_humidity_percent"]))
        )
        amplitude = float(np.clip(amplitude, 2.2, 6.5))
        temp_hourly = (
            float(day["mean_temperature_c"])
            + amplitude
            * np.sin(2 * np.pi * (hour_centres - 9.0) / 24.0)
        )
        rh_hourly = np.clip(
            float(day["mean_relative_humidity_percent"])
            + 8.0
            * np.cos(2 * np.pi * (hour_centres - 5.0) / 24.0),
            25.0,
            100.0,
        )

        timestamp = day["date"] + pd.to_timedelta(
            np.arange(24), unit="h"
        )
        rows.append(
            pd.DataFrame(
                {
                    "timestamp": timestamp,
                    "date": day["date"],
                    "hour": np.arange(24),
                    "month": int(day["month"]),
                    "day_of_year": int(day["day_of_year"]),
                    "weekday": timestamp.dayofweek,
                    "is_weekend": timestamp.dayofweek >= 5,
                    "global_solar_daily_mj_m2": float(
                        day["global_solar_mj_m2"]
                    ),
                    "bright_sunshine_hours": float(
                        day["bright_sunshine_hours"]
                    ),
                    "sunshine_fraction": sunshine_fraction,
                    "mean_relative_humidity_daily_percent": float(
                        day["mean_relative_humidity_percent"]
                    ),
                    "temperature_c": temp_hourly,
                    "relative_humidity_percent": rh_hourly,
                    "solar_elevation_sine": sin_elev,
                    "solar_azimuth_deg": solar_azimuth,
                    "global_horizontal_irradiance_wm2": ghi_wm2,
                    "diffuse_horizontal_irradiance_wm2": dhi_wm2,
                    "direct_normal_irradiance_wm2": dni_wm2,
                    "weather_source": (
                        "HKO 2025 daily GSR/RH/sunshine + "
                        "documented hourly disaggregation"
                    ),
                }
            )
        )

    hourly = pd.concat(rows, ignore_index=True)
    if len(hourly) != 8760:
        raise ValueError(f"Expected 8760 rows, received {len(hourly)}")

    daily_check = (
        hourly.groupby("date")[
            "global_horizontal_irradiance_wm2"
        ].sum()
        / 1000.0
        * 3.6
    )
    expected = daily.set_index("date")["global_solar_mj_m2"]
    maximum_error = float((daily_check - expected).abs().max())
    hourly.attrs["maximum_daily_solar_energy_error_mj_m2"] = maximum_error
    return hourly
