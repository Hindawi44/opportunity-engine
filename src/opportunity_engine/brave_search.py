"""Guarded Brave Search API connector for Opportunity Engine v2.6.1.

This module performs web search only. It does not calculate market value, select an
investment path, or modify Living Investment Files. The connector is deliberately
cost-aware: it validates queries, caps requests, supports an injectable transport for
tests, records usage, and can reuse a short-lived local cache.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BRAVE_WEB_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BraveSearchError(RuntimeError):
    """Base connector error."""


class BraveSearchConfigurationError(BraveSearchError):
    """Raised when required configuration is missing or invalid."""


class BraveSearchRateLimitError(BraveSearchError):
    """Raised when Brave returns HTTP 429."""


@dataclass(frozen=True, slots=True)
class BraveSearchConfig:
    api_key: str
    country: str = "NO"
    search_lang: str = "no"
    count: int = 10
    timeout_seconds: float = 12.0
    max_requests_per_run: int = 8
    cache_dir: str = "data/brave_cache"
    cache_ttl_hours: int = 24
    usage_log_path: str = "data/brave_usage.jsonl"

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise BraveSearchConfigurationError("Brave API key is required")
        if not 1 <= self.count <= 20:
            raise BraveSearchConfigurationError("count must be between 1 and 20")
        if self.timeout_seconds <= 0:
            raise BraveSearchConfigurationError("timeout_seconds must be positive")
        if self.max_requests_per_run <= 0:
            raise BraveSearchConfigurationError("max_requests_per_run must be positive")
        if self.cache_ttl_hours < 0:
            raise BraveSearchConfigurationError("cache_ttl_hours cannot be negative")

    @classmethod
    def from_environment(cls) -> "BraveSearchConfig":
        api_key = os.getenv("BRAVE_API_KEY", "").strip() or os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
        if not api_key:
            raise BraveSearchConfigurationError(
                "Set BRAVE_API_KEY (or BRAVE_SEARCH_API_KEY) before using Brave Search"
            )
        return cls(
            api_key=api_key,
            country=os.getenv("BRAVE_COUNTRY", "NO").strip() or "NO",
            search_lang=os.getenv("BRAVE_SEARCH_LANG", "no").strip() or "no",
            count=_env_int("BRAVE_RESULTS_PER_QUERY", 10),
            timeout_seconds=_env_float("BRAVE_TIMEOUT_SECONDS", 12.0),
            max_requests_per_run=_env_int("BRAVE_MAX_REQUESTS_PER_RUN", 8),
            cache_dir=os.getenv("BRAVE_CACHE_DIR", "data/brave_cache").strip() or "data/brave_cache",
            cache_ttl_hours=_env_int("BRAVE_CACHE_TTL_HOURS", 24),
            usage_log_path=os.getenv("BRAVE_USAGE_LOG", "data/brave_usage.jsonl").strip()
            or "data/brave_usage.jsonl",
        )


@dataclass(frozen=True, slots=True)
class BraveSearchResult:
    result_id: str
    title: str
    url: str
    description: str
    age: str | None = None
    language: str | None = None
    extra_snippets: tuple[str, ...] = ()
    source_rank: int = 0


@dataclass(frozen=True, slots=True)
class BraveSearchResponse:
    query: str
    collected_at: str
    results: tuple[BraveSearchResult, ...]
    more_results_available: bool
    from_cache: bool
    request_count_for_run: int
    raw_result_count: int
    warnings: tuple[str, ...] = ()


@dataclass(slots=True)
class BraveUsageCounter:
    requests: int = 0
    cache_hits: int = 0
    failures: int = 0
    queries: list[str] = field(default_factory=list)


Transport = Callable[[str, dict[str, str], float], dict[str, Any]]


class BraveSearchConnector:
    """Cost-aware connector for Brave's Web Search endpoint."""

    def __init__(
        self,
        config: BraveSearchConfig,
        *,
        transport: Transport | None = None,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self.config = config
        self.transport = transport or _default_transport
        self.now = now
        self.usage = BraveUsageCounter()

    def search(
        self,
        query: str,
        *,
        count: int | None = None,
        country: str | None = None,
        search_lang: str | None = None,
        freshness: str | None = None,
        use_cache: bool = True,
    ) -> BraveSearchResponse:
        clean_query = " ".join(query.split()).strip()
        if not clean_query:
            raise ValueError("Search query cannot be empty")
        if len(clean_query) > 400 or len(clean_query.split()) > 50:
            raise ValueError("Brave query exceeds 400 characters or 50 words")

        result_count = self.config.count if count is None else count
        if not 1 <= result_count <= 20:
            raise ValueError("count must be between 1 and 20")

        params: dict[str, str] = {
            "q": clean_query,
            "count": str(result_count),
            "country": (country or self.config.country).upper(),
            "search_lang": search_lang or self.config.search_lang,
            "safesearch": "moderate",
            "spellcheck": "1",
        }
        if freshness:
            params["freshness"] = freshness

        cache_key = self._cache_key(params)
        if use_cache:
            cached = self._load_cache(cache_key)
            if cached is not None:
                self.usage.cache_hits += 1
                return self._parse(clean_query, cached, from_cache=True)

        if self.usage.requests >= self.config.max_requests_per_run:
            raise BraveSearchRateLimitError(
                f"Per-run Brave request budget reached ({self.config.max_requests_per_run})"
            )

        url = f"{BRAVE_WEB_SEARCH_ENDPOINT}?{urlencode(params)}"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.config.api_key,
            "User-Agent": "OpportunityEngine/2.6.1",
        }
        self.usage.requests += 1
        self.usage.queries.append(clean_query)
        try:
            payload = self.transport(url, headers, self.config.timeout_seconds)
        except BraveSearchError:
            self.usage.failures += 1
            self._record_usage(clean_query, "failed")
            raise
        except Exception as exc:  # Defensive boundary around custom transports.
            self.usage.failures += 1
            self._record_usage(clean_query, "failed")
            raise BraveSearchError(f"Brave transport failed: {exc}") from exc

        self._save_cache(cache_key, payload)
        self._record_usage(clean_query, "success")
        return self._parse(clean_query, payload, from_cache=False)

    def _parse(self, query: str, payload: dict[str, Any], *, from_cache: bool) -> BraveSearchResponse:
        web = payload.get("web") if isinstance(payload, dict) else None
        raw_results = web.get("results", []) if isinstance(web, dict) else []
        warnings: list[str] = []
        parsed: list[BraveSearchResult] = []
        seen_urls: set[str] = set()

        for rank, item in enumerate(raw_results, start=1):
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()
            if not url.startswith("https://") or not title or url in seen_urls:
                continue
            seen_urls.add(url)
            description = " ".join(str(item.get("description") or "").split()).strip()
            snippets = item.get("extra_snippets")
            if not isinstance(snippets, list):
                snippets = []
            result_id = str(item.get("id") or "").strip() or sha256(url.encode("utf-8")).hexdigest()[:24]
            parsed.append(
                BraveSearchResult(
                    result_id=result_id,
                    title=title,
                    url=url,
                    description=description,
                    age=_optional_text(item.get("age")),
                    language=_optional_text(item.get("language")),
                    extra_snippets=tuple(
                        " ".join(str(value).split()).strip()
                        for value in snippets
                        if str(value).strip()
                    ),
                    source_rank=rank,
                )
            )

        if not parsed:
            warnings.append("Brave returned no usable HTTPS web results")
        query_info = payload.get("query", {}) if isinstance(payload, dict) else {}
        return BraveSearchResponse(
            query=query,
            collected_at=self.now().isoformat(),
            results=tuple(parsed),
            more_results_available=bool(
                query_info.get("more_results_available") if isinstance(query_info, dict) else False
            ),
            from_cache=from_cache,
            request_count_for_run=self.usage.requests,
            raw_result_count=len(raw_results),
            warnings=tuple(warnings),
        )

    def _cache_key(self, params: dict[str, str]) -> str:
        normalized = json.dumps(params, sort_keys=True, ensure_ascii=False)
        return sha256(normalized.encode("utf-8")).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return Path(self.config.cache_dir) / f"{key}.json"

    def _load_cache(self, key: str) -> dict[str, Any] | None:
        if self.config.cache_ttl_hours == 0:
            return None
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            wrapper = json.loads(path.read_text(encoding="utf-8"))
            saved_at = datetime.fromisoformat(str(wrapper["saved_at"]).replace("Z", "+00:00"))
            if saved_at.tzinfo is None:
                saved_at = saved_at.replace(tzinfo=timezone.utc)
            if self.now() - saved_at > timedelta(hours=self.config.cache_ttl_hours):
                return None
            payload = wrapper.get("payload")
            return payload if isinstance(payload, dict) else None
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def _save_cache(self, key: str, payload: dict[str, Any]) -> None:
        path = self._cache_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(
                {"saved_at": self.now().isoformat(), "payload": payload},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    def _record_usage(self, query: str, status: str) -> None:
        path = Path(self.config.usage_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": self.now().isoformat(),
            "provider": "brave_search",
            "query_hash": sha256(query.casefold().encode("utf-8")).hexdigest(),
            "status": status,
            "requests_this_run": self.usage.requests,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _default_transport(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
    except HTTPError as exc:
        if exc.code == 429:
            raise BraveSearchRateLimitError("Brave Search API rate limit reached") from exc
        if exc.code in {401, 403}:
            raise BraveSearchConfigurationError("Brave Search API rejected the subscription token") from exc
        raise BraveSearchError(f"Brave Search API returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise BraveSearchError(f"Brave Search API network error: {exc.reason}") from exc
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BraveSearchError("Brave Search API returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise BraveSearchError("Brave Search API returned an unexpected payload")
    return payload


def response_to_dict(response: BraveSearchResponse) -> dict[str, Any]:
    return asdict(response)


def _optional_text(value: Any) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text or None


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise BraveSearchConfigurationError(f"{name} must be an integer") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise BraveSearchConfigurationError(f"{name} must be numeric") from exc
