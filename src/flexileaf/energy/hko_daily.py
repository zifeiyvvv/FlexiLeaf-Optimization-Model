"""Parse the official HKO daily global-solar-radiation CSV format."""

from __future__ import annotations

from io import StringIO
from typing import Any

import pandas as pd


def parse_hko_daily_solar_csv(csv_text: str) -> pd.DataFrame:
    """Return a tidy daily solar table.

    HKO files currently start with two bilingual title rows followed by:
    Year, Month, Day, Value and data completeness. The parser locates the
    header rather than assuming a fixed row number.
    """
    lines = csv_text.replace("\r\n", "\n").splitlines()
    header_index = None
    for index, line in enumerate(lines):
        compact = line.replace("\ufeff", "").strip()
        if "Year" in compact and "Month" in compact and "Day" in compact:
            header_index = index
            break
    if header_index is None:
        raise ValueError("Unable to locate the HKO daily solar CSV header.")

    frame = pd.read_csv(StringIO("\n".join(lines[header_index:])))
    if frame.shape[1] < 5:
        raise ValueError("Unexpected HKO daily solar CSV column count.")

    frame = frame.iloc[:, :5].copy()
    frame.columns = [
        "year",
        "month",
        "day",
        "global_solar_mj_m2",
        "data_completeness",
    ]

    for column in ("year", "month", "day"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["global_solar_mj_m2"] = pd.to_numeric(
        frame["global_solar_mj_m2"],
        errors="coerce",
    )
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
    frame = frame.dropna(
        subset=["date", "global_solar_mj_m2"]
    ).copy()
    frame["year"] = frame["year"].astype(int)
    frame["month"] = frame["month"].astype(int)
    frame["day"] = frame["day"].astype(int)
    frame = frame.sort_values("date").reset_index(drop=True)
    return frame[
        [
            "date",
            "year",
            "month",
            "day",
            "global_solar_mj_m2",
            "data_completeness",
        ]
    ]


def latest_complete_daily_solar(
    frame: pd.DataFrame,
) -> dict[str, Any]:
    """Select the most recent complete positive HKO daily observation."""
    required = {
        "date",
        "global_solar_mj_m2",
        "data_completeness",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(
            f"Daily solar frame is missing columns: {sorted(missing)}"
        )

    complete = frame[
        frame["global_solar_mj_m2"].notna()
        & (frame["global_solar_mj_m2"] >= 0)
        & (
            frame["data_completeness"]
            .astype(str)
            .str.upper()
            .eq("C")
        )
    ]
    if complete.empty:
        raise ValueError("No complete HKO daily solar observation is available.")

    row = complete.sort_values("date").iloc[-1].to_dict()
    if isinstance(row.get("date"), pd.Timestamp):
        row["date"] = row["date"].date().isoformat()
    return row
