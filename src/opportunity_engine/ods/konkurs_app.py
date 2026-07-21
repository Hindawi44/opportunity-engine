"""Konkurs.app connectors for authorized feeds and limited public API discovery.

The public client uses the documented JSON API for a small, recent page of active
company bankruptcies. It is a discovery lead source, not an asset-sale feed: prices,
fees, stock and resale values are never inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .live_data import SourceDocument
from .models import ODSRequest

JsonTransport = Callable[[str, float, dict[str, str]], bytes]


def _default_json_transport(url: str, timeout: float, headers: dict[str, str]) -> bytes:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - documented HTTPS API/feed
            return response.read()
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise RuntimeError("Konkurs.app authorization failed") from exc
        if exc.code == 429:
            raise RuntimeError("Konkurs.app rate limit reached") from exc
        raise RuntimeError(f"Konkurs.app returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Konkurs.app request failed: {exc.reason}") from exc


@dataclass(frozen=True)
class KonkursAppFeedClient:
    feed_url: str
    token: str | None = None
    timeout: float = 15.0
    transport: JsonTransport = _default_json_transport

    def __post_init__(self) -> None:
        if not self.feed_url.startswith("https://"):
            raise ValueError("Konkurs.app feed_url must use HTTPS")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "Opportunity-Engine/1.0 (limited-integration)",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def fetch(self, *, keyword: str | None = None) -> tuple[SourceDocument, ...]:
        payload = self.transport(self.feed_url, self.timeout, self.headers)
        return parse_konkurs_app_feed(payload, keyword=keyword)


@dataclass(frozen=True)
class KonkursAppPublicApiClient:
    """Fetch one small page of recent active company bankruptcies.

    The documented API is rate limited and disallows mass harvesting, so the default
    request is intentionally limited to 25 records and a single request per run.
    """

    base_url: str = "https://konkurs.app/api/konkursbo"
    page_size: int = 25
    timeout: float = 15.0
    transport: JsonTransport = _default_json_transport

    def __post_init__(self) -> None:
        if not self.base_url.startswith("https://"):
            raise ValueError("Konkurs.app base_url must use HTTPS")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "User-Agent": "Opportunity-Engine/1.0 (limited-public-api-integration)",
        }

    def fetch(self, *, keyword: str | None = None) -> tuple[SourceDocument, ...]:
        params = {
            "page": 1,
            "size": self.page_size,
            "sort": "stiftelsesdato",
            "order": "desc",
            "status": "aktive",
        }
        if keyword and keyword.strip():
            params["search"] = keyword.strip()
        url = f"{self.base_url}?{urlencode(params)}"
        payload = self.transport(url, self.timeout, self.headers)
        return parse_konkurs_app_feed(payload, keyword=None, access_mode="public_api")


@dataclass(frozen=True)
class KonkursAppConnector:
    client: KonkursAppFeedClient
    name: str = "konkurs_app_authorized_feed"

    def fetch(self, request: ODSRequest) -> tuple[SourceDocument, ...]:
        return self.client.fetch(keyword=request.subject)


def parse_konkurs_app_feed(
    payload: bytes | str,
    *,
    keyword: str | None = None,
    access_mode: str = "authorized_feed",
) -> tuple[SourceDocument, ...]:
    try:
        decoded = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        data = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("Konkurs.app returned invalid JSON") from exc

    items = data.get("items", data.get("results", data.get("data", data))) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise RuntimeError("Konkurs.app response must contain a list, data, items, or results list")

    needle = keyword.casefold().strip() if keyword and keyword.strip() else None
    documents: list[SourceDocument] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(
            item.get("title")
            or item.get("company_name")
            or item.get("debitor_navn")
            or item.get("navn")
            or item.get("name")
            or ""
        ).strip()
        organization_number = _text_or_none(
            item.get("organization_number") or item.get("orgnr") or item.get("debitor_orgnr")
        )
        url = str(item.get("url") or item.get("source_url") or "").strip()
        if not url and organization_number:
            url = f"https://konkurs.app/konkursbo/{organization_number}"
        if not title or not url.startswith("https://"):
            continue

        description = str(
            item.get("description")
            or item.get("summary")
            or item.get("debitor_aktivitet")
            or item.get("debitor_formaal")
            or item.get("naeringsbeskrivelse")
            or ""
        ).strip()
        searchable = " ".join(
            str(value or "")
            for value in (
                title,
                description,
                organization_number,
                item.get("naeringsbeskrivelse"),
                item.get("kommune"),
            )
        ).casefold()
        if needle and needle not in searchable:
            continue

        raw_id = str(item.get("id") or item.get("case_id") or item.get("orgnr") or organization_number or "").strip()
        document_id = raw_id or hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        if document_id in seen:
            continue
        seen.add(document_id)

        city = _text_or_none(
            item.get("city") or item.get("location") or item.get("municipality") or item.get("kommune") or item.get("poststed")
        )
        deadline = _datetime_or_none(item.get("ends_at") or item.get("deadline"))
        bankruptcy_date = _datetime_or_none(
            item.get("bankruptcy_date") or item.get("opened_at") or item.get("stiftelsesdato") or item.get("registreringsdato")
        )
        price = _float_or_none(item.get("price_nok") or item.get("current_price_nok"))
        is_public_lead = access_mode == "public_api"
        documents.append(
            SourceDocument(
                document_id=f"konkurs-app-{document_id}",
                source_name="Konkurs.app",
                source_type="bankruptcy_discovery_lead" if is_public_lead else "authorized_liquidation_asset",
                title=title,
                text=description or title,
                url=url,
                published_at=bankruptcy_date or _datetime_or_none(item.get("published_at")),
                country="Norway",
                metadata={
                    "current_price_nok": price,
                    "city": city,
                    "ends_at": deadline.isoformat() if deadline else None,
                    "description": description or None,
                    "organization_number": organization_number,
                    "bankruptcy_date": bankruptcy_date.isoformat() if bankruptcy_date else None,
                    "industry_code": _text_or_none(item.get("naeringskode")),
                    "industry_description": _text_or_none(item.get("naeringsbeskrivelse")),
                    "trustee": _text_or_none(item.get("bostyrer")),
                    "asset_type": _text_or_none(item.get("asset_type") or item.get("category")),
                    "mva_status": str(item.get("mva_status") or "unknown"),
                    "access_mode": access_mode,
                    "lead_only": is_public_lead,
                },
            )
        )
    return tuple(documents)


def _float_or_none(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _text_or_none(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _datetime_or_none(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
