"""Cost-aware Brave Search API client for authorized external research.

V2.6.1 deliberately limits this module to search and normalization. It does not
calculate market value, discover buyers, modify Living Investment Files, or select
investment scenarios.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

JsonTransport = Callable[[str, float, dict[str, str]], bytes]


def _default_transport(url: str, timeout: float, headers: dict[str, str]) -> bytes:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed official API
            return response.read()
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise RuntimeError("Brave Search authentication failed") from exc
        if exc.code == 429:
            raise RuntimeError("Brave Search rate limit reached") from exc
        raise RuntimeError(f"Brave Search returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Brave Search request failed: {exc.reason}") from exc


@dataclass(frozen=True)
class BraveSearchClient:
    api_key: str
    base_url: str = "https://api.search.brave.com/res/v1/web/search"
    timeout: float = 20.0
    transport: JsonTransport = _default_transport
    cache_dir: str = "data/brave_cache"
    cache_ttl_hours: int = 24
    max_requests_per_run: int = 8
    usage_log_path: str = "data/brave_usage.jsonl"

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("api_key must not be empty")
        if not self.base_url.startswith("https://"):
            raise ValueError("base_url must use HTTPS")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if self.cache_ttl_hours < 0:
            raise ValueError("cache_ttl_hours cannot be negative")
        if self.max_requests_per_run <= 0:
            raise ValueError("max_requests_per_run must be positive")
        object.__setattr__(self, "_request_count", 0)
        object.__setattr__(self, "_cache_hits", 0)

    @classmethod
    def from_environment(cls) -> "BraveSearchClient":
        api_key = os.getenv("BRAVE_API_KEY", "").strip() or os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
        if not api_key:
            raise ValueError("Set BRAVE_API_KEY or BRAVE_SEARCH_API_KEY")
        return cls(
            api_key=api_key,
            timeout=_env_float("BRAVE_TIMEOUT_SECONDS", 20.0),
            cache_dir=os.getenv("BRAVE_CACHE_DIR", "data/brave_cache").strip() or "data/brave_cache",
            cache_ttl_hours=_env_int("BRAVE_CACHE_TTL_HOURS", 24),
            max_requests_per_run=_env_int("BRAVE_MAX_REQUESTS_PER_RUN", 8),
            usage_log_path=os.getenv("BRAVE_USAGE_LOG", "data/brave_usage.jsonl").strip()
            or "data/brave_usage.jsonl",
        )

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
            "User-Agent": "Opportunity-Engine/2.7.2.4.6 (authorized-web-search)",
        }

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
        """Run one bounded Brave web search and return normalized direct fields.

        Brave documents ``q`` as required, with maximum 400 characters / 50 words,
        and ``count`` as at most 20. ``result_filter=web`` is explicit so the
        response contains the ``web.results`` collection consumed by the parser.
        """
        query = " ".join(query.split()).strip()
        if not query:
            raise ValueError("query must not be empty")
        if len(query) > 400 or len(query.split()) > 50:
            raise ValueError("query exceeds Brave's 400-character or 50-word limit")
        if not 1 <= count <= 20:
            raise ValueError("count must be between 1 and 20")

        params = {
            "q": query,
            "count": str(count),
            "country": country.upper(),
            "search_lang": search_lang,
            "safesearch": "moderate",
            "spellcheck": "1",
            "result_filter": "web",
        }
        if freshness:
            params["freshness"] = freshness

        cache_key = sha256(json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()
        if use_cache:
            cached = self._load_cache(cache_key)
            if cached is not None:
                object.__setattr__(self, "_cache_hits", self._cache_hits + 1)
                return parse_brave_results(cached)

        if self._request_count >= self.max_requests_per_run:
            raise RuntimeError(
                f"Brave per-run request budget reached ({self.max_requests_per_run})"
            )

        url = f"{self.base_url}?{urlencode(params)}"
        object.__setattr__(self, "_request_count", self._request_count + 1)
        try:
            payload = self.transport(url, self.timeout, self.headers)
        except RuntimeError:
            self._record_usage(query, "failed")
            raise

        self._save_cache(cache_key, payload)
        self._record_usage(query, "success")
        return parse_brave_results(payload)

    def _cache_path(self, cache_key: str) -> Path:
        return Path(self.cache_dir) / f"{cache_key}.json"

    def _load_cache(self, cache_key: str) -> bytes | None:
        if self.cache_ttl_hours == 0:
            return None
        path = self._cache_path(cache_key)
        if not path.exists():
            return None
        try:
            wrapper = json.loads(path.read_text(encoding="utf-8"))
            saved_at = datetime.fromisoformat(str(wrapper["saved_at"]).replace("Z", "+00:00"))
            if saved_at.tzinfo is None:
                saved_at = saved_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - saved_at > timedelta(hours=self.cache_ttl_hours):
                return None
            payload = wrapper.get("payload")
            return json.dumps(payload).encode("utf-8") if isinstance(payload, dict) else None
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def _save_cache(self, cache_key: str, payload: bytes) -> None:
        path = self._cache_path(cache_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Brave Search returned invalid JSON") from exc
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(
                {"saved_at": datetime.now(timezone.utc).isoformat(), "payload": decoded},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    def _record_usage(self, query: str, status: str) -> None:
        path = Path(self.usage_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": "brave_search",
            "query_hash": sha256(query.casefold().encode("utf-8")).hexdigest(),
            "status": status,
            "requests_this_run": self._request_count,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def parse_brave_results(payload: bytes | str) -> list[dict[str, object]]:
    try:
        decoded = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        data = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("Brave Search returned invalid JSON") from exc

    web = data.get("web", {}) if isinstance(data, dict) else {}
    items = web.get("results", []) if isinstance(web, dict) else []
    if not isinstance(items, list):
        raise RuntimeError("Brave Search response does not contain web results")

    results: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    for rank, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title or not url.startswith("https://") or url in seen_urls:
            continue
        seen_urls.add(url)
        extra = item.get("extra_snippets")
        if not isinstance(extra, list):
            extra = []
        results.append(
            {
                "id": str(item.get("id") or sha256(url.encode("utf-8")).hexdigest()[:24]),
                "title": title,
                "url": url,
                "snippet": " ".join(str(item.get("description") or "").split()).strip(),
                "extra_snippets": [
                    " ".join(str(value).split()).strip()
                    for value in extra
                    if str(value).strip()
                ],
                "source": "Brave Search",
                "published_at": item.get("page_age") or item.get("age") or None,
                "language": item.get("language") or None,
                "source_rank": rank,
            }
        )
    return results


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc
