"""Capture source-verified opportunities that the canonical core failed to report.

This module closes the feedback loop without treating search hits as truth.  A
candidate can become missed-opportunity ground truth only when an existing
source-specific verifier has confirmed the public source page, entity link and
commercial facts, and the evidence proves a bulk clothing lot rather than a
single item.  The detector then compares the exact URL against the canonical
checkpoint and traces the same URL through the configured source artifacts to
explain where the core pipeline lost it.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from opportunity_engine.discovery.signal_follow_up_engine import _canonical_url
from opportunity_engine.missed_opportunity_learning import (
    DiscoveryTrace,
    MissedOpportunityCase,
    load_missed_opportunity_memory,
    save_missed_opportunity_memory,
)

SCHEMA_VERSION = "automatic-missed-opportunity-capture-1.0"
OUTPUT_FILENAME = "automatic-missed-opportunity-capture.json"
MEMORY_RELATIVE_PATH = Path("learning/missed-opportunities.json")

_SOURCE_KIND_TO_SOURCE = {
    "AUKSJONEN_EXACT_ITEM": ("NO", "Auksjonen.no"),
    "VENTA_EXACT_ITEM": ("DE", "VENTA Industrieversteigerungen"),
}

_CLOTHING_TERMS = (
    "klær",
    "klaer",
    "arbeidsklær",
    "arbeidsklaer",
    "jakke",
    "jakker",
    "bukse",
    "bukser",
    "skjorte",
    "skjorter",
    "sko",
    "vernesko",
    "tekstiler",
    "tekstil",
    "bekleidung",
    "kleidung",
    "arbeitskleidung",
    "jacken",
    "hosen",
    "hemden",
    "schuhe",
    "textilien",
    "clothing",
    "apparel",
    "garments",
    "jackets",
    "trousers",
    "shirts",
    "footwear",
)
_BULK_TERMS = (
    "varelager",
    "restlager",
    "lagerparti",
    "vareparti",
    "parti med",
    "parti klær",
    "parti klaer",
    "lagerbeholdning",
    "warenbestand",
    "lagerbestand",
    "restposten",
    "warenposten",
    "posten bekleidung",
    "stock clothing",
    "stock apparel",
    "inventory lot",
    "warehouse stock",
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


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


def _utc_from_report(value: object) -> datetime:
    text = _compact(value)
    if not text:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical(value: object) -> str:
    return _canonical_url(value) or ""


def _walk_strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, Mapping):
        for child in value.values():
            yield from _walk_strings(child)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for child in value:
            yield from _walk_strings(child)


def _json_contains_url(path: Path, target_url: str) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for value in _walk_strings(payload):
        if not value.startswith(("http://", "https://")):
            continue
        if _canonical(value) == target_url:
            return True
    return False


def _checkpoint_urls(checkpoint: Mapping[str, Any]) -> set[str]:
    urls: set[str] = set()
    for raw in checkpoint.get("deduplicated_opportunities") or []:
        if not isinstance(raw, Mapping):
            continue
        values: list[object] = [raw.get("canonical_url")]
        identity = raw.get("opportunity_identity")
        if isinstance(identity, str) and identity.startswith(("http://", "https://")):
            values.append(identity)
        source_urls = raw.get("source_urls")
        if isinstance(source_urls, Sequence) and not isinstance(source_urls, (str, bytes)):
            values.extend(source_urls)
        for value in values:
            canonical = _canonical(value)
            if canonical:
                urls.add(canonical)
    return urls


def _source_spec(
    manifest: Mapping[str, Any],
    source_name: str,
) -> Mapping[str, Any] | None:
    expected = source_name.casefold()
    for raw in manifest.get("sources") or []:
        if not isinstance(raw, Mapping):
            continue
        name = _compact(raw.get("source_name") or raw.get("source")).casefold()
        if name == expected:
            return raw
    return None


def _artifact_paths(
    manifest: Mapping[str, Any],
    *,
    source_name: str,
    root: Path,
) -> tuple[Path | None, Path | None, Path | None]:
    spec = _source_spec(manifest, source_name)
    if spec is None:
        return None, None, None
    artifact_dir_text = _compact(spec.get("artifact_dir"))
    if not artifact_dir_text:
        return None, None, None
    directory = root / artifact_dir_text
    report = directory / _compact(spec.get("report_file") or "search-run-report.json")
    candidates = directory / _compact(
        spec.get("candidates_file") or "all-discovered-candidates.json"
    )
    unified = directory / _compact(
        spec.get("unified_report_file") or "unified-opportunity-report.json"
    )
    return report, candidates, unified


def _text_for_verification(row: Mapping[str, Any]) -> str:
    values = [
        row.get("target_label"),
        row.get("search_result_title"),
        row.get("title"),
        row.get("clothing_inventory_evidence"),
        row.get("sale_evidence"),
    ]
    return _compact(" ".join(_compact(value) for value in values if _compact(value)))


def _positive_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _verified_bulk_clothing(row: Mapping[str, Any]) -> bool:
    if row.get("source_page_verified") is not True:
        return False
    if row.get("entity_link_verified") is not True:
        return False
    if row.get("commercial_facts_confirmed") is not True:
        return False
    if _compact(row.get("source_kind")) not in _SOURCE_KIND_TO_SOURCE:
        return False

    text = _text_for_verification(row).casefold()
    explicit_clothing = bool(row.get("clothing_inventory_evidence")) or any(
        term.casefold() in text for term in _CLOTHING_TERMS
    )
    if not explicit_clothing:
        return False

    quantity = _positive_number(row.get("quantity"))
    pallets = _positive_number(row.get("pallet_count"))
    # An explicit one-piece quantity vetoes generic "parti/lager" wording.
    if quantity is not None:
        bulk = quantity > 1
    else:
        bulk = bool(pallets) or any(term.casefold() in text for term in _BULK_TERMS)
    return bulk


def _trace_for_artifacts(
    target_url: str,
    *,
    manifest: Mapping[str, Any],
    source_name: str,
    root: Path,
) -> DiscoveryTrace:
    report_path, candidates_path, unified_path = _artifact_paths(
        manifest,
        source_name=source_name,
        root=root,
    )
    raw_seen = bool(report_path and _json_contains_url(report_path, target_url))
    candidate_seen = bool(
        raw_seen and candidates_path and _json_contains_url(candidates_path, target_url)
    )
    unified_seen = bool(
        candidate_seen and unified_path and _json_contains_url(unified_path, target_url)
    )

    return DiscoveryTrace(
        # These are direct-source paths, so vocabulary/query learning must not be
        # blamed when the source collector itself failed to surface the exact URL.
        query_generated=True,
        search_hit=raw_seen,
        retrieved=True if raw_seen else None,
        timely_discovery=True,
        parsed=candidate_seen if raw_seen else None,
        entity_linked=True if candidate_seen else None,
        classified_relevant=True if candidate_seen else None,
        verified=unified_seen if candidate_seen else None,
        ranked=True if unified_seen else None,
        reported=False if unified_seen else None,
    )


def detect_verified_core_misses(
    checkpoint: Mapping[str, Any],
    manifest: Mapping[str, Any],
    source_verification: Mapping[str, Any],
    *,
    root: str | Path = ".",
) -> list[MissedOpportunityCase]:
    """Return conservative source-verified misses absent from the core checkpoint."""
    root_path = Path(root)
    known_urls = _checkpoint_urls(checkpoint)
    observed_at = _utc_from_report(source_verification.get("generated_at"))
    cases: list[MissedOpportunityCase] = []
    seen_urls: set[str] = set()

    for raw in source_verification.get("verifications") or []:
        if not isinstance(raw, Mapping) or not _verified_bulk_clothing(raw):
            continue
        source_kind = _compact(raw.get("source_kind"))
        market_code, source_name = _SOURCE_KIND_TO_SOURCE[source_kind]
        row_market = _compact(raw.get("country")).upper()
        if row_market and row_market != market_code:
            continue
        url = _canonical(raw.get("canonical_source_url") or raw.get("source_url"))
        if not url or url in known_urls or url in seen_urls:
            continue
        seen_urls.add(url)

        trace = _trace_for_artifacts(
            url,
            manifest=manifest,
            source_name=source_name,
            root=root_path,
        )
        evidence_text = _text_for_verification(raw)
        company = _compact(raw.get("target_label") or raw.get("case_title"))
        case = MissedOpportunityCase(
            case_id=(
                f"auto-miss:{market_code.casefold()}:"
                f"{sha256(url.encode('utf-8')).hexdigest()[:24]}"
            ),
            market_code=market_code,
            discovered_by="AUTOMATIC_SOURCE_VERIFIED_GAP_DETECTOR",
            observed_at=observed_at,
            opportunity_type="VERIFIED_BULK_CLOTHING_STOCK",
            stock_proven=True,
            ground_truth_company=company,
            ground_truth_url=url,
            trace=trace,
            learning_evidence_text=evidence_text,
        ).with_diagnosis()
        cases.append(case)

    return sorted(cases, key=lambda case: case.case_id)


def _merge_detected_cases(
    existing: Sequence[MissedOpportunityCase],
    detected: Sequence[MissedOpportunityCase],
) -> tuple[list[MissedOpportunityCase], int, int]:
    by_id = {case.case_id: case for case in existing if case.case_id}
    order = [case.case_id for case in existing if case.case_id]
    new_count = 0
    repeat_count = 0

    for case in detected:
        previous = by_id.get(case.case_id)
        if previous is None:
            by_id[case.case_id] = case
            order.append(case.case_id)
            new_count += 1
            continue
        if previous.learning_status == "RECOVERED" and not previous.repeat_miss:
            by_id[case.case_id] = replace(previous, repeat_miss=True)
            repeat_count += 1

    return [by_id[case_id] for case_id in order], new_count, repeat_count


def _attach_to_brief(output_dir: Path, report: Mapping[str, Any]) -> None:
    path = output_dir / "domain-market-intelligence-brief.json"
    brief = _read_object(path)
    if not brief:
        return
    brief["automatic_missed_opportunity_capture"] = {
        key: report.get(key)
        for key in (
            "schema_version",
            "status",
            "verified_candidate_count",
            "detected_miss_count",
            "new_case_count",
            "repeat_miss_count_this_run",
            "known_case_count_after",
            "root_cause_counts",
        )
    }
    _write_object(path, brief)


def write_automatic_missed_opportunity_capture(
    output_dir: str | Path,
    *,
    input_root: str | Path,
    root: str | Path = ".",
) -> dict[str, Any]:
    """Detect verified core misses, merge them into durable learning memory, and report."""
    output = Path(output_dir)
    checkpoint = _read_object(output / "multi-market-daily-checkpoint.json")
    manifest = _read_object(output / "input-manifest.json")
    verification = _read_object(output / "signal-follow-up-source-verification.json")

    detected = detect_verified_core_misses(
        checkpoint,
        manifest,
        verification,
        root=root,
    )
    memory_path = Path(input_root) / MEMORY_RELATIVE_PATH
    existing = load_missed_opportunity_memory(memory_path)
    merged, new_count, repeat_count = _merge_detected_cases(existing, detected)
    save_missed_opportunity_memory(memory_path, merged)

    eligible_verified = sum(
        1
        for raw in verification.get("verifications") or []
        if isinstance(raw, Mapping) and _verified_bulk_clothing(raw)
    )
    causes = Counter(case.root_cause or "UNDIAGNOSED" for case in detected)
    if not verification.get("verifications"):
        status = "VALID_ZERO_NO_SOURCE_VERIFICATIONS"
    elif not detected:
        status = "VALID_ZERO_NO_CORE_MISSES"
    else:
        status = "SUCCESS"

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "purpose": "CAPTURE_SOURCE_VERIFIED_BULK_CLOTHING_OPPORTUNITIES_MISSED_BY_CORE",
        "verified_candidate_count": eligible_verified,
        "detected_miss_count": len(detected),
        "new_case_count": new_count,
        "repeat_miss_count_this_run": repeat_count,
        "known_case_count_after": len(merged),
        "root_cause_counts": dict(sorted(causes.items())),
        "detected_cases": [case.to_dict() for case in detected],
        "memory_path": memory_path.as_posix(),
        "search_hit_alone_is_never_ground_truth": True,
        "single_item_is_never_bulk_stock_ground_truth": True,
        "source_page_verification_required": True,
        "automatic_query_activation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    _write_object(output / OUTPUT_FILENAME, report)
    _attach_to_brief(output, report)
    return report
