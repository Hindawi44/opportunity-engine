"""Shadow-only source learning from confirmed external SOURCE_GAP misses.

Repeated independent verified opportunities from the same previously unseen source
can validate that source as worth shadow evaluation. Validation never activates
or adds the source to production.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

SCHEMA_VERSION = "source-discovery-shadow-candidates-1.0"


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _canonical_url(value: object) -> str:
    raw = _compact(value)
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return ""
    if parts.scheme.casefold() not in {"http", "https"} or not parts.netloc:
        return ""
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            parts.path.rstrip("/") or "/",
            parts.query,
            "",
        )
    )


def _domain(value: object) -> str:
    try:
        host = urlsplit(_compact(value)).hostname or ""
    except ValueError:
        return ""
    return host.casefold().rstrip(".")


def _eligible_case_ids(benchmark_result: Mapping[str, Any]) -> set[str]:
    rows = benchmark_result.get("cases") or []
    if not isinstance(rows, list):
        return set()
    return {
        _compact(row.get("case_id"))
        for row in rows
        if isinstance(row, Mapping)
        and row.get("confirmed_miss") is True
        and _compact(row.get("root_cause")) == "SOURCE_GAP"
        and _compact(row.get("case_id"))
    }


def build_source_shadow_candidates(
    benchmark: Mapping[str, Any],
    benchmark_result: Mapping[str, Any],
    *,
    min_independent_opportunities: int = 2,
) -> dict[str, Any]:
    """Aggregate confirmed SOURCE_GAP misses into safe source candidates."""
    if benchmark.get("schema_version") != "external-ground-truth-benchmark-1.0":
        raise ValueError("unsupported external ground-truth benchmark schema")
    if min_independent_opportunities < 2:
        raise ValueError("min_independent_opportunities must be >= 2")

    eligible_ids = _eligible_case_ids(benchmark_result)
    opportunities = benchmark.get("opportunities") or []
    if not isinstance(opportunities, list):
        raise ValueError("external benchmark opportunities must be a list")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in opportunities:
        if not isinstance(raw, Mapping):
            continue
        case_id = _compact(raw.get("case_id"))
        if case_id not in eligible_ids:
            continue
        if raw.get("stock_proven") is not True or raw.get("public_evidence_verified") is not True:
            continue
        source_url = _canonical_url(raw.get("source_url"))
        source_domain = _domain(source_url)
        if not source_url or not source_domain:
            continue
        evidence = raw.get("evidence")
        category = ""
        if isinstance(evidence, Mapping):
            category = _compact(evidence.get("category")).upper()
        grouped[source_domain].append(
            {
                "case_id": case_id,
                "source_name": _compact(raw.get("source_name")),
                "source_url": source_url,
                "category": category,
            }
        )

    source_candidates: list[dict[str, Any]] = []
    for source_domain, rows in sorted(grouped.items()):
        by_url: dict[str, dict[str, Any]] = {}
        for row in rows:
            by_url.setdefault(row["source_url"], row)
        independent_rows = list(by_url.values())
        independent_rows.sort(key=lambda row: (row["case_id"], row["source_url"]))
        count = len(independent_rows)
        validated = count >= min_independent_opportunities
        source_names = sorted({row["source_name"] for row in independent_rows if row["source_name"]})
        categories = sorted({row["category"] for row in independent_rows if row["category"]})
        candidate_id = f"source-candidate:{sha256(source_domain.encode('utf-8')).hexdigest()[:20]}"
        source_candidates.append(
            {
                "candidate_id": candidate_id,
                "source_domain": source_domain,
                "source_name": source_names[0] if len(source_names) == 1 else None,
                "source_names": source_names,
                "verified_opportunity_count": count,
                "evidence_case_ids": sorted(row["case_id"] for row in independent_rows),
                "evidence_urls": sorted(row["source_url"] for row in independent_rows),
                "categories": categories,
                "status": "VALIDATED_SOURCE" if validated else "CANDIDATE",
                "shadow_eligible": validated,
                "validation_rule": (
                    f">={min_independent_opportunities} independent publicly verified stock opportunities"
                ),
                "production_active": False,
                "automatic_source_addition": False,
            }
        )

    validated_count = sum(1 for row in source_candidates if row["status"] == "VALIDATED_SOURCE")
    return {
        "schema_version": SCHEMA_VERSION,
        "source_candidate_count": len(source_candidates),
        "validated_source_count": validated_count,
        "shadow_eligible_source_count": sum(1 for row in source_candidates if row["shadow_eligible"]),
        "source_candidates": source_candidates,
        "learning_input": "CONFIRMED_EXTERNAL_SOURCE_GAP_MISSES_ONLY",
        "min_independent_opportunities": min_independent_opportunities,
        "automatic_source_addition": False,
        "automatic_promotion": False,
        "production_mutation": False,
        "network_requests": 0,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
