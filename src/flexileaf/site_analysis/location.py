"""Normalise Lands Department location-search results."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .geo import hk1980_to_wgs84


_LOCATION_COLUMNS = [
    "candidate_rank",
    "name_en",
    "name_zh",
    "address_en",
    "address_zh",
    "district_en",
    "district_zh",
    "x_hk1980",
    "y_hk1980",
    "longitude",
    "latitude",
]


def _records_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]

    if isinstance(payload, dict):
        for key in ("results", "data", "locations", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return [
                    record for record in value if isinstance(record, dict)
                ]
        return [payload]

    return []


def location_candidates(payload: Any) -> pd.DataFrame:
    """Convert LandsD HK1980 x/y results into a ranked WGS84 table."""
    rows = []
    for rank, record in enumerate(_records_from_payload(payload)):
        x = record.get("x")
        y = record.get("y")
        try:
            x_value = float(x)
            y_value = float(y)
        except (TypeError, ValueError):
            continue

        longitude, latitude = hk1980_to_wgs84(x_value, y_value)
        rows.append(
            {
                "candidate_rank": rank,
                "name_en": record.get("nameEN", ""),
                "name_zh": record.get("nameZH", ""),
                "address_en": record.get("addressEN", ""),
                "address_zh": record.get("addressZH", ""),
                "district_en": record.get("districtEN", ""),
                "district_zh": record.get("districtZH", ""),
                "x_hk1980": x_value,
                "y_hk1980": y_value,
                "longitude": longitude,
                "latitude": latitude,
            }
        )

    return pd.DataFrame(rows, columns=_LOCATION_COLUMNS)


def select_location_candidate(
    candidates: pd.DataFrame,
    candidate_index: int = 0,
) -> dict[str, Any]:
    """Select a location by displayed row position, not DataFrame label."""
    if candidates.empty:
        raise ValueError("The location API returned no usable coordinates.")
    if not (0 <= candidate_index < len(candidates)):
        raise ValueError(
            f"candidate_index must be between 0 and {len(candidates) - 1}"
        )
    return candidates.iloc[candidate_index].to_dict()
