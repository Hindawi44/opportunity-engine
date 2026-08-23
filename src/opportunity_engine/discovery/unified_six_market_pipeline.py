"""Country-neutral pipeline ledger for the six active opportunity markets.

This module is an architectural migration layer. It does not re-run source
collectors, alter source truth, contact sellers, bid, reserve, buy, or pay. It
adapts the existing NO/SE/DE canonical checkpoint and the FR/IT/NL expansion
cycles into one ordered stage contract so every market exposes the same path.

The contract deliberately makes missing capabilities explicit. A market may
report NOT_IMPLEMENTED or BLOCKED_BY_* for a stage, but it may not silently
skip that stage. Later migrations can move execution behind this contract
without changing the operator-facing schema.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "unified-six-market-pipeline-1.0"
PIPELINE_CONTRACT = "UNIFIED_SIX_MARKET_PIPELINE_V1"
UNIFIED_MARKET_CODES = ("NO", "SE", "DE", "FR", "IT", "NL")
MARKET_CURRENCIES = {
    "NO": "NOK",
    "SE": "SEK",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "NL": "EUR",
}
STAGE_ORDER = (
    "DISCOVERY",
    "SIGNAL_VALIDATION",
    "ENTITY_RESOLUTION",
    "MEMORY",
    "FOLLOW_UP",
    "EXACT_LOT_VERIFICATION",
    "COMMERCIAL_QUALIFICATION",
    "EVIDENCE",
    "OPPORTUNITY_DECISION",
    "REPORT",
)


_SUCCESS = {"SUCCESS", "PASS", "OK", "COMPLETED"}
_ZERO = {
    "VALID_ZERO",
    "VALID_ZERO_RESULT",
    "VALID_ZERO_NO_RESULTS",
    "VALID_ZERO_NO_SIGNALS",
    "VALID_ZERO_NO_CASES",
}
_FAILURE = {"FAILED", "FAILURE", "ERROR"}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _status(value: object, *, zero_when_empty: bool = False, count: int | None = None) -> str:
    text = _compact(value).upper()
    if text in _SUCCESS:
        if zero_when_empty and count == 0:
            return "VALID_ZERO"
        return "SUCCESS"
    if text in _ZERO or text.startswith("VALID_ZERO"):
        return "VALID_ZERO"
    if text in _FAILURE:
        return "FAILURE"
    if text.startswith("SKIPPED"):
        return text
    if text:
        return text
    if zero_when_empty and count == 0:
        return "VALID_ZERO"
    return "UNKNOWN"


def _stage(name: str, status: str, **facts: Any) -> dict[str, Any]:
    return {"stage": name, "status": status, **facts}


def _core_market_row(core_report: Mapping[str, Any], market: Mapping[str, Any]) -> dict[str, Any]:
    code = _compact(market.get("market_code")).upper()
    if code not in {"NO", "SE", "DE"}:
        raise ValueError(f"Unsupported core market: {code!r}")

    execution_counts = market.get("source_execution_counts") or {}
    if not isinstance(execution_counts, Mapping):
        execution_counts = {}
    record_count = _int(market.get("deduplicated_record_count"))
    active_count = _int(market.get("active_count"))
    top5_count = _int(market.get("top5_eligible_count"))

    failures = _int(execution_counts.get("FAILURE"))
    successes = _int(execution_counts.get("SUCCESS"))
    zero_results = _int(execution_counts.get("VALID_ZERO_RESULT"))
    if failures:
        discovery_status = "FAILURE"
    elif record_count:
        discovery_status = "SUCCESS"
    elif successes or zero_results:
        discovery_status = "VALID_ZERO"
    else:
        discovery_status = "UNKNOWN"

    if top5_count:
        decision_status = "CANDIDATE_AVAILABLE"
    elif record_count:
        decision_status = "WATCH_ONLY"
    elif discovery_status == "VALID_ZERO":
        decision_status = "VALID_ZERO"
    elif discovery_status == "FAILURE":
        decision_status = "BLOCKED_BY_DISCOVERY_FAILURE"
    else:
        decision_status = "NOT_READY"

    stages = [
        _stage(
            "DISCOVERY",
            discovery_status,
            source_count=_int(market.get("source_count")),
            source_execution_counts=dict(execution_counts),
            deduplicated_record_count=record_count,
        ),
        _stage(
            "SIGNAL_VALIDATION",
            "ADAPTED_FROM_CANONICAL_PIPELINE",
            canonical_truth_preserved=True,
        ),
        _stage(
            "ENTITY_RESOLUTION",
            "ADAPTED_FROM_CANONICAL_PIPELINE",
            canonical_truth_preserved=True,
        ),
        _stage(
            "MEMORY",
            "ADAPTED_FROM_CANONICAL_PIPELINE",
            canonical_truth_preserved=True,
        ),
        _stage(
            "FOLLOW_UP",
            "ADAPTED_FROM_CANONICAL_PIPELINE",
            active_count=active_count,
        ),
        _stage(
            "EXACT_LOT_VERIFICATION",
            "ADAPTED_FROM_CANONICAL_PIPELINE",
            canonical_truth_preserved=True,
        ),
        _stage(
            "COMMERCIAL_QUALIFICATION",
            "ADAPTED_FROM_CANONICAL_PIPELINE",
            canonical_truth_preserved=True,
        ),
        _stage(
            "EVIDENCE",
            "ADAPTED_FROM_CANONICAL_PIPELINE",
            canonical_truth_preserved=True,
        ),
        _stage(
            "OPPORTUNITY_DECISION",
            decision_status,
            top5_eligible_count=top5_count,
            active_count=active_count,
        ),
        _stage("REPORT", "SUCCESS", source="MULTI_MARKET_OPERATOR_CHECKPOINT"),
    ]
    return _market_row(code, stages, currency=_compact(market.get("currency")))


def _expansion_market_row(code: str, cycle: Mapping[str, Any]) -> dict[str, Any]:
    accepted = _int(cycle.get("discovery_accepted_signal_count"))
    persistent = _int(cycle.get("persistent_case_count"))
    follow_up = cycle.get("follow_up") or {}
    if not isinstance(follow_up, Mapping):
        follow_up = {}
    case_count = _int(follow_up.get("case_count") or follow_up.get("follow_up_case_count"))
    commercial_leads = _int(follow_up.get("commercial_lead_count"))

    discovery_status = _status(
        cycle.get("discovery_status") or cycle.get("status"),
        zero_when_empty=True,
        count=accepted,
    )
    if discovery_status == "SUCCESS" and accepted == 0:
        discovery_status = "VALID_ZERO"

    signal_status = "SUCCESS" if accepted else (
        "VALID_ZERO" if discovery_status == "VALID_ZERO" else "BLOCKED_BY_DISCOVERY"
    )
    entity_status = "SUCCESS" if persistent else (
        "VALID_ZERO" if accepted == 0 else "REQUIRES_VERIFICATION"
    )
    memory_status = "SUCCESS" if persistent else (
        "VALID_ZERO" if accepted == 0 else "REQUIRES_VERIFICATION"
    )
    follow_status = _status(
        follow_up.get("status"),
        zero_when_empty=True,
        count=case_count,
    )
    if follow_status == "UNKNOWN":
        follow_status = "VALID_ZERO" if not persistent else "REQUIRES_VERIFICATION"

    exact_summary = cycle.get("exact_lot_verification") or {}
    if not isinstance(exact_summary, Mapping):
        exact_summary = {}
    explicit_exact_status = _compact(cycle.get("exact_lot_verification_status")).upper()
    if exact_summary:
        exact_status = _status(exact_summary.get("status"))
        verified_exact = _int(exact_summary.get("verified_active_exact_lot_lead_count"))
        exact_stage = _stage(
            "EXACT_LOT_VERIFICATION",
            exact_status,
            candidate_lead_count=_int(exact_summary.get("candidate_lead_count")),
            source_page_verified_count=_int(exact_summary.get("source_page_verified_count")),
            verified_active_exact_lot_count=verified_exact,
            engine_version=exact_summary.get("engine_version"),
        )
    elif "NOT_BUILT" in explicit_exact_status or "NOT_IMPLEMENTED" in explicit_exact_status:
        verified_exact = 0
        exact_stage = _stage(
            "EXACT_LOT_VERIFICATION",
            "NOT_IMPLEMENTED",
            capability_gap=explicit_exact_status or "SOURCE_SPECIFIC_VERIFIER_REQUIRED",
            verified_active_exact_lot_count=0,
        )
    else:
        verified_exact = 0
        exact_stage = _stage(
            "EXACT_LOT_VERIFICATION",
            "NOT_READY",
            verified_active_exact_lot_count=0,
        )

    qualification = cycle.get("commercial_qualification") or {}
    if not isinstance(qualification, Mapping):
        qualification = {}
    if qualification:
        qualification_count = _int(qualification.get("qualification_count"))
        financial_ready = _int(qualification.get("financial_decision_ready_count"))
        qualification_stage = _stage(
            "COMMERCIAL_QUALIFICATION",
            _status(qualification.get("status")),
            qualification_count=qualification_count,
            financial_decision_ready_count=financial_ready,
            engine_version=qualification.get("engine_version"),
        )
    elif exact_stage["status"] == "NOT_IMPLEMENTED":
        qualification_count = 0
        financial_ready = 0
        qualification_stage = _stage(
            "COMMERCIAL_QUALIFICATION",
            "BLOCKED_BY_EXACT_LOT",
            qualification_count=0,
            financial_decision_ready_count=0,
        )
    elif verified_exact:
        qualification_count = 0
        financial_ready = 0
        qualification_stage = _stage(
            "COMMERCIAL_QUALIFICATION",
            "NOT_IMPLEMENTED",
            qualification_count=0,
            financial_decision_ready_count=0,
        )
    else:
        qualification_count = 0
        financial_ready = 0
        qualification_stage = _stage(
            "COMMERCIAL_QUALIFICATION",
            "NOT_READY",
            qualification_count=0,
            financial_decision_ready_count=0,
        )

    if financial_ready:
        evidence_status = "READY"
        decision_status = "READY_FOR_HUMAN_DECISION"
    elif qualification_count:
        evidence_status = "REQUIRES_EVIDENCE"
        decision_status = "NOT_READY"
    elif qualification_stage["status"] == "BLOCKED_BY_EXACT_LOT":
        evidence_status = "BLOCKED_BY_COMMERCIAL_QUALIFICATION"
        decision_status = "NOT_READY"
    elif commercial_leads or verified_exact:
        evidence_status = "NOT_READY"
        decision_status = "NOT_READY"
    elif discovery_status == "VALID_ZERO":
        evidence_status = "VALID_ZERO"
        decision_status = "VALID_ZERO"
    else:
        evidence_status = "NOT_READY"
        decision_status = "NOT_READY"

    stages = [
        _stage(
            "DISCOVERY",
            discovery_status,
            accepted_signal_count=accepted,
        ),
        _stage(
            "SIGNAL_VALIDATION",
            signal_status,
            accepted_signal_count=accepted,
        ),
        _stage(
            "ENTITY_RESOLUTION",
            entity_status,
            persistent_case_count=persistent,
        ),
        _stage(
            "MEMORY",
            memory_status,
            persistent_case_count=persistent,
        ),
        _stage(
            "FOLLOW_UP",
            follow_status,
            case_count=case_count,
            commercial_lead_count=commercial_leads,
        ),
        exact_stage,
        qualification_stage,
        _stage("EVIDENCE", evidence_status),
        _stage(
            "OPPORTUNITY_DECISION",
            decision_status,
            financial_decision_ready_count=financial_ready,
        ),
        _stage("REPORT", "SUCCESS", source="DAILY_OPERATOR_CHECKPOINT"),
    ]
    return _market_row(code, stages, currency=MARKET_CURRENCIES[code])


def _market_row(code: str, stages: Sequence[Mapping[str, Any]], *, currency: str) -> dict[str, Any]:
    stage_names = tuple(_compact(stage.get("stage")) for stage in stages)
    if stage_names != STAGE_ORDER:
        raise ValueError(f"{code} stage order diverged from unified contract: {stage_names!r}")
    return {
        "market_code": code,
        "currency": currency or MARKET_CURRENCIES[code],
        "pipeline_contract": PIPELINE_CONTRACT,
        "stages": [dict(stage) for stage in stages],
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def build_unified_six_market_pipeline(
    core_report: Mapping[str, Any],
    *,
    france_sidecar: Mapping[str, Any],
    italy_sidecar: Mapping[str, Any],
    netherlands_sidecar: Mapping[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Adapt all six current market paths into one explicit ordered contract."""
    raw_core_markets = core_report.get("markets") or []
    if not isinstance(raw_core_markets, Sequence) or isinstance(raw_core_markets, (str, bytes)):
        raise ValueError("core_report.markets must be a sequence")
    core_index = {
        _compact(item.get("market_code")).upper(): item
        for item in raw_core_markets
        if isinstance(item, Mapping)
    }
    missing_core = [code for code in ("NO", "SE", "DE") if code not in core_index]
    if missing_core:
        raise ValueError(f"Core checkpoint is missing markets: {missing_core}")

    rows = [
        _core_market_row(core_report, core_index["NO"]),
        _core_market_row(core_report, core_index["SE"]),
        _core_market_row(core_report, core_index["DE"]),
        _expansion_market_row("FR", france_sidecar),
        _expansion_market_row("IT", italy_sidecar),
        _expansion_market_row("NL", netherlands_sidecar),
    ]
    now = generated_at or _compact(core_report.get("generated_at"))
    if not now:
        now = datetime.now(timezone.utc).isoformat()

    return {
        "schema_version": SCHEMA_VERSION,
        "pipeline_contract": PIPELINE_CONTRACT,
        "generated_at": now,
        "domain": "CLOTHING_INVENTORY",
        "market_coverage": list(UNIFIED_MARKET_CODES),
        "stage_order": list(STAGE_ORDER),
        "markets": rows,
        "country_specific_bypass_allowed": False,
        "source_truth_reclassified": False,
        "migration_mode": "ADAPT_EXISTING_EXECUTION_TO_ONE_CONTRACT",
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
