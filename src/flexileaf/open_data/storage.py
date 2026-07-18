"""Storage helpers that preserve raw files and provenance metadata."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import json
import re

from .http_client import DownloadedResource


HK_TIMEZONE = ZoneInfo("Asia/Hong_Kong")


def _safe_name(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "_", value)
    return value.strip("_") or "resource"


class OpenDataStore:
    """Write immutable raw downloads and replaceable processed outputs."""

    def __init__(self, root: str | Path = "data") -> None:
        self.root = Path(root)

    @staticmethod
    def timestamp() -> str:
        return datetime.now(HK_TIMEZONE).strftime("%Y%m%dT%H%M%S%z")

    def save_raw(
        self,
        *,
        provider: str,
        dataset: str,
        extension: str,
        resource: DownloadedResource,
        request_parameters: dict[str, Any] | None = None,
    ) -> Path:
        timestamp = self.timestamp()
        provider_name = _safe_name(provider)
        dataset_name = _safe_name(dataset)
        extension = extension.lstrip(".")

        directory = self.root / "raw" / provider_name / dataset_name
        directory.mkdir(parents=True, exist_ok=True)

        data_path = directory / f"{timestamp}.{extension}"
        data_path.write_bytes(resource.content)

        metadata = {
            "provider": provider,
            "dataset": dataset,
            "source_url": resource.url,
            "downloaded_at_hkt": timestamp,
            "http_status": resource.status_code,
            "content_type": resource.content_type,
            "request_parameters": request_parameters or {},
            "raw_file": data_path.name,
        }
        metadata_path = directory / f"{timestamp}.meta.json"
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return data_path

    def processed_path(
        self,
        *,
        provider: str,
        dataset: str,
        filename: str,
    ) -> Path:
        directory = (
            self.root
            / "processed"
            / _safe_name(provider)
            / _safe_name(dataset)
        )
        directory.mkdir(parents=True, exist_ok=True)
        return directory / filename
