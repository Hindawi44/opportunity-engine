"""Shadow market-fit evidence for verified pages inside the unified search runtime.

A search being anchored to one market is not evidence that the seller, inventory,
or commercial page is actually located in that market. This module annotates the
existing freshly fetched verification rows with bounded country/market signals.

The annotation is deliberately non-authoritative:
* it never changes page classification or Exact-Lot acceptance;
* it never adds search requests or page fetches;
* it never promotes a source, route, provider, or opportunity;
* it never treats the query market itself as qualification evidence.

Signals are intentionally conservative and auditable: matching ccTLD, explicit
country-name text, country phone prefix, and market-specific currency codes where
they are actually distinctive (NOK/SEK). Conflicting ccTLD/phone signals are
reported, not used as an automatic rejection gate, because cross-border wholesale
pages are valid commercial possibilities.
"""
from __future__ import annotations

from collections import Counter
import re
from typing import Any, Callable
from urllib.parse import urlsplit

from opportunity_engine.discovery import provider_unique_page_verification as verifier


VERSION = "MARKET_FIT_EVIDENCE_V1"
SUPPORTED_MARKETS = ("NO", "SE", "DE", "FR", "IT", "NL")
SEARCH_REQUESTS_ADDED = 0
PAGE_FETCHES_ADDED = 0
QUALIFICATION_EFFECT = False
_INSTALLED = False
_UPSTREAM_VERIFY_ROW: Callable[..., tuple[dict[str, Any], bool]] | None = None
_UPSTREAM_VERIFY_REPORT: Callable[..., dict[str, Any]] | None = None

_MARKET_CCTLD = {
    "NO": ".no",
    "SE": ".se",
    "DE": ".de",
    "FR": ".fr",
    "IT": ".it",
    "NL": ".nl",
}
_MARKET_PHONE_PREFIX = {
    "NO": "+47",
    "SE": "+46",
    "DE": "+49",
    "FR": "+33",
    "IT": "+39",
    "NL": "+31",
}
_MARKET_COUNTRY_TERMS = {
    "NO": ("norway", "norge"),
    "SE": ("sweden", "sverige"),
    "DE": ("germany", "deutschland"),
    "FR": ("france",),
    "IT": ("italy", "italia"),
    "NL": ("netherlands", "nederland", "holland"),
}
# EUR is shared by DE/FR/IT/NL and therefore cannot identify one of those markets.
_MARKET_SPECIFIC_CURRENCY = {
    "NO": ("nok",),
    "SE": ("sek",),
}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _host(url: object) -> str:
    try:
        host = (urlsplit(_compact(url)).hostname or "").casefold()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def _contains_term(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(term.casefold())}(?!\w)", text))


def _phone_present(text: str, prefix: str) -> bool:
    compact = text.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    return prefix in compact


def assess_market_fit_evidence(
    *,
    market: str,
    url: object,
    title: object = "",
    text: object = "",
) -> dict[str, Any]:
    """Return bounded market-fit evidence without making a qualification decision."""
    target = _compact(market).upper()
    if target not in SUPPORTED_MARKETS:
        raise ValueError(f"unsupported market: {target}")

    host = _host(url)
    combined = _compact(f"{title or ''} {text or ''}").casefold()
    matching: list[str] = []
    conflicting: list[dict[str, str]] = []
    other_country_mentions: list[str] = []

    target_tld = _MARKET_CCTLD[target]
    if host.endswith(target_tld):
        matching.append("HOST_CCTLD")
    else:
        for code, suffix in _MARKET_CCTLD.items():
            if code != target and host.endswith(suffix):
                conflicting.append({"market_code": code, "signal": "HOST_CCTLD"})
                break

    if _phone_present(combined, _MARKET_PHONE_PREFIX[target]):
        matching.append("PHONE_PREFIX")
    for code, prefix in _MARKET_PHONE_PREFIX.items():
        if code != target and _phone_present(combined, prefix):
            conflicting.append({"market_code": code, "signal": "PHONE_PREFIX"})

    if any(_contains_term(combined, term) for term in _MARKET_COUNTRY_TERMS[target]):
        matching.append("COUNTRY_TERM")
    for code, terms in _MARKET_COUNTRY_TERMS.items():
        if code != target and any(_contains_term(combined, term) for term in terms):
            other_country_mentions.append(code)

    currency_terms = _MARKET_SPECIFIC_CURRENCY.get(target, ())
    if any(_contains_term(combined, term) for term in currency_terms):
        matching.append("MARKET_SPECIFIC_CURRENCY")

    matching = sorted(set(matching))
    conflicting_markets = sorted({row["market_code"] for row in conflicting})
    other_country_mentions = sorted(set(other_country_mentions))

    if matching and conflicting:
        status = "MIXED_CROSS_BORDER_EVIDENCE"
    elif conflicting:
        status = "CONFLICTING_MARKET_EVIDENCE"
    elif len(matching) >= 2:
        status = "SUPPORTED_MARKET_FIT"
    elif matching:
        status = "PARTIAL_MARKET_EVIDENCE"
    else:
        status = "UNPROVEN_MARKET_FIT"

    return {
        "version": VERSION,
        "target_market_code": target,
        "status": status,
        "matching_signal_families": matching,
        "matching_signal_family_count": len(matching),
        "conflicting_signals": conflicting,
        "conflicting_market_codes": conflicting_markets,
        "other_country_mentions": other_country_mentions,
        "host": host,
        "query_market_is_qualification_evidence": False,
        "market_fit_is_qualification_evidence": False,
        "changes_exact_lot_decision": False,
        "automatic_rejection": False,
        "automatic_source_promotion": False,
        "production_mutation": False,
    }


def _unavailable_evidence(market: str, *, reason: str) -> dict[str, Any]:
    return {
        "version": VERSION,
        "target_market_code": _compact(market).upper(),
        "status": "UNAVAILABLE",
        "reason": reason,
        "matching_signal_families": [],
        "matching_signal_family_count": 0,
        "conflicting_signals": [],
        "conflicting_market_codes": [],
        "other_country_mentions": [],
        "query_market_is_qualification_evidence": False,
        "market_fit_is_qualification_evidence": False,
        "changes_exact_lot_decision": False,
        "automatic_rejection": False,
        "automatic_source_promotion": False,
        "production_mutation": False,
    }


def _verify_row_with_market_fit(
    candidate: dict[str, str],
    *,
    page_fetcher,
    allow_tool_learning_credit: bool,
) -> tuple[dict[str, Any], bool]:
    upstream = _UPSTREAM_VERIFY_ROW
    if upstream is None:
        raise RuntimeError("upstream verifier row function is unavailable")

    captured: dict[str, Any] = {}

    def capture_fetch(url: str):
        fetched = page_fetcher(url)
        captured["fetched"] = fetched
        return fetched

    row, ok = upstream(
        candidate,
        page_fetcher=capture_fetch,
        allow_tool_learning_credit=allow_tool_learning_credit,
    )
    output = dict(row)
    fetched = captured.get("fetched")
    market = _compact(candidate.get("market_code")).upper()
    if ok and fetched is not None:
        output["market_fit_evidence"] = assess_market_fit_evidence(
            market=market,
            url=getattr(fetched, "final_url", None) or candidate.get("url"),
            title=getattr(fetched, "title", None) or candidate.get("title"),
            text=getattr(fetched, "text", ""),
        )
    else:
        output["market_fit_evidence"] = _unavailable_evidence(
            market,
            reason="PAGE_FETCH_NOT_SUCCESSFUL",
        )
    output["market_fit_is_qualification_evidence"] = False
    output["exact_lot_decision_changed_by_market_fit"] = False
    return output, ok


def _verify_report_with_market_fit(*args, **kwargs) -> dict[str, Any]:
    upstream = _UPSTREAM_VERIFY_REPORT
    if upstream is None:
        raise RuntimeError("upstream verifier report function is unavailable")
    report = dict(upstream(*args, **kwargs))
    pages = [row for row in report.get("verified_pages") or [] if isinstance(row, dict)]
    status_counts = Counter(
        _compact((row.get("market_fit_evidence") or {}).get("status")) or "MISSING"
        for row in pages
    )
    report.update(
        {
            "market_fit_evidence_version": VERSION,
            "market_fit_shadow_only": True,
            "market_fit_is_qualification_evidence": False,
            "market_fit_changes_exact_lot_decision": False,
            "market_fit_status_counts": dict(sorted(status_counts.items())),
            "search_requests_added_by_market_fit": SEARCH_REQUESTS_ADDED,
            "page_fetches_added_by_market_fit": PAGE_FETCHES_ADDED,
            "production_mutation": False,
        }
    )
    return report


def install_market_fit_evidence_v1() -> bool:
    """Patch only evidence annotation around the established verifier."""
    global _INSTALLED, _UPSTREAM_VERIFY_ROW, _UPSTREAM_VERIFY_REPORT
    if _INSTALLED:
        return False
    _UPSTREAM_VERIFY_ROW = verifier._verify_fetched_candidate
    _UPSTREAM_VERIFY_REPORT = verifier.verify_provider_unique_pages
    verifier._verify_fetched_candidate = _verify_row_with_market_fit
    verifier.verify_provider_unique_pages = _verify_report_with_market_fit
    _INSTALLED = True
    return True
