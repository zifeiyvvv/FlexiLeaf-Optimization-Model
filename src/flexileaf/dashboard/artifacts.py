"""Load a completed site-analysis run and its provenance files."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import pandas as pd


_REQUIRED_FILES = {
    "summary": "site_summary.json",
    "candidates": "location_candidates.csv",
    "solar": "solar_observations.csv",
    "buildings": "building_analysis.csv",
    "top_buildings": "top_buildings.csv",
    "geojson": "analysed_buildings.geojson",
}


def _read_raw_metadata(raw_path: str | Path) -> dict[str, Any] | None:
    path = Path(raw_path)
    metadata_path = path.with_suffix(".meta.json")
    if not metadata_path.exists():
        return None
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_run_artifacts(run_directory: str | Path) -> dict[str, Any]:
    directory = Path(run_directory)
    if not directory.exists():
        raise FileNotFoundError(f"Run directory does not exist: {directory}")

    paths = {
        key: directory / filename
        for key, filename in _REQUIRED_FILES.items()
    }
    missing = [
        str(path)
        for path in paths.values()
        if not path.exists()
    ]
    if missing:
        raise FileNotFoundError(
            "The site-analysis run is incomplete. Missing files: "
            + ", ".join(missing)
        )

    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    geojson = json.loads(paths["geojson"].read_text(encoding="utf-8"))

    raw_metadata: dict[str, Any] = {}
    for key, raw_path in (summary.get("raw_sources") or {}).items():
        metadata = _read_raw_metadata(raw_path)
        if metadata is not None:
            raw_metadata[key] = metadata

    return {
        "directory": directory,
        "summary": summary,
        "candidates": pd.read_csv(paths["candidates"]),
        "solar": pd.read_csv(paths["solar"]),
        "buildings": pd.read_csv(paths["buildings"]),
        "top_buildings": pd.read_csv(paths["top_buildings"]),
        "geojson": geojson,
        "raw_metadata": raw_metadata,
        "paths": paths,
    }
