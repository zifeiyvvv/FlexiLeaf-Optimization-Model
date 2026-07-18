"""Solar station selection and observation extraction."""

from __future__ import annotations

from typing import Any

import pandas as pd
from pyproj import Geod


_GEOD = Geod(ellps="WGS84")

# Coordinates published by the Hong Kong Observatory.
SOLAR_STATIONS = {
    "KP": {
        "station_code": "KP",
        "station_name": "King's Park",
        "latitude": 22 + 18 / 60 + 43 / 3600,
        "longitude": 114 + 10 / 60 + 22 / 3600,
    },
    "KSC": {
        "station_code": "KSC",
        "station_name": "Kau Sai Chau",
        "latitude": 22 + 22 / 60 + 13 / 3600,
        "longitude": 114 + 18 / 60 + 45 / 3600,
    },
}


def _distance_m(
    longitude_1: float,
    latitude_1: float,
    longitude_2: float,
    latitude_2: float,
) -> float:
    _, _, distance = _GEOD.inv(
        longitude_1,
        latitude_1,
        longitude_2,
        latitude_2,
    )
    return float(distance)


def choose_nearest_solar_station(
    *,
    longitude: float,
    latitude: float,
) -> dict[str, Any]:
    rows = []
    for station in SOLAR_STATIONS.values():
        row = dict(station)
        row["distance_to_site_m"] = _distance_m(
            longitude,
            latitude,
            station["longitude"],
            station["latitude"],
        )
        rows.append(row)
    return min(rows, key=lambda item: item["distance_to_site_m"])


def _normalise_station_name(value: str) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace("’", "'")
        .replace("`", "'")
    )


def select_solar_observation(
    solar_frame: pd.DataFrame,
    station_code: str,
) -> dict[str, Any]:
    station_code = station_code.upper()
    if station_code not in SOLAR_STATIONS:
        raise ValueError("station_code must be KP or KSC")

    target = _normalise_station_name(
        SOLAR_STATIONS[station_code]["station_name"]
    )
    matches = solar_frame[
        solar_frame["station"].map(_normalise_station_name) == target
    ]
    if matches.empty:
        available = sorted(solar_frame["station"].astype(str).unique())
        raise ValueError(
            f"Solar station {station_code} was not present. "
            f"Available stations: {available}"
        )

    row = matches.iloc[0].to_dict()
    row["station_code"] = station_code
    return row
