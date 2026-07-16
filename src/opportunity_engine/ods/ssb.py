"""Statistics Norway (SSB) PxWebApi v2 connector for ODS.

The connector uses SSB's official PxWebApi v2 endpoints and normalizes table
metadata or JSON-stat2 data into ``SourceDocument`` evidence. Network access is
isolated behind an injectable transport so tests never call the live service.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .live_data import SourceDocument
from .models import ODSRequest


SSB_API_BASE = "https://data.ssb.no/api/pxwebapi/v2"
JsonTransport = Callable[[str, float], Any]


def _default_json_transport(url: str, timeout: float) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ODS-Opportunity-Engine/0.2",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS API base
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except HTTPError as exc:
        raise RuntimeError(f"SSB API returned HTTP {exc.code} for {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"SSB API request failed for {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"SSB API returned invalid JSON for {url}") from exc


@dataclass(frozen=True)
class SSBClient:
    """Small client for the official SSB PxWebApi v2."""

    language: str = "en"
    timeout: float = 15.0
    base_url: str = SSB_API_BASE
    transport: JsonTransport = _default_json_transport

    def __post_init__(self) -> None:
        if self.language not in {"en", "no", "nb", "nn"}:
            raise ValueError("unsupported SSB language")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if not self.base_url.startswith("https://"):
            raise ValueError("SSB base_url must use HTTPS")

    def search_tables(self, query: str, *, page_size: int = 10) -> tuple[dict[str, Any], ...]:
        if not query.strip():
            raise ValueError("SSB table query must not be empty")
        if not 1 <= page_size <= 1000:
            raise ValueError("page_size must be between 1 and 1000")
        params = urlencode(
            {"lang": self.language, "query": query, "pagesize": page_size, "pagenumber": 1}
        )
        payload = self.transport(f"{self.base_url}/tables?{params}", self.timeout)
        tables = payload.get("tables", payload) if isinstance(payload, dict) else payload
        if not isinstance(tables, list):
            raise RuntimeError("SSB table search returned an unexpected payload")
        return tuple(item for item in tables if isinstance(item, dict))

    def get_table_info(self, table_id: str) -> dict[str, Any]:
        table_id = self._validated_table_id(table_id)
        payload = self.transport(
            f"{self.base_url}/tables/{table_id}?{urlencode({'lang': self.language})}",
            self.timeout,
        )
        if not isinstance(payload, dict):
            raise RuntimeError("SSB table info returned an unexpected payload")
        return payload

    def get_metadata(self, table_id: str) -> dict[str, Any]:
        table_id = self._validated_table_id(table_id)
        payload = self.transport(
            f"{self.base_url}/tables/{table_id}/metadata?{urlencode({'lang': self.language})}",
            self.timeout,
        )
        if not isinstance(payload, dict):
            raise RuntimeError("SSB metadata returned an unexpected payload")
        return payload

    def get_default_data(self, table_id: str) -> dict[str, Any]:
        """Fetch SSB's default extraction in JSON-stat2 format."""

        table_id = self._validated_table_id(table_id)
        params = urlencode({"lang": self.language, "outputFormat": "json-stat2"})
        payload = self.transport(
            f"{self.base_url}/tables/{table_id}/data?{params}", self.timeout
        )
        if not isinstance(payload, dict):
            raise RuntimeError("SSB table data returned an unexpected payload")
        return payload

    @staticmethod
    def _validated_table_id(table_id: str) -> str:
        normalized = table_id.strip()
        if len(normalized) != 5 or not normalized.isdigit():
            raise ValueError("SSB table_id must contain exactly five digits")
        return normalized


@dataclass(frozen=True)
class SSBConnector:
    """Normalize configured SSB tables into ODS source documents.

    The connector is deliberately table-driven. A later discovery layer may search
    tables dynamically, while this class remains reusable and deterministic.
    """

    table_ids: tuple[str, ...]
    client: SSBClient = SSBClient()
    include_data: bool = True
    name: str = "ssb_pxweb_v2"

    def __post_init__(self) -> None:
        if not self.table_ids:
            raise ValueError("SSBConnector requires at least one table_id")
        for table_id in self.table_ids:
            self.client._validated_table_id(table_id)

    def fetch(self, request: ODSRequest) -> tuple[SourceDocument, ...]:
        documents: list[SourceDocument] = []
        for table_id in self.table_ids:
            info = self.client.get_table_info(table_id)
            data = self.client.get_default_data(table_id) if self.include_data else None
            title = str(info.get("label") or info.get("title") or f"SSB table {table_id}")
            summary = self._summary_text(info, data, request)
            documents.append(
                SourceDocument(
                    document_id=f"ssb-table-{table_id}",
                    source_name="Statistics Norway (SSB)",
                    source_type="official_statistics",
                    title=title,
                    text=summary,
                    url=f"https://www.ssb.no/en/statbank/table/{table_id}",
                    country="Norway",
                    metadata={
                        "table_id": table_id,
                        "api_version": "PxWebApi v2",
                        "first_period": info.get("firstPeriod"),
                        "last_period": info.get("lastPeriod"),
                        "variable_names": info.get("variableNames", ()),
                        "json_stat2": data,
                        "request_subject": request.subject,
                    },
                )
            )
        return tuple(documents)

    @staticmethod
    def _summary_text(
        info: dict[str, Any], data: dict[str, Any] | None, request: ODSRequest
    ) -> str:
        parts = [
            str(info.get("label") or info.get("title") or "Official SSB statistical table"),
            f"Target analysis subject: {request.subject}.",
        ]
        first_period = info.get("firstPeriod")
        last_period = info.get("lastPeriod")
        if first_period or last_period:
            parts.append(f"Available period: {first_period or '?'} to {last_period or '?' }.")
        variables = info.get("variableNames")
        if isinstance(variables, list) and variables:
            parts.append("Variables: " + ", ".join(str(value) for value in variables) + ".")
        if data is not None:
            values = data.get("value")
            value_count = len(values) if isinstance(values, list) else 0
            parts.append(f"Default JSON-stat2 extraction contains {value_count} values.")
        return " ".join(parts)
