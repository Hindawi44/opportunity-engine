"""Conservative parser rescue overlay learned from verified PARSER_GAP cases.

V1 is intentionally narrow: it learns only Auksjonen inventory-lot wording for
listings that already passed the static clothing gate.  It never broadens what
counts as clothing and never fetches a page.  A new term must come from the raw
title of an exact URL whose downstream source verifier proved bulk clothing,
must look semantically like stock/lot language, must not already be covered by
the static lot parser, and must remain rare in the current raw clothing corpus.

The resulting overlay is durable state for the *next* scheduled run.  Learned
terms augment only ``inventory_lot_signal``; exact item-page verification and all
existing opportunity safety gates remain unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    has_inventory_lot_signal,
)
from opportunity_engine.discovery.signal_follow_up_engine import _canonical_url
from opportunity_engine.missed_opportunity_learning import (
    MissedOpportunityCase,
    load_missed_opportunity_memory,
)

SCHEMA_VERSION = "parser-gap-rescue-overlay-1.0"
REPORT_SCHEMA_VERSION = "parser-gap-rescue-learning-1.0"
OUTPUT_FILENAME = "parser-gap-rescue-learning.json"
OVERLAY_FILENAME = "parser-rescue-overlay.json"
MEMORY_RELATIVE_PATH = Path("learning/missed-opportunities.json")
SUPPORTED_SOURCE = "Auksjonen.no"

# Candidate tokens must carry an intrinsically stock/lot-like stem.  Generic
# commercial words such as ``salg`` are deliberately absent.
_STRONG_BULK_FRAGMENTS = (
    "lager",
    "parti",
    "bulk",
    "pall",
    "rest",
    "konkurs",
    "samle",
    "tømm",
    "opphør",
    "avvikl",
)
_GENERIC_DENYLIST = {
    "lager",
    "parti",
    "rest",
    "salg",
    "auksjon",
    "klær",
    "klaer",
    "tekstil",
    "arbeidsklær",
    "arbeidsklaer",
    "jakke",
    "jakker",
    "bukse",
    "bukser",
    "sko",
    "varer",
}
_TOKEN_RE = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*", re.UNICODE)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _canonical(value: object) -> str:
    return _canonical_url(value) or ""


def _read_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _write_object(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _tokens(value: object) -> list[str]:
    return [match.group(0).casefold() for match in _TOKEN_RE.finditer(_compact(value))]


def _company_tokens(case: MissedOpportunityCase) -> set[str]:
    return {token for token in _tokens(case.ground_truth_company) if len(token) >= 3}


def _raw_listings(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = report.get("listings") or []
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _listing_for_url(
    report: Mapping[str, Any], target_url: str
) -> Mapping[str, Any] | None:
    expected = _canonical(target_url)
    if not expected:
        return None
    for row in _raw_listings(report):
        if _canonical(row.get("url")) == expected:
            return row
    return None


def _strong_candidate_terms(
    title: str,
    *,
    company_tokens: set[str],
) -> list[str]:
    # If the established parser already recognizes the title, no rescue is
    # needed and we must not manufacture redundant vocabulary.
    if has_inventory_lot_signal(title):
        return []
    terms: list[str] = []
    for token in _tokens(title):
        if len(token) < 6:
            continue
        if token in company_tokens or token in _GENERIC_DENYLIST:
            continue
        if not any(fragment in token for fragment in _STRONG_BULK_FRAGMENTS):
            continue
        terms.append(token)
    return sorted(set(terms))


def _term_in_title(term: str, title: object) -> bool:
    return term.casefold() in set(_tokens(title))


def _raw_match_count(term: str, report: Mapping[str, Any]) -> int:
    return sum(
        1
        for row in _raw_listings(report)
        if _term_in_title(term, row.get("title"))
    )


def _active_parser_cases(
    cases: Sequence[MissedOpportunityCase],
) -> list[MissedOpportunityCase]:
    rows: list[MissedOpportunityCase] = []
    for case in cases:
        diagnosed = case if case.root_cause else case.with_diagnosis()
        if diagnosed.root_cause != "PARSER_GAP":
            continue
        if not diagnosed.stock_proven:
            continue
        if diagnosed.market_code.upper() != "NO":
            continue
        if diagnosed.learning_status == "RECOVERED" and not diagnosed.repeat_miss:
            continue
        rows.append(diagnosed)
    rows.sort(key=lambda case: (not case.repeat_miss, case.observed_at, case.case_id))
    return rows


def _existing_rows(
    overlay: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if not isinstance(overlay, Mapping):
        return {}
    sources = overlay.get("sources")
    if not isinstance(sources, Mapping):
        return {}
    raw_rows = sources.get(SUPPORTED_SOURCE)
    if not isinstance(raw_rows, list):
        return {}
    by_term: dict[str, dict[str, Any]] = {}
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            continue
        term = _compact(raw.get("term")).casefold()
        if not term:
            continue
        if _compact(raw.get("status")) != "PROVEN_BY_VERIFIED_PARSER_GAP":
            continue
        by_term[term] = dict(raw)
    return by_term


def build_parser_rescue_overlay(
    cases: Sequence[MissedOpportunityCase],
    raw_report: Mapping[str, Any],
    *,
    existing_overlay: Mapping[str, Any] | None = None,
    max_raw_matches_per_term: int = 5,
    max_terms_per_source: int = 8,
) -> dict[str, Any]:
    """Build a bounded Auksjonen lot-parser overlay from verified parser misses."""
    if max_raw_matches_per_term < 1:
        raise ValueError("max_raw_matches_per_term must be >= 1")
    if max_terms_per_source < 1:
        raise ValueError("max_terms_per_source must be >= 1")

    by_term = _existing_rows(existing_overlay)
    rejected_noisy: set[str] = set()
    evidence_by_term: dict[str, set[str]] = {}
    match_count_by_term: dict[str, int] = {}

    for case in _active_parser_cases(cases):
        listing = _listing_for_url(raw_report, case.ground_truth_url)
        if listing is None:
            continue
        title = _compact(listing.get("title"))
        if not title:
            continue
        company_tokens = _company_tokens(case)
        for term in _strong_candidate_terms(title, company_tokens=company_tokens):
            count = _raw_match_count(term, raw_report)
            if count <= 0:
                continue
            if count > max_raw_matches_per_term:
                rejected_noisy.add(term)
                continue
            evidence_by_term.setdefault(term, set()).add(case.case_id)
            match_count_by_term[term] = count

    for term, case_ids in evidence_by_term.items():
        previous = by_term.get(term, {})
        previous_ids = {
            _compact(value)
            for value in previous.get("verified_case_ids") or []
            if _compact(value)
        }
        by_term[term] = {
            "term": term,
            "status": "PROVEN_BY_VERIFIED_PARSER_GAP",
            "raw_match_count": match_count_by_term[term],
            "verified_case_ids": sorted(previous_ids | case_ids),
            "source": SUPPORTED_SOURCE,
            "affects": "INVENTORY_LOT_SIGNAL_ONLY",
        }

    ranked = sorted(
        by_term.values(),
        key=lambda row: (
            -len(row.get("verified_case_ids") or []),
            int(row.get("raw_match_count") or 999),
            str(row.get("term") or ""),
        ),
    )[:max_terms_per_source]
    sources = {SUPPORTED_SOURCE: ranked} if ranked else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "sources": sources,
        "active_term_count": len(ranked),
        "max_terms_per_source": max_terms_per_source,
        "max_raw_matches_per_term": max_raw_matches_per_term,
        "rejected_noisy_terms": sorted(rejected_noisy),
        "affects_clothing_gate": False,
        "affects_inventory_lot_signal_only": True,
        "network_requests": 0,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def load_parser_rescue_overlay(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "sources": {},
            "active_term_count": 0,
        }
    payload = _read_object(target)
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported parser rescue overlay schema")
    if not isinstance(payload.get("sources"), Mapping):
        raise ValueError("parser rescue overlay sources must be an object")
    return payload


def load_parser_rescue_terms(
    path: str | Path,
    source_name: str,
) -> tuple[str, ...]:
    overlay = load_parser_rescue_overlay(path)
    rows = (overlay.get("sources") or {}).get(source_name) or []
    if not isinstance(rows, list):
        return ()
    return tuple(
        _compact(row.get("term")).casefold()
        for row in rows
        if isinstance(row, Mapping)
        and _compact(row.get("status")) == "PROVEN_BY_VERIFIED_PARSER_GAP"
        and _compact(row.get("term"))
    )


def save_parser_rescue_overlay(path: str | Path, overlay: Mapping[str, Any]) -> None:
    payload = dict(overlay)
    payload["schema_version"] = SCHEMA_VERSION
    _write_object(Path(path), payload)


def _auksjonen_raw_report(
    manifest: Mapping[str, Any],
    *,
    root: Path,
) -> dict[str, Any]:
    for raw in manifest.get("sources") or []:
        if not isinstance(raw, Mapping):
            continue
        if _compact(raw.get("source_name")) != SUPPORTED_SOURCE:
            continue
        artifact_dir = _compact(raw.get("artifact_dir"))
        if not artifact_dir:
            continue
        report_file = _compact(raw.get("report_file")) or "auksjonen-live-clothing-listings.json"
        return _read_object(root / artifact_dir / report_file)
    return {}


def _attach_to_brief(output_dir: Path, report: Mapping[str, Any]) -> None:
    path = output_dir / "domain-market-intelligence-brief.json"
    brief = _read_object(path)
    if not brief:
        return
    brief["parser_gap_rescue_learning"] = {
        key: report.get(key)
        for key in (
            "schema_version",
            "status",
            "active_term_count",
            "new_term_count",
            "rejected_noisy_terms",
            "network_requests",
        )
    }
    _write_object(path, brief)


def write_parser_gap_rescue_overlay(
    output_dir: str | Path,
    *,
    input_root: str | Path,
    root: str | Path = ".",
    max_raw_matches_per_term: int = 5,
    max_terms_per_source: int = 8,
) -> dict[str, Any]:
    """Learn parser rescue terms from today's verified parser gaps for tomorrow."""
    output = Path(output_dir)
    input_path = Path(input_root)
    memory_path = input_path / MEMORY_RELATIVE_PATH
    overlay_path = input_path / "learning" / OVERLAY_FILENAME
    manifest = _read_object(output / "input-manifest.json")
    raw_report = _auksjonen_raw_report(manifest, root=Path(root))
    cases = load_missed_opportunity_memory(memory_path)
    existing = load_parser_rescue_overlay(overlay_path) if overlay_path.exists() else None
    previous_terms = set(load_parser_rescue_terms(overlay_path, SUPPORTED_SOURCE)) if overlay_path.exists() else set()

    overlay = build_parser_rescue_overlay(
        cases,
        raw_report,
        existing_overlay=existing,
        max_raw_matches_per_term=max_raw_matches_per_term,
        max_terms_per_source=max_terms_per_source,
    )
    save_parser_rescue_overlay(overlay_path, overlay)
    current_terms = set(load_parser_rescue_terms(overlay_path, SUPPORTED_SOURCE))
    new_terms = sorted(current_terms - previous_terms)

    active_parser_cases = len(_active_parser_cases(cases))
    if not raw_report:
        status = "SKIPPED_AUKSJONEN_RAW_REPORT_MISSING"
    elif new_terms:
        status = "NEW_PROVEN_TERMS"
    elif current_terms:
        status = "RETAINED_PROVEN_TERMS"
    elif active_parser_cases:
        status = "VALID_ZERO_NO_SAFE_RESCUE_TERM"
    else:
        status = "VALID_ZERO_NO_PARSER_GAPS"

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": status,
        "source": SUPPORTED_SOURCE,
        "active_parser_gap_case_count": active_parser_cases,
        "active_term_count": len(current_terms),
        "new_term_count": len(new_terms),
        "new_terms": new_terms,
        "active_terms": sorted(current_terms),
        "rejected_noisy_terms": overlay.get("rejected_noisy_terms") or [],
        "overlay_path": overlay_path.as_posix(),
        "network_requests": 0,
        "affects_clothing_gate": False,
        "affects_inventory_lot_signal_only": True,
        "source_page_verification_still_required": True,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    _write_object(output / OUTPUT_FILENAME, report)
    _attach_to_brief(output, report)
    return report
