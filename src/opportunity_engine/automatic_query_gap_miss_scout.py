"""Independent, source-verified QUERY_GAP miss scout.

This scout is deliberately separate from the canonical query pack. It asks one
bounded Norway search using closure/inventory semantics without embedding the
candidate sale words that learning is expected to discover. A search hit is
never ground truth: an exact public HTML page must independently prove a real
store/business closure and an all-goods/inventory liquidation event.

Only then, if the exact page is absent from the canonical checkpoint and the
page contains a commercially meaningful sale term absent from active queries,
the scout emits a QUERY_GAP missed-opportunity case. Production query mutation,
contact, bidding, purchasing and payment are always forbidden.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from opportunity_engine.cost_guard import manual_paid_brave_block_reason
from opportunity_engine.daily_learning_runtime import load_active_learning_queries
from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.signal_follow_up_engine import _canonical_url
from opportunity_engine.missed_opportunity_learning import (
    DiscoveryTrace,
    MissedOpportunityCase,
    load_missed_opportunity_memory,
    save_missed_opportunity_memory,
)

SCHEMA_VERSION = "automatic-query-gap-miss-scout-1.0"
OUTPUT_FILENAME = "automatic-query-gap-miss-scout.json"
MEMORY_RELATIVE_PATH = Path("learning/missed-opportunities.json")
DEFAULT_ACTIVE_QUERY_CONFIG = "config/brave_search_queries.json"
DEFAULT_MAX_PAGES = 3
MAX_PAGES = 3
DEFAULT_SEARCH_RESULTS = 8
MAX_PAGE_BYTES = 1_500_000

# No candidate learning term may appear here. The query describes the event,
# while candidate lexical knowledge must be discovered only after page fetch.
SCOUT_QUERY_NO = (
    '("legger ned" OR "legges ned" OR "stenger for godt" OR "siste åpningsdag") '
    '(butikk OR bedrift OR selskap) (varer OR varelager OR lagerbeholdning)'
)

_GAP_TERMS = (
    "sluttsalg",
    "avslutningssalg",
    "opphørssalg",
    "avviklingssalg",
    "tømmesalg",
)
_CLOSURE_MARKERS = (
    "legger ned",
    "legges ned",
    "stenger for godt",
    "stenger etter",
    "siste åpningsdag",
    "avvikles",
    "opphører",
)
_LIQUIDATION_MARKERS = (
    "alt skal ut",
    "alle varer skal ut",
    "alle varene skal ut",
    "alle varer må ut",
    "varelager",
    "lagerbeholdning",
    "hele lageret",
)
_TEMPORARY_MARKERS = (
    "midlertidig stengt",
    "stengt for oppussing",
    "stenger for oppussing",
    "stengt på grunn av ferie",
)
_COMPANY_PATTERNS = (
    re.compile(
        r"\b(?:klesbutikken|butikken|bedriften|selskapet|forretningen)\s+"
        r"([A-ZÆØÅ][A-Za-zÆØÅæøå0-9&.'’\- ]{1,80}?)\s+"
        r"(?:i|på|stenger|legger|legges|skal|har|vil)\b"
    ),
    re.compile(
        r"\b([A-ZÆØÅ][A-Za-zÆØÅæøå0-9&.'’\- ]{1,80}?)\s+"
        r"(?:legger ned|legges ned|stenger for godt|stenger etter)\b"
    ),
)

SearchCallback = Callable[[str], Sequence[SearchHit]]
PageFetcher = Callable[[str], "PublicPage"]


@dataclass(frozen=True, slots=True)
class PublicPage:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    html: str


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0:
            cleaned = " ".join(data.split()).strip()
            if cleaned:
                self.parts.append(cleaned)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _canonical(value: object) -> str:
    return _canonical_url(value) or ""


def _visible_text(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    return _compact(" ".join(parser.parts))[:80_000]


def _read_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _write_object(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _walk_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for child in value:
            yield from _walk_strings(child)


def _checkpoint_urls(checkpoint: Mapping[str, Any]) -> set[str]:
    urls: set[str] = set()
    for row in checkpoint.get("deduplicated_opportunities") or []:
        if not isinstance(row, Mapping):
            continue
        for value in _walk_strings(row):
            if not value.startswith(("https://", "http://")):
                continue
            canonical = _canonical(value)
            if canonical:
                urls.add(canonical)
    return urls


def _query_contains_term(active_queries: Sequence[str], term: str) -> bool:
    pattern = re.compile(rf"(?<!\w){re.escape(term.casefold())}(?!\w)")
    return any(pattern.search(str(query).casefold()) for query in active_queries)


def _extract_company(text: str) -> str | None:
    for pattern in _COMPANY_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        value = _compact(match.group(1)).strip(" -–—|:,.;")
        if 2 <= len(value) <= 100:
            return value
    return None


def _bounded_context(text: str, term: str, *, radius: int = 360) -> str:
    folded = text.casefold()
    index = folded.find(term.casefold())
    if index < 0:
        return text[:1200]
    start = max(0, index - radius)
    end = min(len(text), index + len(term) + radius)
    return _compact(text[start:end])[:1200]


def _verify_closure_liquidation_page(page: PublicPage) -> dict[str, Any] | None:
    if page.status_code != 200:
        return None
    if "text/html" not in page.content_type.casefold():
        return None
    final = _canonical(page.final_url)
    if not final or urlparse(final).scheme != "https":
        return None

    text = _visible_text(page.html)
    folded = text.casefold()
    if not text or any(marker in folded for marker in _TEMPORARY_MARKERS):
        return None

    closure_markers = [marker for marker in _CLOSURE_MARKERS if marker in folded]
    sale_terms = [term for term in _GAP_TERMS if term in folded]
    liquidation_markers = [marker for marker in _LIQUIDATION_MARKERS if marker in folded]
    if not closure_markers or not sale_terms or not liquidation_markers:
        return None

    company = _extract_company(text)
    if not company:
        return None

    return {
        "canonical_url": final,
        "company": company,
        "query_gap_terms": sale_terms,
        "closure_markers": closure_markers,
        "liquidation_markers": liquidation_markers,
        "evidence_text": _bounded_context(text, sale_terms[0]),
        "source_page_verified": True,
        "closure_verified": True,
        "inventory_liquidation_verified": True,
    }


def fetch_public_page(url: str, *, timeout: float = 15.0) -> PublicPage:
    canonical = _canonical(url)
    if not canonical or urlparse(canonical).scheme != "https":
        raise ValueError("scout page must be a canonical HTTPS URL")
    request = Request(
        canonical,
        headers={
            "User-Agent": "OpportunityEngine/QueryGapScout-1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - verified HTTPS input
        status = int(getattr(response, "status", 200) or 200)
        final_url = str(response.geturl() or canonical)
        content_type = str(response.headers.get("Content-Type") or "")
        raw = response.read(MAX_PAGE_BYTES + 1)
    if len(raw) > MAX_PAGE_BYTES:
        raise ValueError("public page exceeded bounded byte limit")
    charset_match = re.search(r"charset=([A-Za-z0-9._-]+)", content_type, flags=re.I)
    charset = charset_match.group(1) if charset_match else "utf-8"
    html = raw.decode(charset, errors="replace")
    return PublicPage(
        requested_url=canonical,
        final_url=final_url,
        status_code=status,
        content_type=content_type,
        html=html,
    )


def discover_query_gap_misses(
    checkpoint: Mapping[str, Any],
    *,
    active_queries: Sequence[str],
    search: SearchCallback,
    fetch_page: PageFetcher,
    observed_at: datetime | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> dict[str, Any]:
    """Search independently, verify exact pages, and return true QUERY_GAP misses."""
    bounded_pages = max(0, min(MAX_PAGES, int(max_pages)))
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    core_urls = _checkpoint_urls(checkpoint)
    raw_hits = [item for item in search(SCOUT_QUERY_NO) if isinstance(item, SearchHit)]
    search_request_count = 1
    page_requests = verified_pages = core_known = no_new_term = 0
    cases: list[MissedOpportunityCase] = []
    metadata: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for hit in raw_hits:
        url = _canonical(hit.url)
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        if url in core_urls:
            core_known += 1
            continue
        if page_requests >= bounded_pages:
            break

        page_requests += 1
        try:
            page = fetch_page(url)
        except Exception:
            continue
        proof = _verify_closure_liquidation_page(page)
        if proof is None:
            continue
        verified_pages += 1

        available_terms = [
            term
            for term in proof["query_gap_terms"]
            if term.casefold() not in SCOUT_QUERY_NO.casefold()
            and not _query_contains_term(active_queries, term)
        ]
        if not available_terms:
            no_new_term += 1
            continue
        term = available_terms[0]
        final_url = str(proof["canonical_url"])
        if final_url in core_urls:
            core_known += 1
            continue

        case = MissedOpportunityCase(
            case_id=(
                "auto-query-gap:no:"
                + sha256(final_url.encode("utf-8")).hexdigest()[:24]
            ),
            market_code="NO",
            discovered_by="AUTOMATIC_INDEPENDENT_QUERY_GAP_SCOUT",
            observed_at=now,
            opportunity_type="VERIFIED_STORE_CLOSURE_INVENTORY_LIQUIDATION",
            stock_proven=True,
            ground_truth_company=str(proof["company"]),
            ground_truth_url=final_url,
            trace=DiscoveryTrace(query_generated=False),
            learning_evidence_text=str(proof["evidence_text"]),
        ).with_diagnosis()
        cases.append(case)
        metadata.append(
            {
                "case_id": case.case_id,
                "canonical_url": final_url,
                "company": case.ground_truth_company,
                "query_gap_term": term,
                "source_page_verified": True,
                "closure_verified": True,
                "inventory_liquidation_verified": True,
                "closure_markers": list(proof["closure_markers"]),
                "liquidation_markers": list(proof["liquidation_markers"]),
                "search_hit_alone_is_ground_truth": False,
                "scout_query_contains_gap_term": False,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS" if cases else "VALID_ZERO",
        "market_code": "NO",
        "scout_query": SCOUT_QUERY_NO,
        "search_request_count": search_request_count,
        "search_hit_count": len(raw_hits),
        "page_request_count": page_requests,
        "verified_page_count": verified_pages,
        "detected_miss_count": len(cases),
        "core_already_knew_count": core_known,
        "no_new_query_term_count": no_new_term,
        "cases": cases,
        "cases_metadata": metadata,
        "search_hit_alone_is_never_ground_truth": True,
        "source_page_verification_required": True,
        "automatic_query_activation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _merge_memory(
    existing: Sequence[MissedOpportunityCase],
    detected: Sequence[MissedOpportunityCase],
) -> tuple[list[MissedOpportunityCase], int, int]:
    by_id = {case.case_id: case for case in existing if case.case_id}
    order = [case.case_id for case in existing if case.case_id]
    new_count = repeat_count = 0
    for case in detected:
        previous = by_id.get(case.case_id)
        if previous is None:
            by_id[case.case_id] = case
            order.append(case.case_id)
            new_count += 1
        elif previous.learning_status in {"RECOVERED", "TRANSFER_PROVEN"} and not previous.repeat_miss:
            by_id[case.case_id] = replace(previous, repeat_miss=True)
            repeat_count += 1
    return [by_id[item] for item in order], new_count, repeat_count


def _attach_to_brief(output_dir: Path, report: Mapping[str, Any]) -> None:
    brief_path = output_dir / "domain-market-intelligence-brief.json"
    brief = _read_object(brief_path)
    if not brief:
        return
    brief["automatic_query_gap_miss_scout"] = {
        key: report.get(key)
        for key in (
            "status",
            "search_request_count",
            "search_hit_count",
            "page_request_count",
            "verified_page_count",
            "detected_miss_count",
            "new_case_count",
            "repeat_miss_count_this_run",
            "known_case_count_after",
            "core_already_knew_count",
            "no_new_query_term_count",
            "automatic_query_activation",
        )
    }
    _write_object(brief_path, brief)


def write_automatic_query_gap_miss_scout(
    output_dir: str | Path,
    *,
    input_root: str | Path,
    active_query_config: str | Path = DEFAULT_ACTIVE_QUERY_CONFIG,
    environment: Mapping[str, str] | None = None,
    search_override: SearchCallback | None = None,
    page_fetcher: PageFetcher | None = None,
    observed_at: datetime | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> dict[str, Any]:
    """Run the bounded scout and merge verified QUERY_GAP cases into memory."""
    env = environment if environment is not None else os.environ
    output = Path(output_dir)
    root = Path(input_root)
    cost_block = manual_paid_brave_block_reason(env)
    report_path = output / OUTPUT_FILENAME
    if cost_block:
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "SKIPPED_COST_GUARD",
            "cost_guard_reason": cost_block,
            "search_request_count": 0,
            "search_hit_count": 0,
            "page_request_count": 0,
            "verified_page_count": 0,
            "detected_miss_count": 0,
            "new_case_count": 0,
            "repeat_miss_count_this_run": 0,
            "automatic_query_activation": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
        _write_object(report_path, report)
        _attach_to_brief(output, report)
        return report

    api_key = _compact(env.get("BRAVE_SEARCH_API_KEY") or env.get("BRAVE_API_KEY"))
    if search_override is None and not api_key:
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "SKIPPED_NO_API_KEY",
            "search_request_count": 0,
            "page_request_count": 0,
            "detected_miss_count": 0,
            "automatic_query_activation": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
        _write_object(report_path, report)
        _attach_to_brief(output, report)
        return report

    if search_override is None:
        provider = BraveSearchProvider(
            api_key,
            country="NO",
            freshness="pm",
            extra_snippets=True,
        )

        def search(query: str):
            return provider.search(query, count=DEFAULT_SEARCH_RESULTS)
    else:
        search = search_override

    checkpoint = _read_object(output / "multi-market-daily-checkpoint.json")
    active_queries = load_active_learning_queries(active_query_config)
    outcome = discover_query_gap_misses(
        checkpoint,
        active_queries=active_queries,
        search=search,
        fetch_page=page_fetcher or fetch_public_page,
        observed_at=observed_at,
        max_pages=max_pages,
    )
    detected = list(outcome.pop("cases"))
    memory_path = root / MEMORY_RELATIVE_PATH
    existing = load_missed_opportunity_memory(memory_path)
    merged, new_count, repeat_count = _merge_memory(existing, detected)
    save_missed_opportunity_memory(memory_path, merged)

    report = {
        **outcome,
        "status": "SUCCESS" if detected else outcome.get("status", "VALID_ZERO"),
        "new_case_count": new_count,
        "repeat_miss_count_this_run": repeat_count,
        "known_case_count_after": len(merged),
        "detected_cases": [case.to_dict() for case in detected],
        "memory_path": memory_path.as_posix(),
        "max_pages": max(0, min(MAX_PAGES, int(max_pages))),
        "automatic_query_activation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    _write_object(report_path, report)
    _attach_to_brief(output, report)
    return report
