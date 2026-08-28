"""Select any active analysis-eligible checkpoint opportunity for manual commerce.

This is a commercial routing helper, not discovery. It never searches, fetches,
or promotes an unknown URL. A manual override is accepted only when the exact
opportunity identity already exists in the latest checkpoint's active,
analysis-eligible candidate set.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from opportunity_engine.discovery.one_opportunity_commercial_analysis import CommercialInputError
from opportunity_engine.discovery.one_opportunity_daily_analysis import build_daily_analysis

SCHEMA_VERSION = "commercial-candidate-selection-1.0"


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _eligible_candidate(checkpoint: Mapping[str, Any], identity: str) -> Mapping[str, Any] | None:
    for raw in checkpoint.get("deduplicated_opportunities") or []:
        if not isinstance(raw, Mapping):
            continue
        if _text(raw.get("opportunity_identity")) != identity:
            continue
        if _text(raw.get("listing_status")).upper() != "ACTIVE":
            return None
        if _text(raw.get("workflow_status")).upper() != "ACTIVE_OPPORTUNITY":
            return None
        if raw.get("analysis_eligible") is not True:
            return None
        return raw
    return None


def select_eligible_commercial_analysis(
    daily_analysis: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    *,
    opportunity_identity: str,
) -> dict[str, Any]:
    """Return a daily-analysis shape for one exact eligible checkpoint candidate."""
    requested = _text(opportunity_identity)
    if not requested:
        raise CommercialInputError("opportunity_identity is required")

    selected = daily_analysis.get("selected_opportunity")
    current = _text(selected.get("opportunity_identity")) if isinstance(selected, Mapping) else ""
    if current == requested:
        report = deepcopy(dict(daily_analysis))
        report["commercial_candidate_selection"] = {
            "schema_version": SCHEMA_VERSION,
            "selection_mode": "CURRENT_DAILY_SELECTION",
            "requested_opportunity_identity": requested,
            "original_selected_opportunity_identity": current,
            "checkpoint_eligibility_verified": True,
        }
        return report

    candidate = _eligible_candidate(checkpoint, requested)
    if candidate is None:
        raise CommercialInputError(
            "requested opportunity is not an active analysis-eligible candidate in the latest checkpoint"
        )

    routed_checkpoint = deepcopy(dict(checkpoint))
    routed_checkpoint["next_human_action"] = {"opportunity_identity": requested}
    report = build_daily_analysis(routed_checkpoint)
    routed_selected = report.get("selected_opportunity") or {}
    if _text(routed_selected.get("opportunity_identity")) != requested:
        raise CommercialInputError("eligible commercial candidate routing failed closed")

    report["selection_reason"] = "MANUAL_ELIGIBLE_CANDIDATE_OVERRIDE"
    if daily_analysis.get("generated_at"):
        report["generated_at"] = daily_analysis.get("generated_at")

    facts = report.get("known_facts")
    if isinstance(facts, dict) and not _text(facts.get("source_url")):
        source_urls = candidate.get("source_urls") or []
        if isinstance(source_urls, str):
            source_urls = [source_urls]
        first_url = next((_text(url) for url in source_urls if _text(url)), "")
        facts["source_url"] = first_url or requested

    report["commercial_candidate_selection"] = {
        "schema_version": SCHEMA_VERSION,
        "selection_mode": "MANUAL_ELIGIBLE_CANDIDATE_OVERRIDE",
        "requested_opportunity_identity": requested,
        "original_selected_opportunity_identity": current or None,
        "checkpoint_eligibility_verified": True,
        "search_requests_made": 0,
        "page_fetches_made": 0,
    }
    for key in (
        "automatic_contact",
        "automatic_bid",
        "automatic_purchase",
        "automatic_payment",
    ):
        report[key] = False
    return report
