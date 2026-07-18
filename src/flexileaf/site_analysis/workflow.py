"""End-to-end location, building and live solar site-analysis workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import json
import re

import pandas as pd

from flexileaf.open_data import CSDIBuildingClient, HKOClient, LandsDClient
from flexileaf.open_data.http_client import GovernmentHTTPClient
from flexileaf.open_data.storage import OpenDataStore

from .buildings import analyse_buildings
from .geo import make_wgs84_bbox_from_hk1980, normalise_geojson_axis_order
from .location import location_candidates, select_location_candidate
from .pv_model import estimate_building_pv
from .solar import choose_nearest_solar_station, select_solar_observation


HK_TZ = ZoneInfo("Asia/Hong_Kong")


@dataclass(frozen=True)
class SiteAnalysisConfig:
    search_radius_m: float = 250.0
    max_buildings: int = 300
    top_buildings: int = 15
    default_building_height_m: float = 30.0
    roof_usable_ratio: float = 0.65
    facade_usable_ratio: float = 0.25
    module_efficiency: float = 0.20
    performance_ratio: float = 0.82
    roof_orientation_factor: float = 0.90
    facade_orientation_factor: float = 0.55

    @classmethod
    def from_json(cls, path: str | Path) -> "SiteAnalysisConfig":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**payload)


def _slug(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:50] or "site"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _enrich_geojson(
    payload: dict[str, Any],
    building_frame: pd.DataFrame,
) -> dict[str, Any]:
    normalised = normalise_geojson_axis_order(payload)
    features = normalised.get("features", [])
    if not isinstance(features, list) or building_frame.empty:
        return normalised

    metrics_by_index = {
        int(row["feature_index"]): row
        for row in building_frame.to_dict(orient="records")
    }
    for feature_index, feature in enumerate(features):
        if not isinstance(feature, dict):
            continue
        metrics = metrics_by_index.get(feature_index)
        if metrics is None:
            continue
        properties = feature.setdefault("properties", {})
        properties.update(
            {
                "flexileaf_building_rank": metrics.get("building_rank"),
                "flexileaf_distance_to_query_m": metrics.get(
                    "distance_to_query_m"
                ),
                "flexileaf_estimated_total_pv_area_m2": metrics.get(
                    "estimated_total_pv_area_m2"
                ),
                "flexileaf_estimated_current_power_kw": metrics.get(
                    "estimated_total_current_power_kw"
                ),
            }
        )
    return normalised


def run_site_analysis(
    *,
    query: str,
    candidate_index: int = 0,
    config: SiteAnalysisConfig | None = None,
    data_root: str | Path = "data",
    output_root: str | Path | None = None,
    http_client: GovernmentHTTPClient | None = None,
) -> dict[str, Any]:
    """Run the first complete FlexiLeaf open-data analytical workflow."""
    config = config or SiteAnalysisConfig()
    http = http_client or GovernmentHTTPClient(
        user_agent="FlexiLeaf-Student-Project/0.2"
    )
    store = OpenDataStore(data_root)

    landsd = LandsDClient(http)
    csdi = CSDIBuildingClient(http)
    hko = HKOClient(http)

    # 1. Resolve location.
    location_resource = landsd.search_location(query)
    raw_location_path = store.save_raw(
        provider="landsd",
        dataset="location_search",
        extension="json",
        resource=location_resource,
        request_parameters={"q": query},
    )
    location_payload = location_resource.json()
    candidate_frame = location_candidates(location_payload)
    selected_location = select_location_candidate(
        candidate_frame,
        candidate_index,
    )

    # 2. Build a metric radius and convert it to a WFS EPSG:4326 BBOX.
    bbox = make_wgs84_bbox_from_hk1980(
        centre_x=selected_location["x_hk1980"],
        centre_y=selected_location["y_hk1980"],
        radius_m=config.search_radius_m,
    )

    # 3. Download building polygons.
    building_resource = csdi.fetch_buildings_by_bbox(
        **bbox,
        count=config.max_buildings,
        start_index=0,
    )
    raw_building_path = store.save_raw(
        provider="csdi",
        dataset="building_footprints",
        extension="geojson",
        resource=building_resource,
        request_parameters={**bbox, "count": config.max_buildings},
    )
    building_payload = building_resource.json()
    building_frame = analyse_buildings(
        building_payload,
        query_x_hk1980=selected_location["x_hk1980"],
        query_y_hk1980=selected_location["y_hk1980"],
        default_height_m=config.default_building_height_m,
        roof_usable_ratio=config.roof_usable_ratio,
        facade_usable_ratio=config.facade_usable_ratio,
    )
    if building_frame.empty:
        raise ValueError(
            "No usable building polygons were returned for this search area."
        )

    # 4. Obtain current solar radiation and select nearest official station.
    solar_resource = hko.fetch_latest_solar_radiation()
    raw_solar_path = store.save_raw(
        provider="hko",
        dataset="latest_solar_radiation",
        extension="csv",
        resource=solar_resource,
    )
    solar_frame = hko.parse_latest_solar_radiation(solar_resource.text())
    station = choose_nearest_solar_station(
        longitude=selected_location["longitude"],
        latitude=selected_location["latitude"],
    )
    solar_observation = select_solar_observation(
        solar_frame,
        station["station_code"],
    )

    irradiance_wm2 = float(solar_observation["global_solar_wm2"])
    pv_rows = []
    for building in building_frame.to_dict(orient="records"):
        pv_rows.append(
            estimate_building_pv(
                building,
                irradiance_wm2=irradiance_wm2,
                module_efficiency=config.module_efficiency,
                performance_ratio=config.performance_ratio,
                roof_orientation_factor=config.roof_orientation_factor,
                facade_orientation_factor=config.facade_orientation_factor,
            )
        )
    pv_frame = pd.DataFrame(pv_rows)
    building_frame = pd.concat(
        [building_frame.reset_index(drop=True), pv_frame],
        axis=1,
    )

    top_buildings = building_frame.head(config.top_buildings).copy()
    selected_building = top_buildings.iloc[0].to_dict()

    run_timestamp = datetime.now(HK_TZ).strftime("%Y%m%dT%H%M%S%z")
    run_id = f"{_slug(query)}-{run_timestamp}"
    if output_root is None:
        run_directory = (
            Path(data_root) / "processed" / "site_analysis" / run_id
        )
    else:
        run_directory = Path(output_root) / run_id
    run_directory.mkdir(parents=True, exist_ok=True)

    candidate_frame.to_csv(
        run_directory / "location_candidates.csv",
        index=False,
        encoding="utf-8-sig",
    )
    solar_frame.to_csv(
        run_directory / "solar_observations.csv",
        index=False,
        encoding="utf-8-sig",
    )
    building_frame.to_csv(
        run_directory / "building_analysis.csv",
        index=False,
        encoding="utf-8-sig",
    )
    top_buildings.to_csv(
        run_directory / "top_buildings.csv",
        index=False,
        encoding="utf-8-sig",
    )

    enriched_geojson = _enrich_geojson(
        building_payload,
        building_frame,
    )
    (run_directory / "analysed_buildings.geojson").write_text(
        json.dumps(
            _json_safe(enriched_geojson),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = {
        "run_id": run_id,
        "query": query,
        "generated_at_hkt": run_timestamp,
        "config": asdict(config),
        "selected_location": _json_safe(selected_location),
        "wfs_bbox": bbox,
        "nearest_solar_station": _json_safe(station),
        "solar_observation": _json_safe(solar_observation),
        "selected_building": _json_safe(selected_building),
        "building_count": int(len(building_frame)),
        "raw_sources": {
            "location": str(raw_location_path),
            "buildings": str(raw_building_path),
            "solar": str(raw_solar_path),
        },
        "method_notes": {
            "location_coordinates": (
                "LandsD Location Search x/y are transformed from "
                "Hong Kong 1980 Grid (EPSG:2326) to WGS84."
            ),
            "roof_area": (
                "Building footprint multiplied by the configured usable ratio."
            ),
            "facade_area": (
                "Building perimeter multiplied by height and facade usable "
                "ratio; this is a planning assumption, not a facade survey."
            ),
            "solar": (
                "Latest provisional horizontal global solar radiation from "
                "the nearest of the two HKO solar stations."
            ),
            "pv_power": (
                "Planning-level instantaneous estimate, not field-measured "
                "generation and not a replacement for detailed shading or "
                "engineering assessment."
            ),
        },
    }
    summary_path = run_directory / "site_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary["output_directory"] = str(run_directory)
    summary["summary_path"] = str(summary_path)
    return summary
