"""CSDI OGC WFS connector for Lands Department building footprints."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .http_client import DownloadedResource, GovernmentHTTPClient, OpenDataError


class CSDIBuildingClient:
    """Retrieve building polygons and attributes from the CSDI WFS service."""

    BUILDING_WFS_URL = (
        "https://portal.csdi.gov.hk/server/services/common/"
        "landsd_rcd_1637211194312_35158/MapServer/WFSServer"
    )

    def __init__(self, http_client: GovernmentHTTPClient | None = None) -> None:
        self.http = http_client or GovernmentHTTPClient()

    def fetch_buildings_by_bbox(
        self,
        *,
        south_lat: float,
        west_lon: float,
        north_lat: float,
        east_lon: float,
        count: int = 100,
        start_index: int = 0,
    ) -> DownloadedResource:
        """Fetch building features inside a Hong Kong bounding box.

        The CSDI documentation's EPSG:4326 WFS examples use this order:
        south latitude, west longitude, north latitude, east longitude.
        """
        if south_lat >= north_lat:
            raise ValueError("south_lat must be smaller than north_lat")
        if west_lon >= east_lon:
            raise ValueError("west_lon must be smaller than east_lon")
        if not (1 <= count <= 10_000):
            raise ValueError("count must be between 1 and 10,000")
        if start_index < 0:
            raise ValueError("start_index cannot be negative")

        bbox = f"{south_lat},{west_lon},{north_lat},{east_lon}"
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": "Building",
            "outputFormat": "GeoJSON",
            "srsName": "EPSG:4326",
            "bbox": bbox,
            "count": count,
            "resultType": "results",
            "startIndex": start_index,
        }
        return self.http.get(self.BUILDING_WFS_URL, params=params)

    @staticmethod
    def parse_building_summary(payload: dict[str, Any]) -> pd.DataFrame:
        features = payload.get("features")
        if not isinstance(features, list):
            raise OpenDataError(
                "Unexpected CSDI GeoJSON response: 'features' is missing."
            )

        rows = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            properties = feature.get("properties") or {}
            geometry = feature.get("geometry") or {}
            rows.append(
                {
                    "feature_id": feature.get("id"),
                    "geometry_type": geometry.get("type"),
                    **properties,
                }
            )
        return pd.json_normalize(rows)
