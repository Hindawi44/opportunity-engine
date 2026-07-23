"""Diagnostic Brave transport wrapper for V2.7.2.4.4.

This module observes the HTTP transport and response pipeline only. It does not
change opportunity selection, investment scoring, evidence acceptance, or query
construction logic.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import socket
import ssl
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from opportunity_engine.ods.brave_search import parse_brave_results


@dataclass(slots=True)
class BraveTransportRecord:
    query: str
    request_sent: bool = False
    endpoint: str = ""
    http_method: str = "GET"
    headers_present: tuple[str, ...] = ()
    request_timestamp: str | None = None
    http_status: int | None = None
    response_time_ms: int | None = None
    response_size_bytes: int | None = None
    results_count: int = 0
    body_preview: str = ""
    content_type: str | None = None
    stage_reached: str = "prepare_request"
    transport_error: str | None = None
    parse_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditedBraveSearchProvider:
    """Drop-in Brave provider that records every transport and parsing stage."""

    def __init__(self, provider: Any) -> None:
        self.provider = provider
        self.records: list[BraveTransportRecord] = []
        self._request_count = 0
        self._cache_hits = 0

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def cache_hits(self) -> int:
        return self._cache_hits

    def search(
        self,
        query: str,
        *,
        count: int = 10,
        country: str = "NO",
        search_lang: str = "nb",
        freshness: str | None = None,
        use_cache: bool = True,
    ) -> list[dict[str, object]]:
        del use_cache  # This audit intentionally forces a live transport request.
        query = " ".join(query.split()).strip()
        record = BraveTransportRecord(query=query)
        self.records.append(record)

        params = {
            "q": query,
            "count": str(count),
            "country": country.upper(),
            "search_lang": search_lang,
            "safesearch": "moderate",
            "spellcheck": "1",
        }
        if freshness:
            params["freshness"] = freshness

        record.endpoint = f"{self.provider.base_url}?{urlencode(params)}"
        headers = dict(self.provider.headers)
        record.headers_present = tuple(sorted(headers.keys()))
        record.request_timestamp = datetime.now(timezone.utc).isoformat()
        record.stage_reached = "send_request"
        request = Request(record.endpoint, headers=headers, method="GET")

        started = perf_counter()
        try:
            record.request_sent = True
            self._request_count += 1
            with urlopen(request, timeout=float(self.provider.timeout)) as response:  # noqa: S310
                payload = response.read()
                record.http_status = int(response.getcode())
                record.content_type = response.headers.get("Content-Type")
                record.response_time_ms = round((perf_counter() - started) * 1000)
                record.response_size_bytes = len(payload)
                record.body_preview = payload[:500].decode("utf-8", errors="replace")
                record.stage_reached = "receive_response"
        except HTTPError as exc:
            payload = exc.read() or b""
            record.http_status = int(exc.code)
            record.content_type = exc.headers.get("Content-Type") if exc.headers else None
            record.response_time_ms = round((perf_counter() - started) * 1000)
            record.response_size_bytes = len(payload)
            record.body_preview = payload[:500].decode("utf-8", errors="replace")
            record.stage_reached = "receive_response"
            record.transport_error = _classify_http_error(exc.code)
            raise RuntimeError(record.transport_error) from exc
        except TimeoutError as exc:
            record.response_time_ms = round((perf_counter() - started) * 1000)
            record.transport_error = "Timeout"
            raise RuntimeError("Timeout") from exc
        except ssl.SSLError as exc:
            record.response_time_ms = round((perf_counter() - started) * 1000)
            record.transport_error = "SSL Error"
            raise RuntimeError("SSL Error") from exc
        except socket.gaierror as exc:
            record.response_time_ms = round((perf_counter() - started) * 1000)
            record.transport_error = "DNS Error"
            raise RuntimeError("DNS Error") from exc
        except URLError as exc:
            record.response_time_ms = round((perf_counter() - started) * 1000)
            reason = exc.reason
            if isinstance(reason, socket.gaierror):
                record.transport_error = "DNS Error"
            elif isinstance(reason, ssl.SSLError):
                record.transport_error = "SSL Error"
            elif isinstance(reason, TimeoutError):
                record.transport_error = "Timeout"
            else:
                record.transport_error = f"Transport Error: {reason}"
            raise RuntimeError(record.transport_error) from exc

        if not payload:
            record.transport_error = "Empty Body"
            raise RuntimeError("Empty Body")

        record.stage_reached = "parse_json"
        try:
            json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            record.parse_error = "JSON Parse Error"
            raise RuntimeError("JSON Parse Error") from exc

        try:
            results = parse_brave_results(payload)
        except RuntimeError as exc:
            record.parse_error = str(exc)
            raise

        record.stage_reached = "extract_results"
        record.results_count = len(results)
        return results

    def mark_forwarded(self, records: list[BraveTransportRecord]) -> None:
        for record in records:
            if record.stage_reached == "extract_results":
                record.stage_reached = "forward_to_evidence"


def summarize_transport(records: list[BraveTransportRecord]) -> dict[str, int]:
    return {
        "requests_sent": sum(record.request_sent for record in records),
        "responses_received": sum(record.http_status is not None for record in records),
        "http_200": sum(record.http_status == 200 for record in records),
        "http_401": sum(record.http_status == 401 for record in records),
        "http_403": sum(record.http_status == 403 for record in records),
        "http_429": sum(record.http_status == 429 for record in records),
        "timeouts": sum(record.transport_error == "Timeout" for record in records),
        "dns_errors": sum(record.transport_error == "DNS Error" for record in records),
        "ssl_errors": sum(record.transport_error == "SSL Error" for record in records),
        "json_parse_failures": sum(record.parse_error == "JSON Parse Error" for record in records),
        "empty_responses": sum(record.transport_error == "Empty Body" for record in records),
    }


def _classify_http_error(status: int) -> str:
    if status == 401:
        return "Authentication (401)"
    if status == 403:
        return "Forbidden (403)"
    if status == 429:
        return "Rate Limit (429)"
    return f"HTTP Error ({status})"
