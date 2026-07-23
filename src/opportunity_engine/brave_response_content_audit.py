"""Inspect Brave response content without changing search or investment logic.

V2.7.2.4.5 captures a sanitized copy of each raw JSON response, records the
available result paths, and compares those paths with ``parse_brave_results``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from opportunity_engine.ods.brave_search import parse_brave_results


SENSITIVE_KEYS = {
    "token",
    "api_key",
    "apikey",
    "authorization",
    "x-subscription-token",
    "subscription_token",
}
CANDIDATE_RESULT_PATHS = (
    "web.results",
    "mixed.results",
    "news.results",
    "videos.results",
    "discussions.results",
    "locations.results",
)


@dataclass(slots=True)
class BraveResponseContentRecord:
    query: str
    request_timestamp: str
    http_status: int | None = None
    content_type: str | None = None
    response_size_bytes: int = 0
    top_level_keys: tuple[str, ...] = ()
    expected_path: str = "web.results"
    expected_path_exists: bool = False
    expected_path_type: str | None = None
    expected_path_count: int = 0
    discovered_result_paths: dict[str, int] | None = None
    parser_results_count: int = 0
    raw_json_file: str | None = None
    raw_json_sha256: str | None = None
    diagnosis: str = "not_evaluated"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResponseContentAuditedBraveProvider:
    """Drop-in provider that performs a live request and inspects raw JSON shape."""

    def __init__(self, provider: Any, raw_dir: str = "data/validation/brave_raw_responses") -> None:
        self.provider = provider
        self.raw_dir = Path(raw_dir)
        self.records: list[BraveResponseContentRecord] = []
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
        del use_cache
        query = " ".join(query.split()).strip()
        record = BraveResponseContentRecord(
            query=query,
            request_timestamp=datetime.now(timezone.utc).isoformat(),
            discovered_result_paths={},
        )
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
        url = f"{self.provider.base_url}?{urlencode(params)}"
        request = Request(url, headers=dict(self.provider.headers), method="GET")

        try:
            self._request_count += 1
            with urlopen(request, timeout=float(self.provider.timeout)) as response:  # noqa: S310
                payload = response.read()
                record.http_status = int(response.getcode())
                record.content_type = response.headers.get("Content-Type")
                record.response_size_bytes = len(payload)
        except Exception as exc:
            record.error = f"transport_error: {exc}"
            record.diagnosis = "transport_failed"
            raise

        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            record.error = f"json_parse_error: {exc}"
            record.diagnosis = "invalid_json"
            raise RuntimeError("Brave Search returned invalid JSON") from exc

        sanitized = _sanitize(decoded)
        record.top_level_keys = tuple(sorted(decoded.keys())) if isinstance(decoded, dict) else ()
        record.expected_path_exists, expected = _get_path(decoded, "web.results")
        record.expected_path_type = type(expected).__name__ if record.expected_path_exists else None
        record.expected_path_count = len(expected) if isinstance(expected, list) else 0
        record.discovered_result_paths = {
            path: len(value)
            for path in CANDIDATE_RESULT_PATHS
            for exists, value in [_get_path(decoded, path)]
            if exists and isinstance(value, list)
        }

        raw_path = self._write_raw_response(sanitized, len(self.records))
        record.raw_json_file = str(raw_path)
        record.raw_json_sha256 = _sha256_file(raw_path)

        results = parse_brave_results(payload)
        record.parser_results_count = len(results)
        record.diagnosis = diagnose_content(record)
        return results

    def _write_raw_response(self, sanitized: Any, sequence: int) -> Path:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        target = self.raw_dir / f"response-{sequence:03d}.json"
        target.write_text(
            json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return target


def diagnose_content(record: BraveResponseContentRecord) -> str:
    alternate_count = sum(
        count
        for path, count in (record.discovered_result_paths or {}).items()
        if path != record.expected_path
    )
    if record.expected_path_count > 0 and record.parser_results_count > 0:
        return "web_results_present_and_parser_extracts"
    if record.expected_path_count > 0 and record.parser_results_count == 0:
        return "web_results_present_but_parser_rejects"
    if record.expected_path_count == 0 and alternate_count > 0:
        return "results_exist_in_alternate_path"
    if record.expected_path_exists and record.expected_path_count == 0:
        return "web_results_explicitly_empty"
    if not record.expected_path_exists:
        return "web_results_path_missing"
    return "undetermined"


def summarize_content(records: list[BraveResponseContentRecord]) -> dict[str, int]:
    return {
        "responses_audited": len(records),
        "web_results_present": sum(item.expected_path_count > 0 for item in records),
        "web_results_empty": sum(item.diagnosis == "web_results_explicitly_empty" for item in records),
        "web_results_path_missing": sum(item.diagnosis == "web_results_path_missing" for item in records),
        "alternate_path_results": sum(item.diagnosis == "results_exist_in_alternate_path" for item in records),
        "parser_rejections": sum(item.diagnosis == "web_results_present_but_parser_rejects" for item in records),
        "parser_successes": sum(item.diagnosis == "web_results_present_and_parser_extracts" for item in records),
    }


def _get_path(value: Any, dotted_path: str) -> tuple[bool, Any]:
    current = value
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, child in value.items():
            if str(key).casefold() in SENSITIVE_KEYS:
                output[str(key)] = "***REDACTED***"
            else:
                output[str(key)] = _sanitize(child)
        return output
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _sha256_file(path: Path) -> str:
    from hashlib import sha256

    return sha256(path.read_bytes()).hexdigest()
