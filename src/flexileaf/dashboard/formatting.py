"""Human-readable labels used by the interactive dashboard."""

from __future__ import annotations

from typing import Any

import math


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def _number(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return numeric if math.isfinite(numeric) else default


def format_location_option(record: dict[str, Any]) -> str:
    rank = int(_number(record.get("candidate_rank"), 0))
    name = (
        _clean_text(record.get("name_en"))
        or _clean_text(record.get("name_zh"))
        or "Unnamed location"
    )
    address = (
        _clean_text(record.get("address_en"))
        or _clean_text(record.get("address_zh"))
    )
    district = (
        _clean_text(record.get("district_en"))
        or _clean_text(record.get("district_zh"))
    )

    details = " · ".join(part for part in (address, district) if part)
    return f"#{rank} — {name}" + (f" — {details}" if details else "")


def format_building_option(record: dict[str, Any]) -> str:
    rank = int(_number(record.get("building_rank"), 0))
    name = _clean_text(record.get("building_name")) or "Unnamed building"
    distance_m = _number(record.get("distance_to_query_m"))
    area_m2 = _number(record.get("estimated_total_pv_area_m2"))
    power_kw = _number(record.get("estimated_total_current_power_kw"))

    return (
        f"#{rank} — {name} — {distance_m:,.0f} m — "
        f"{area_m2:,.0f} m² — {power_kw:,.1f} kW"
    )
