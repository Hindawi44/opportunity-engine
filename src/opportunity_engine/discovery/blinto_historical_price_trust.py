"""Final trust boundary for Blinto historical price observations.

Blinto may expose a bid value even when the bounded item description does not
match the advertised clothing lot. Raw source values remain traceable, but they
must not enter historical price analysis until the item-content match is trusted.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

_HISTORICAL_MARKET_EVIDENCE = "HISTORICAL_MARKET_EVIDENCE"
_HISTORICAL_MANUAL_REVIEW = "HISTORICAL_EVIDENCE_REQUIRES_MANUAL_REVIEW"


def _historical_trust(candidate: Mapping[str, Any]) -> bool | None:
    state = candidate.get("opportunity_state")
    if state == _HISTORICAL_MANUAL_REVIEW:
        return False
    if candidate.get("verification_content_match") is False:
        return False
    if (
        state == _HISTORICAL_MARKET_EVIDENCE
        and candidate.get("verification_content_match") is True
        and candidate.get("historical_data_fields_trusted") is True
        and candidate.get("historical_market_evidence_eligible") is True
    ):
        return True
    return None


def _without_public_price_claims(values: list[object]) -> list[str]:
    blocked_prefixes = (
        "public Blinto bid value:",
        "public Blinto reference value:",
        "raw Blinto bid value observed:",
        "raw Blinto reference value observed:",
    )
    return [
        str(value)
        for value in values
        if not str(value).startswith(blocked_prefixes)
    ]


def _sanitize_unmatched_verifications(candidate: dict[str, Any]) -> None:
    for verification in candidate.get("verification") or []:
        if not isinstance(verification, dict):
            continue
        if verification.get("verification_content_match") is not False:
            continue
        verification["inventory_type"] = None
        verification["quantity"] = None
        verification["price_nok"] = None
        verification["bid_price_nok"] = None
        verification["clothing_inventory_evidence"] = False
        verification["historical_data_fields_trusted"] = False
        verification["exclude_from_historical_price_analysis"] = True


def _apply_candidate_trust(candidate: dict[str, Any]) -> bool | None:
    trusted = _historical_trust(candidate)
    if trusted is None:
        return None

    confirmed = _without_public_price_claims(
        list(candidate.get("confirmed_information") or [])
    )
    bid = candidate.get("bid_price_sek")
    reference = candidate.get("reference_value_sek")

    candidate["exclude_from_historical_price_analysis"] = not trusted
    candidate["historical_price_analysis_exclusion_reason"] = (
        None if trusted else "verification_content_mismatch"
    )

    if bid is not None:
        candidate["bid_price_trusted"] = trusted
        if trusted:
            confirmed.append(f"public Blinto bid value: {bid} SEK")
        else:
            confirmed.append(
                f"raw Blinto bid value observed: {bid} SEK "
                "(excluded from historical price analysis)"
            )

    if reference is not None:
        candidate["reference_value_trusted"] = trusted
        if trusted:
            confirmed.append(
                f"public Blinto reference value: {reference} SEK "
                "(not current sale price)"
            )
        else:
            confirmed.append(
                f"raw Blinto reference value observed: {reference} SEK "
                "(excluded from historical price analysis)"
            )

    candidate["confirmed_information"] = list(dict.fromkeys(confirmed))

    if trusted:
        for verification in candidate.get("verification") or []:
            if not isinstance(verification, dict):
                continue
            if verification.get("verification_content_match") is True:
                verification["historical_data_fields_trusted"] = True
                verification["exclude_from_historical_price_analysis"] = False
    else:
        candidate["historical_market_evidence_eligible"] = False
        candidate["historical_data_fields_trusted"] = False
        _sanitize_unmatched_verifications(candidate)

    return trusted


def apply_blinto_historical_price_trust_gate(
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Mark raw Blinto prices trusted or excluded after source enrichment."""
    corrected = deepcopy(dict(result))
    trusted_candidates = 0
    excluded_candidates = 0
    excluded_bid_values = 0
    excluded_reference_values = 0

    for key in ("all_discovered_candidates", "discovery_top5"):
        for candidate in corrected.get(key) or []:
            if not isinstance(candidate, dict):
                continue
            trusted = _apply_candidate_trust(candidate)
            if key != "all_discovered_candidates" or trusted is None:
                continue
            if trusted:
                trusted_candidates += 1
            else:
                excluded_candidates += 1
                excluded_bid_values += int(candidate.get("bid_price_sek") is not None)
                excluded_reference_values += int(
                    candidate.get("reference_value_sek") is not None
                )

    report = corrected.get("search_run_report")
    if isinstance(report, dict):
        report["historical_price_trust_gate"] = {
            "source": "BLINTO",
            "applied": True,
            "trusted_historical_candidates": trusted_candidates,
            "excluded_historical_candidates": excluded_candidates,
            "excluded_bid_values": excluded_bid_values,
            "excluded_reference_values": excluded_reference_values,
        }
    return corrected
