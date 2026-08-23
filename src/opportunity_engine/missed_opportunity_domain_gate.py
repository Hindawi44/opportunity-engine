"""Fail-closed project-domain gate for legacy missed-opportunity learning state.

Historical learning artifacts may predate PROJECT_DOMAIN_BOUNDARY_V1. This module
keeps those artifacts auditable while preventing cases without explicit clothing
or fabric evidence from participating in current learning, holdout proof, routing,
or retained Shadow overlays.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from opportunity_engine.missed_opportunity_learning import MissedOpportunityCase
from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
    classify_project_domain,
)

_ALLOWED_DOMAINS = {CLOTHING_INVENTORY, FABRIC_PROCUREMENT}


@dataclass(frozen=True, slots=True)
class DomainCasePartition:
    allowed: tuple[MissedOpportunityCase, ...]
    excluded: tuple[MissedOpportunityCase, ...]

    @property
    def excluded_case_ids(self) -> list[str]:
        return sorted({case.case_id for case in self.excluded if case.case_id})


def classify_missed_opportunity_case_domain(case: MissedOpportunityCase) -> str:
    """Classify only evidence that can actually prove the project's product domain.

    Company names and URLs are intentionally excluded: a retailer name or domain
    cannot prove that the missed inventory was clothing or fabric. A structured
    opportunity type may establish scope when it explicitly names clothing/fabric;
    underscores/hyphens are normalized to word separators before text matching.
    """
    opportunity_type = (
        str(case.opportunity_type or "").replace("_", " ").replace("-", " ").strip()
    )
    evidence = " ".join(
        part
        for part in (
            opportunity_type,
            str(case.learning_evidence_text or "").strip(),
        )
        if part
    )
    return classify_project_domain(text=evidence)


def partition_project_domain_cases(
    cases: Sequence[MissedOpportunityCase],
) -> DomainCasePartition:
    allowed: list[MissedOpportunityCase] = []
    excluded: list[MissedOpportunityCase] = []
    for case in cases:
        if classify_missed_opportunity_case_domain(case) in _ALLOWED_DOMAINS:
            allowed.append(case)
        else:
            excluded.append(case)
    return DomainCasePartition(tuple(allowed), tuple(excluded))


def _ids(value: object) -> list[str]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return []
    return sorted({str(item).strip() for item in value if str(item).strip()})


def quarantine_learning_overlay(
    overlay: Mapping[str, Any] | None,
    *,
    allowed_support_case_ids: set[str],
    allowed_validation_case_ids: set[str],
) -> tuple[dict[str, Any], list[str]]:
    """Remove retained learning whose supporting domain proof is no longer valid.

    A row must retain at least one in-domain source/support case. HOLDOUT_TRANSFER
    evidence must also retain at least one in-domain validation case. This makes
    old broad-retail proof fail closed rather than continuing to appear PROVEN.
    """
    source = dict(overlay or {})
    raw_markets = source.get("markets")
    if not isinstance(raw_markets, Mapping):
        raw_markets = {}

    cleaned_markets: dict[str, list[dict[str, Any]]] = {}
    excluded_terms: list[str] = []

    for raw_market, raw_rows in raw_markets.items():
        market = str(raw_market or "").strip().upper()
        if not market or not isinstance(raw_rows, list):
            continue
        cleaned_rows: list[dict[str, Any]] = []
        for raw in raw_rows:
            if not isinstance(raw, Mapping):
                continue
            row = dict(raw)
            term = " ".join(str(row.get("term") or "").casefold().split()).strip()
            if not term:
                continue

            support_ids = [
                case_id
                for case_id in _ids(row.get("support_case_ids"))
                if case_id in allowed_support_case_ids
            ]
            if not support_ids:
                excluded_terms.append(f"{market}:{term}")
                continue

            scope = str(row.get("evaluation_scope") or "SOURCE_CASE_REPLAY").strip().upper()
            scopes = {item.upper() for item in _ids(row.get("evaluation_scopes"))}
            if scope:
                scopes.add(scope)

            transfer_ids = [
                case_id
                for case_id in _ids(row.get("transfer_validation_case_ids"))
                if case_id in allowed_validation_case_ids
            ]
            if "HOLDOUT_TRANSFER" in scopes and not transfer_ids:
                excluded_terms.append(f"{market}:{term}")
                continue

            source_replay_ids = [
                case_id
                for case_id in _ids(row.get("source_replay_case_ids"))
                if case_id in allowed_support_case_ids
            ]
            if scope != "HOLDOUT_TRANSFER" and not source_replay_ids:
                source_replay_ids = [
                    case_id
                    for case_id in _ids(row.get("recovered_case_ids"))
                    if case_id in allowed_support_case_ids
                ]

            row["support_case_ids"] = sorted(support_ids)
            row["transfer_validation_case_ids"] = sorted(transfer_ids)
            row["source_replay_case_ids"] = sorted(source_replay_ids)
            row["recovered_case_ids"] = sorted(set(transfer_ids) | set(source_replay_ids))
            row["independent_transfer_case_count"] = len(transfer_ids)
            cleaned_rows.append(row)

        if cleaned_rows:
            cleaned_markets[market] = cleaned_rows

    cleaned = dict(source)
    cleaned["markets"] = cleaned_markets
    cleaned["active_term_count"] = sum(len(rows) for rows in cleaned_markets.values())
    cleaned["automatic_query_activation"] = False
    cleaned["automatic_financial_action"] = False
    cleaned["automatic_contact"] = False
    cleaned["automatic_bid"] = False
    cleaned["automatic_purchase"] = False
    cleaned["automatic_payment"] = False
    return cleaned, sorted(set(excluded_terms))
