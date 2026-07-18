"""Lands Department Location Search API connector."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import pandas as pd

from .http_client import DownloadedResource, GovernmentHTTPClient


class LandsDClient:
    """Search Hong Kong addresses, buildings, places and facilities."""

    LOCATION_SEARCH_URL = (
        "https://www.map.gov.hk/gs/api/v1.0.0/locationSearch"
    )

    def __init__(self, http_client: GovernmentHTTPClient | None = None) -> None:
        self.http = http_client or GovernmentHTTPClient()

    def search_location(self, query: str) -> DownloadedResource:
        query = query.strip()
        if not query:
            raise ValueError("query cannot be empty")
        return self.http.get(
            self.LOCATION_SEARCH_URL,
            params={"q": query},
        )

    @staticmethod
    def parse_location_results(payload: Any) -> pd.DataFrame:
        """Flatten the API response while tolerating future wrapper changes."""
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            records = None
            for key in ("results", "data", "locations", "result"):
                value = payload.get(key)
                if isinstance(value, list):
                    records = value
                    break
            if records is None:
                records = [payload]
        else:
            records = [{"value": payload}]

        return pd.json_normalize(records)
