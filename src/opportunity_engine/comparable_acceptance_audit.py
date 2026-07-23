"""Explain why normalized Brave rows do or do not become market comparables.

V2.7.2.4.7 is diagnostic only. It observes the exact rows returned by the
configured search provider and mirrors the production comparable adapter and
MarketComparablesEngine acceptance rules without changing investment logic.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import urlparse


@dataclass(slots=True)
class ComparableRowAudit:
    rank: int
    title: str
    url: str
    domain: str
    price_nok: float | None
    currency: str | None
    similarity_score: float | None
    published_at: str | None
    adapter_accepted: bool
    engine_accepted: bool
    rejection_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ComparableSearchAudit:
    query: str
    response_count: int
    inspected_count: int
    adapter_accepted_count: int
    engine_accepted_count: int
    rows: tuple[ComparableRowAudit, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ComparableAcceptanceAuditedProvider:
    """Transparent search-provider wrapper that audits up to ``row_limit`` rows."""

    def __init__(
        self,
        provider: Any,
        *,
        comparable_adapter: Callable[[Any], Iterable[Any]],
        comparables_engine: Any,
        row_limit: int = 20,
    ) -> None:
        self.provider = provider
        self.comparable_adapter = comparable_adapter
        self.comparables_engine = comparables_engine
        self.row_limit = max(1, int(row_limit))
        self.audits: list[ComparableSearchAudit] = []

    @property
    def request_count(self) -> int:
        return int(getattr(self.provider, "request_count", 0))

    @property
    def cache_hits(self) -> int:
        return int(getattr(self.provider, "cache_hits", 0))

    def search(self, query: str, **kwargs: Any) -> Any:
        response = self.provider.search(query, **kwargs)
        rows = response if isinstance(response, list) else []
        inspected = rows[: self.row_limit]

        adapter_candidates = tuple(self.comparable_adapter(inspected))
        engine_result = self.comparables_engine.evaluate(adapter_candidates)
        accepted_urls = {str(getattr(item, "url", "")) for item in getattr(engine_result, "accepted", ())}
        engine_reasons = {
            str(getattr(getattr(item, "candidate", None), "url", "")): tuple(
                str(reason) for reason in getattr(item, "reasons", ())
            )
            for item in getattr(engine_result, "rejected", ())
        }
        adapter_urls = {str(getattr(item, "url", "")) for item in adapter_candidates}

        audited_rows: list[ComparableRowAudit] = []
        for rank, item in enumerate(inspected, start=1):
            row = item if isinstance(item, dict) else {}
            title = str(row.get("title") or "").strip()
            url = str(row.get("url") or "").strip()
            price = _numeric_price(row.get("price_nok"))
            currency = _currency(row)
            similarity = _numeric_similarity(row.get("similarity_score"))
            reasons: list[str] = []

            if not isinstance(item, dict):
                reasons.append("row_not_object")
            if not title:
                reasons.append("missing_title")
            if not url.startswith("https://"):
                reasons.append("invalid_https_url")
            raw_price = row.get("price_nok")
            if raw_price is None:
                reasons.append("missing_price")
            elif price is None:
                reasons.append("invalid_price")
            if currency and currency != "NOK":
                reasons.append("currency_not_nok")
            if similarity is not None and similarity < 0.65:
                reasons.append("low_similarity")

            adapter_accepted = url in adapter_urls
            if not adapter_accepted and not reasons:
                reasons.append("adapter_rejected_other")

            engine_accepted = url in accepted_urls
            if adapter_accepted and not engine_accepted:
                reasons.extend(reason for reason in engine_reasons.get(url, ()) if reason not in reasons)
                if not engine_reasons.get(url):
                    reasons.append("engine_rejected_other")

            audited_rows.append(
                ComparableRowAudit(
                    rank=rank,
                    title=title,
                    url=url,
                    domain=(urlparse(url).hostname or "").lower().removeprefix("www."),
                    price_nok=price,
                    currency=currency,
                    similarity_score=similarity,
                    published_at=_optional_text(row.get("published_at")),
                    adapter_accepted=adapter_accepted,
                    engine_accepted=engine_accepted,
                    rejection_reasons=tuple(dict.fromkeys(reasons)),
                )
            )

        self.audits.append(
            ComparableSearchAudit(
                query=query,
                response_count=len(rows),
                inspected_count=len(inspected),
                adapter_accepted_count=sum(item.adapter_accepted for item in audited_rows),
                engine_accepted_count=sum(item.engine_accepted for item in audited_rows),
                rows=tuple(audited_rows),
            )
        )
        return response


def summarize_acceptance(audits: Iterable[ComparableSearchAudit]) -> dict[str, Any]:
    items = tuple(audits)
    rows = tuple(row for audit in items for row in audit.rows)
    reasons = Counter(reason for row in rows for reason in row.rejection_reasons)
    domains = Counter(row.domain for row in rows if row.domain)
    return {
        "searches_audited": len(items),
        "results_received": sum(item.response_count for item in items),
        "results_inspected": len(rows),
        "adapter_accepted": sum(row.adapter_accepted for row in rows),
        "engine_accepted": sum(row.engine_accepted for row in rows),
        "rejected": sum(not row.engine_accepted for row in rows),
        "rejection_reasons": dict(sorted(reasons.items())),
        "top_domains": dict(domains.most_common(10)),
    }


def _numeric_price(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return None


def _numeric_similarity(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _currency(row: dict[str, Any]) -> str | None:
    for key in ("currency", "price_currency", "currency_code"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip().upper()
    return "NOK" if _numeric_price(row.get("price_nok")) is not None else None


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
