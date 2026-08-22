"""Read-only benchmark for externally verified stock opportunities.

This module answers one bounded question: did the current engine already know an
externally verified opportunity before we teach it anything?  It never adds a
source, mutates a query, promotes a learning, or performs a network request.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

SCHEMA_VERSION = "external-ground-truth-benchmark-1.0"
REPORT_SCHEMA_VERSION = "external-ground-truth-benchmark-report-1.0"


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
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.casefold(), parts.netloc.casefold(), path, parts.query, "")
    )


def _domain(value: object) -> str:
    raw = _compact(value)
    if not raw:
        return ""
    try:
        host = urlsplit(raw).hostname or ""
    except ValueError:
        return ""
    return host.casefold().rstrip(".")


def _walk_strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, Mapping):
        for child in value.values():
            yield from _walk_strings(child)
        return
    if isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk_strings(child)


def _baseline_index(documents: Mapping[str, object]) -> tuple[set[str], set[str]]:
    urls: set[str] = set()
    domains: set[str] = set()
    for document in documents.values():
        for text in _walk_strings(document):
            canonical = _canonical_url(text)
            if not canonical:
                continue
            urls.add(canonical)
            domain = _domain(canonical)
            if domain:
                domains.add(domain)
    return urls, domains


def evaluate_external_ground_truth(
    benchmark: Mapping[str, Any],
    *,
    documents: Mapping[str, object],
) -> dict[str, Any]:
    """Compare date-stamped external ground truth with engine artifacts.

    Exact URL presence means the baseline already knew the opportunity.  If a
    verified stock lot is absent and its source domain is absent too, the result
    is a conservative SOURCE_GAP.  If the domain is already visible but the
    exact lot is not, V1 labels SOURCE_COVERAGE_GAP rather than guessing a parser
    or verifier failure without a trace.
    """
    if benchmark.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported external ground-truth benchmark schema")
    raw_rows = benchmark.get("opportunities") or []
    if not isinstance(raw_rows, list):
        raise ValueError("external benchmark opportunities must be a list")

    known_urls, known_domains = _baseline_index(documents)
    cases: list[dict[str, Any]] = []
    causes: Counter[str] = Counter()

    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            continue
        source_url = _canonical_url(raw.get("source_url"))
        source_domain = _domain(source_url)
        stock_proven = raw.get("stock_proven") is True
        public_evidence_verified = raw.get("public_evidence_verified") is True
        baseline_found = bool(source_url and source_url in known_urls)
        source_domain_seen = bool(source_domain and source_domain in known_domains)
        confirmed_miss = bool(
            source_url
            and stock_proven
            and public_evidence_verified
            and not baseline_found
        )

        root_cause: str | None = None
        if confirmed_miss:
            root_cause = "SOURCE_COVERAGE_GAP" if source_domain_seen else "SOURCE_GAP"
            causes[root_cause] += 1

        cases.append(
            {
                "case_id": _compact(raw.get("case_id")),
                "source_name": _compact(raw.get("source_name")),
                "source_url": source_url,
                "evidence_url": _canonical_url(raw.get("evidence_url")),
                "title": _compact(raw.get("title")),
                "stock_proven": stock_proven,
                "public_evidence_verified": public_evidence_verified,
                "baseline_found": baseline_found,
                "source_domain_seen_by_baseline": source_domain_seen,
                "confirmed_miss": confirmed_miss,
                "root_cause": root_cause,
                "evidence": dict(raw.get("evidence") or {})
                if isinstance(raw.get("evidence"), Mapping)
                else {},
            }
        )

    baseline_found_count = sum(1 for case in cases if case["baseline_found"])
    confirmed_miss_count = sum(1 for case in cases if case["confirmed_miss"])
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "benchmark_schema_version": SCHEMA_VERSION,
        "captured_at": _compact(benchmark.get("captured_at")),
        "benchmark_count": len(cases),
        "baseline_found_count": baseline_found_count,
        "confirmed_miss_count": confirmed_miss_count,
        "coverage_rate": round(baseline_found_count / len(cases), 6) if cases else 0.0,
        "root_cause_counts": dict(sorted(causes.items())),
        "cases": cases,
        "purpose": "MEASURE_EXTERNAL_GROUND_TRUTH_BEFORE_ANY_LEARNING_OR_SOURCE_ADDITION",
        "automatic_promotion": False,
        "production_mutation": False,
        "network_requests": 0,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
