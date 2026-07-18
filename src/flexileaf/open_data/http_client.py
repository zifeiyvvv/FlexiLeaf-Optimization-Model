"""Shared HTTP client with retry, timeout and clear error handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class OpenDataError(RuntimeError):
    """Raised when a government open-data request cannot be completed."""


@dataclass(frozen=True)
class DownloadedResource:
    """A downloaded HTTP resource and its provenance metadata."""

    url: str
    status_code: int
    content_type: str
    content: bytes
    encoding: str | None

    def json(self) -> Any:
        try:
            return requests.models.complexjson.loads(self.text())
        except ValueError as exc:
            raise OpenDataError(
                f"The response from {self.url} is not valid JSON."
            ) from exc

    def text(self) -> str:
        """Decode bytes while tolerating common Hong Kong government encodings."""
        candidate_encodings = [
            self.encoding,
            "utf-8-sig",
            "utf-8",
            "big5",
            "cp950",
        ]
        for encoding in candidate_encodings:
            if not encoding:
                continue
            try:
                return self.content.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        return self.content.decode("utf-8", errors="replace")


class GovernmentHTTPClient:
    """HTTP client suitable for public government APIs.

    The client:
    - applies a finite timeout;
    - retries temporary server and rate-limit failures;
    - uses a descriptive User-Agent;
    - raises a single project-specific exception.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        user_agent: str = "FlexiLeaf-Student-Project/0.1",
        retries: int = 3,
        backoff_factor: float = 0.8,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json,text/csv,text/plain,*/*",
            }
        )

        retry_policy = Retry(
            total=retries,
            connect=retries,
            read=retries,
            status=retries,
            backoff_factor=backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_policy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> DownloadedResource:
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise OpenDataError(
                f"Unable to connect to the open-data service: {url}. "
                f"Original error: {exc}"
            ) from exc

        if not response.ok:
            body_preview = response.text[:300].replace("\n", " ")
            raise OpenDataError(
                f"Open-data request failed with HTTP {response.status_code}: "
                f"{response.url}. Response preview: {body_preview}"
            )

        return DownloadedResource(
            url=response.url,
            status_code=response.status_code,
            content_type=response.headers.get("Content-Type", ""),
            content=response.content,
            encoding=response.encoding,
        )
