"""Deterministic Mathematical Logic V1 shadow over the current project baseline.

This layer is deliberately descriptive before it is predictive.  It converts the
existing structured outputs into numeric feature vectors, readiness distances,
and funnel conversion measurements without interpreting free text, calling an
LLM/API, changing a score, or influencing the operator decision.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import mean, median
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "mathematical-logic-shadow-1.0"
ENGINE_VERSION = "MATHEMATICAL_LOGIC_V1"
OUTPUT_FILENAME = "mathematical-logic-shadow-v1.json"

CORE_MARKETS = ("NO", "SE", "DE")
EXPANSION_SIDECARS = ("IT", "NL", "FR")

# The V1 vector is intentionally unweighted.  A later law/model may only be
# selected after this representation has been tested on real outcomes.
READINESS_DIMENSIONS = (
    "source_reference_present",
    "market_identity_present",
    "evidence_present",
    "quantity_present",
    "price_present",
    "verification_gate_passed",
)

SIDECAR_FUNNELS: dict[str, tuple[tuple[str, str], ...]] = {
    "IT": (
        ("italy-market-discovery-v1.json", "accepted_signal_count"),
        ("italy-case-memory-v1.json", "persistent_case_count"),
        ("italy-signal-follow-up-v1.json", "commercial_lead_count"),
        ("italy-exact-lot-verification-v1.json", "verified_active_exact_lot_lead_count"),
        ("italy-commercial-qualification-v1.json", "qualification_count"),
        ("italy-commercial-qualification-v1.json", "financial_decision_ready_count"),
    ),
    "NL": (
        ("netherlands-market-discovery-v1.json", "accepted_signal_count"),
        ("netherlands-case-memory-v1.json", "persistent_case_count"),
        ("netherlands-signal-follow-up-v1.json", "commercial_lead_count"),
    ),
    "FR": (
        ("france-market-discovery-v1.json", "accepted_signal_count"),
        ("france-case-memory-v1.json", "persistent_case_count"),
        ("france-signal-follow-up-v1.json", "commercial_lead_count"),
    ),
}


def _as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _bounded_score(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return round(max(0.0, min(100.0, number)), 6)


def _nonnegative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        return 0
    return int(number)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _segment(case: Mapping[str, Any]) -> str:
    case_type = str(case.get("case_type") or "").upper()
    countries = {str(value or "").upper() for value in _as_list(case.get("countries"))}
    if case_type == "FABRIC_PROCUREMENT":
        return "FABRIC_PROCUREMENT"
    if countries.intersection(CORE_MARKETS):
        return "CORE_OPPORTUNITY_MARKETS"
    if countries.intersection(EXPANSION_SIDECARS):
        return "EXPANSION_SIDECARS"
    return "OTHER"


def _commercial_snapshot_counts(case: Mapping[str, Any]) -> tuple[int, int]:
    snapshot = _as_dict(case.get("commercial_snapshot"))
    return len(_as_list(snapshot.get("quantities"))), len(_as_list(snapshot.get("prices")))


def _case_row(case: Mapping[str, Any]) -> dict[str, Any]:
    gate = _as_dict(case.get("verification_gate"))
    required = _as_list(gate.get("required_evidence"))
    missing_required = _as_list(gate.get("missing_required_evidence"))
    quantities, prices = _commercial_snapshot_counts(case)
    source_names = [str(v) for v in _as_list(case.get("source_names")) if str(v or "").strip()]
    source_urls = [str(v) for v in _as_list(case.get("source_urls")) if str(v or "").strip()]
    countries = [str(v).upper() for v in _as_list(case.get("countries")) if str(v or "").strip()]
    evidence_count = _nonnegative_int(case.get("evidence_count"))
    item_count = max(1, _nonnegative_int(case.get("item_count")))

    vector = {
        "source_reference_present": bool(source_urls),
        "market_identity_present": bool(countries),
        "evidence_present": evidence_count > 0,
        "quantity_present": quantities > 0,
        "price_present": prices > 0,
        "verification_gate_passed": gate.get("gate_passed") is True,
    }
    known_dimension_count = sum(int(vector[name]) for name in READINESS_DIMENSIONS)
    dimension_count = len(READINESS_DIMENSIONS)

    return {
        "case_id": case.get("case_id"),
        "case_title": case.get("case_title"),
        "case_type": case.get("case_type"),
        "segment": _segment(case),
        "countries": sorted(set(countries)),
        "baseline": {
            "priority_class": case.get("priority_class"),
            "decision_lane": case.get("decision_lane"),
            "case_status": case.get("case_status"),
            "actionability_score": _bounded_score(case.get("actionability_score")),
            "commercial_strength": _bounded_score(case.get("commercial_strength")),
            "source_strength": _bounded_score(case.get("source_strength")),
            "verification_gate_passed": gate.get("gate_passed") is True,
        },
        "numeric_features": {
            "item_count": _nonnegative_int(case.get("item_count")),
            "evidence_count": evidence_count,
            "evidence_per_item": round(evidence_count / item_count, 6),
            "unique_source_count": len(set(source_names)),
            "source_url_count": len(set(source_urls)),
            "country_count": len(set(countries)),
            "missing_information_count": len(_as_list(case.get("missing_information"))),
            "risk_flag_count": len(_as_list(case.get("risk_flags"))),
            "quantity_observation_count": quantities,
            "price_observation_count": prices,
            "verification_required_count": len(required),
            "verification_missing_count": len(missing_required),
        },
        "readiness_vector": vector,
        "readiness": {
            "known_dimension_count": known_dimension_count,
            "dimension_count": dimension_count,
            "completeness_fraction": round(known_dimension_count / dimension_count, 6),
            "decision_distance": dimension_count - known_dimension_count,
        },
        "decision_influence": "NONE",
    }


def _distribution(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "case_count": 0,
            "mean_completeness": None,
            "median_completeness": None,
            "mean_decision_distance": None,
            "gate_pass_count": 0,
            "price_present_count": 0,
            "quantity_present_count": 0,
        }
    completeness = [float(_as_dict(row.get("readiness")).get("completeness_fraction") or 0.0) for row in rows]
    distances = [float(_as_dict(row.get("readiness")).get("decision_distance") or 0.0) for row in rows]
    return {
        "case_count": len(rows),
        "mean_completeness": round(mean(completeness), 6),
        "median_completeness": round(median(completeness), 6),
        "mean_decision_distance": round(mean(distances), 6),
        "gate_pass_count": sum(_as_dict(row.get("readiness_vector")).get("verification_gate_passed") is True for row in rows),
        "price_present_count": sum(_as_dict(row.get("readiness_vector")).get("price_present") is True for row in rows),
        "quantity_present_count": sum(_as_dict(row.get("readiness_vector")).get("quantity_present") is True for row in rows),
    }


def _group_distributions(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(field)
        if isinstance(value, list):
            values = [str(v) for v in value] or ["NONE"]
        else:
            values = [str(value or "NONE")]
        for group in values:
            grouped[group].append(row)
    return {key: _distribution(grouped[key]) for key in sorted(grouped)}


def _read_json_if_present(output_dir: Path, filename: str) -> Mapping[str, Any] | None:
    path = output_dir / filename
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _funnel_for_market(output_dir: Path, market: str) -> dict[str, Any]:
    stages: list[dict[str, Any]] = []
    previous_count: int | None = None
    for filename, field in SIDECAR_FUNNELS[market]:
        payload = _read_json_if_present(output_dir, filename)
        count = _nonnegative_int(payload.get(field)) if payload is not None else 0
        stage = {
            "artifact": filename,
            "field": field,
            "count": count,
            "artifact_present": payload is not None,
            "status": payload.get("status") if payload is not None else None,
            "conversion_from_previous": _ratio(count, previous_count) if previous_count is not None else None,
        }
        stages.append(stage)
        previous_count = count
    return {
        "market": market,
        "stage_count": len(stages),
        "stages": stages,
        "first_stage_count": stages[0]["count"] if stages else 0,
        "last_stage_count": stages[-1]["count"] if stages else 0,
        "end_to_end_conversion": _ratio(stages[-1]["count"], stages[0]["count"]) if stages else None,
    }


def build_mathematical_logic_shadow(
    cases_report: Mapping[str, Any],
    *,
    output_dir: str | Path | None = None,
    generated_at: datetime | None = None,
    baseline_commit: str | None = None,
) -> dict[str, Any]:
    """Build the V1 mathematical representation without changing any decision."""
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    raw_cases = _as_list(cases_report.get("cases"))
    rows = [_case_row(case) for case in raw_cases if isinstance(case, Mapping)]
    declared_count = cases_report.get("case_count")
    coverage_matches = declared_count in (None, len(rows))

    segment_counts = Counter(str(row["segment"]) for row in rows)
    baseline_priority_counts = Counter(str(_as_dict(row.get("baseline")).get("priority_class") or "NONE") for row in rows)
    baseline_gate_pass_count = sum(_as_dict(row.get("baseline")).get("verification_gate_passed") is True for row in rows)

    sidecar_funnels = {}
    if output_dir is not None:
        root = Path(output_dir)
        sidecar_funnels = {market: _funnel_for_market(root, market) for market in EXPANSION_SIDECARS}

    # This is not a new score/ranking.  It is a diagnostic list of cases closest
    # to completing the fixed six-dimensional representation.
    closest = sorted(
        rows,
        key=lambda row: (
            int(_as_dict(row.get("readiness")).get("decision_distance") or 0),
            -float(_as_dict(row.get("readiness")).get("completeness_fraction") or 0.0),
            -int(_as_dict(row.get("numeric_features")).get("unique_source_count") or 0),
            str(row.get("case_id") or ""),
        ),
    )[:10]

    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "generated_at": now.isoformat(),
        "baseline": {
            "mode": "FROZEN_CURRENT_PROJECT_OUTPUT",
            "commit_sha": baseline_commit,
            "source_schema_version": cases_report.get("schema_version"),
            "source_river_schema_version": cases_report.get("river_schema_version"),
            "declared_case_count": declared_count,
            "observed_case_count": len(rows),
            "coverage_matches_declared_count": coverage_matches,
            "priority_counts": dict(sorted(baseline_priority_counts.items())),
            "verification_gate_pass_count": baseline_gate_pass_count,
        },
        "methodology": {
            "stage": "MATHEMATICAL_LOGIC_ONLY",
            "language_logic_enabled": False,
            "probability_law_selected": False,
            "predictive_model_enabled": False,
            "feature_weighting_enabled": False,
            "llm_calls": 0,
            "external_api_calls": 0,
            "readiness_dimensions": list(READINESS_DIMENSIONS),
            "decision_influence": "NONE",
            "promotion_allowed": False,
        },
        "coverage": {
            "core_markets": list(CORE_MARKETS),
            "expansion_sidecars": list(EXPANSION_SIDECARS),
            "segment_counts": dict(sorted(segment_counts.items())),
            "sidecar_funnels_present": bool(sidecar_funnels),
        },
        "aggregate": {
            "all_cases": _distribution(rows),
            "by_segment": _group_distributions(rows, "segment"),
            "by_case_type": _group_distributions(rows, "case_type"),
            "by_country": _group_distributions(rows, "countries"),
        },
        "sidecar_funnels": sidecar_funnels,
        "closest_to_complete_representation": [
            {
                "case_id": row.get("case_id"),
                "case_title": row.get("case_title"),
                "segment": row.get("segment"),
                "decision_distance": _as_dict(row.get("readiness")).get("decision_distance"),
                "completeness_fraction": _as_dict(row.get("readiness")).get("completeness_fraction"),
                "baseline_priority_class": _as_dict(row.get("baseline")).get("priority_class"),
            }
            for row in closest
        ],
        "cases": rows,
        "safety": {
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_reservation": False,
            "automatic_purchase": False,
            "automatic_payment": False,
            "top5_changed": False,
            "primary_human_action_changed": False,
            "canonical_market_scope_changed": False,
        },
    }


def write_mathematical_logic_shadow(
    output_dir: str | Path,
    *,
    baseline_commit: str | None = None,
) -> dict[str, Any]:
    """Read the current unified cases and write one additive shadow artifact."""
    root = Path(output_dir)
    cases_path = root / "unified-market-cases.json"
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("unified-market-cases.json root must be an object")
    report = build_mathematical_logic_shadow(
        payload,
        output_dir=root,
        baseline_commit=baseline_commit,
    )
    root.mkdir(parents=True, exist_ok=True)
    (root / OUTPUT_FILENAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
