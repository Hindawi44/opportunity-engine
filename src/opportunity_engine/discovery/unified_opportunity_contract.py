"""Unified, source-agnostic opportunity contract.

This module introduces the first stable boundary shared by discovery, verification,
commercial evaluation, workflow, dashboards, and future market profiles. It is an
additive compatibility layer: existing discovery decisions and Top 5 behaviour are
not changed.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from opportunity_engine.discovery.e2e_checkpoint import CheckpointOutcome


SCHEMA_VERSION = "unified-opportunity-contract-v1"

ALLOWED_LISTING_STATUSES = frozenset(
    {"UNKNOWN", "ACTIVE", "ENDED", "REMOVED", "SOLD", "UNAVAILABLE"}
)
ALLOWED_VERIFICATION_STATUSES = frozenset(
    {"UNVERIFIED", "REQUIRES_VERIFICATION", "VERIFIED", "CONFLICTING_EVIDENCE"}
)
ALLOWED_COMMERCIAL_STATUSES = frozenset(
    {"NOT_ANALYZED", "WATCH", "QUALIFIED", "DISQUALIFIED"}
)
ALLOWED_WORKFLOW_STATUSES = frozenset(
    {"NEW", "WATCHING", "CONTACTED", "NEGOTIATING", "PURCHASED", "LOST", "ARCHIVED"}
)

_MARKET_CODE = re.compile(r"^[A-Z]{2}$")
_DECISION_TO_COMMERCIAL_STATUS = {
    "BUY_REVIEW": "QUALIFIED",
    "WATCH": "WATCH",
    "REJECT": "DISQUALIFIED",
}
_COST_FIELDS = (
    "asking_price_nok",
    "conservative_resale_value_nok",
    "total_cost_nok",
    "expected_profit_nok",
    "roi_percent",
    "maximum_safe_bid_nok",
    "target_profit_buffer_nok",
    "verified_operating_costs_nok",
)


class UnifiedOpportunityContractError(ValueError):
    """Raised when a V1 opportunity contract violates its stable boundary."""


def _non_empty_strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _source_name_from_url(url: str) -> str:
    hostname = (urlparse(url).hostname or "").casefold()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname


def _allowed_or_default(value: object, allowed: frozenset[str], default: str) -> str:
    candidate = str(value or "").strip().upper()
    return candidate if candidate in allowed else default


@dataclass(frozen=True, slots=True)
class UnifiedOpportunityContractV1:
    """Stable opportunity boundary without inventing missing commercial facts."""

    opportunity_id: str
    market: str
    source: dict[str, Any]
    identity: dict[str, Any]
    listing_status: str
    verification_status: str
    commercial_status: str
    workflow_status: str
    final_decision: str
    evidence: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    cost_estimate: dict[str, Any] = field(default_factory=dict)
    risk: dict[str, Any] = field(default_factory=dict)
    missing_information: tuple[str, ...] = field(default_factory=tuple)
    recommended_actions: tuple[str, ...] = field(default_factory=tuple)
    automatic_purchase_decision: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        errors: list[str] = []

        if self.schema_version != SCHEMA_VERSION:
            errors.append(f"schema_version must be {SCHEMA_VERSION}")
        if not isinstance(self.opportunity_id, str) or not self.opportunity_id.strip():
            errors.append("opportunity_id must be a non-empty string")
        if not isinstance(self.market, str) or _MARKET_CODE.fullmatch(self.market) is None:
            errors.append("market must be a two-letter uppercase country code")
        if self.listing_status not in ALLOWED_LISTING_STATUSES:
            errors.append(f"unsupported listing_status: {self.listing_status}")
        if self.verification_status not in ALLOWED_VERIFICATION_STATUSES:
            errors.append(f"unsupported verification_status: {self.verification_status}")
        if self.commercial_status not in ALLOWED_COMMERCIAL_STATUSES:
            errors.append(f"unsupported commercial_status: {self.commercial_status}")
        if self.workflow_status not in ALLOWED_WORKFLOW_STATUSES:
            errors.append(f"unsupported workflow_status: {self.workflow_status}")
        if not isinstance(self.final_decision, str) or not self.final_decision.strip():
            errors.append("final_decision must be a non-empty string")
        if not isinstance(self.source, dict):
            errors.append("source must be an object")
        else:
            source_name = self.source.get("name")
            source_url = self.source.get("url")
            if not isinstance(source_name, str) or not source_name.strip():
                errors.append("source.name must be a non-empty string")
            if not isinstance(source_url, str) or not source_url.startswith("https://"):
                errors.append("source.url must be a traceable HTTPS URL")
        if not isinstance(self.identity, dict):
            errors.append("identity must be an object")
        if not isinstance(self.cost_estimate, dict):
            errors.append("cost_estimate must be an object")
        if not isinstance(self.risk, dict):
            errors.append("risk must be an object")
        if not all(isinstance(item, dict) for item in self.evidence):
            errors.append("evidence must contain objects only")
        if not all(isinstance(item, str) and item.strip() for item in self.missing_information):
            errors.append("missing_information must contain non-empty strings only")
        if not all(isinstance(item, str) and item.strip() for item in self.recommended_actions):
            errors.append("recommended_actions must contain non-empty strings only")
        if self.automatic_purchase_decision:
            errors.append("automatic_purchase_decision must remain false")

        if errors:
            raise UnifiedOpportunityContractError("; ".join(errors))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready copy while preserving unknown values as null/empty."""
        return {
            "schema_version": self.schema_version,
            "opportunity_id": self.opportunity_id,
            "market": self.market,
            "source": deepcopy(self.source),
            "identity": deepcopy(self.identity),
            "listing_status": self.listing_status,
            "verification_status": self.verification_status,
            "commercial_status": self.commercial_status,
            "workflow_status": self.workflow_status,
            "evidence": deepcopy(list(self.evidence)),
            "cost_estimate": deepcopy(self.cost_estimate),
            "risk": deepcopy(self.risk),
            "final_decision": self.final_decision,
            "missing_information": list(self.missing_information),
            "recommended_actions": list(self.recommended_actions),
            "automatic_purchase_decision": self.automatic_purchase_decision,
        }

    @classmethod
    def from_checkpoint_outcome(
        cls,
        outcome: CheckpointOutcome,
        *,
        market: str = "NO",
        workflow_status: str = "NEW",
    ) -> UnifiedOpportunityContractV1:
        """Adapt the existing controlled checkpoint without changing its decision."""
        dossier = outcome.dossier
        confirmed = dossier.confirmed_facts
        canonical = outcome.canonical_opportunity or {}
        canonical_source = canonical.get("source") or {}

        listing_status = canonical_source.get("listing_status", "UNKNOWN")
        if listing_status not in ALLOWED_LISTING_STATUSES:
            listing_status = "UNKNOWN"

        if outcome.eligibility.eligible_for_analysis:
            verification_status = "VERIFIED"
            commercial_status = "NOT_ANALYZED"
        else:
            verification_status = "REQUIRES_VERIFICATION"
            commercial_status = "WATCH"

        source_url = str(confirmed.get("source_url") or canonical_source.get("url") or "")
        source_name = str(confirmed.get("source_name") or canonical_source.get("name") or "")
        source = {
            "name": source_name,
            "url": source_url,
            "title": confirmed.get("source_title") or canonical_source.get("title"),
            "description": confirmed.get("source_text") or canonical_source.get("description"),
        }
        identity = {
            "source_listing_id": canonical_source.get("listing_id"),
            "canonical_url": source_url,
            "domain": dossier.domain,
            "primary_scenario": dossier.primary_scenario,
        }

        evidence = tuple(
            {
                "kind": "DISCOVERY_SIGNAL",
                "value": signal,
                "source_url": source_url,
            }
            for signal in outcome.discovery_result.evidence
        )
        cost_estimate = deepcopy(canonical.get("verified_cost_evidence") or {})
        risk = {
            "unknown_fields": list(dossier.unknown_fields),
            "missing_evidence": list(dossier.missing_evidence),
            "eligibility_reason": outcome.eligibility.reason,
        }
        missing_information = tuple(
            dict.fromkeys((*dossier.unknown_fields, *dossier.missing_evidence))
        )

        return cls(
            opportunity_id=dossier.opportunity_id,
            market=market,
            source=source,
            identity=identity,
            listing_status=listing_status,
            verification_status=verification_status,
            commercial_status=commercial_status,
            workflow_status=workflow_status,
            evidence=evidence,
            cost_estimate=cost_estimate,
            risk=risk,
            final_decision="NO_DECISION",
            missing_information=missing_information,
            recommended_actions=dossier.seller_questions,
            automatic_purchase_decision=outcome.automatic_purchase_decision,
        )

    @classmethod
    def from_decision_intelligence_record(
        cls,
        record: dict[str, Any],
        *,
        market: str = "NO",
        workflow_status: str = "NEW",
    ) -> UnifiedOpportunityContractV1:
        """Adapt one official decision record without recomputing any decision."""
        if not isinstance(record, dict):
            raise UnifiedOpportunityContractError("decision record must be an object")

        opportunity_id = str(record.get("opportunity_id") or "").strip()
        source_url = str(record.get("url") or "").strip()
        source_name_raw = record.get("source_name") or record.get("source")
        if isinstance(source_name_raw, dict):
            source_name_raw = source_name_raw.get("name")
        source_name = str(source_name_raw or _source_name_from_url(source_url)).strip()
        final_decision = str(record.get("final_decision") or "").strip()

        listing_status = _allowed_or_default(
            record.get("listing_status"), ALLOWED_LISTING_STATUSES, "UNKNOWN"
        )
        explicit_verification = _allowed_or_default(
            record.get("verification_status"), ALLOWED_VERIFICATION_STATUSES, ""
        )
        missing_evidence = _non_empty_strings(record.get("missing_evidence"))
        if explicit_verification:
            verification_status = explicit_verification
        elif record.get("decision_confidence") == "HIGH" and not missing_evidence:
            verification_status = "VERIFIED"
        else:
            verification_status = "REQUIRES_VERIFICATION"

        commercial_status = _DECISION_TO_COMMERCIAL_STATUS.get(
            final_decision, "NOT_ANALYZED"
        )
        workflow_status = _allowed_or_default(
            record.get("workflow_status") or workflow_status,
            ALLOWED_WORKFLOW_STATUSES,
            "NEW",
        )

        source = {
            "name": source_name,
            "url": source_url,
            "title": record.get("title"),
            "description": record.get("description"),
            "city": record.get("city"),
        }
        identity = {
            "source_listing_id": record.get("listing_id") or opportunity_id,
            "canonical_url": source_url,
            "legacy_opportunity_id": opportunity_id,
        }

        evidence_items: list[dict[str, Any]] = []
        for reason in _non_empty_strings(record.get("reasons")):
            evidence_items.append({"kind": "DISCOVERY_REASON", "value": reason})
        for reason in _non_empty_strings(record.get("score_reasons")):
            evidence_items.append({"kind": "SCORE_REASON", "value": reason})
        for reason in _non_empty_strings(record.get("decision_reasons_ar")):
            evidence_items.append({"kind": "DECISION_REASON_AR", "value": reason})

        cost_estimate = {field_name: record.get(field_name) for field_name in _COST_FIELDS}
        risk = {
            "decision_confidence": record.get("decision_confidence"),
            "decision_warnings_ar": list(_non_empty_strings(record.get("decision_warnings_ar"))),
            "exclusion_reasons": list(_non_empty_strings(record.get("exclusion_reasons"))),
            "opportunity_score": record.get("opportunity_score"),
            "relevance_score": record.get("relevance_score"),
            "score_grade": record.get("score_grade"),
            "score_components": deepcopy(record.get("score_components") or {}),
            "top5_eligible": record.get("top5_eligible"),
            "analysis_eligible": record.get("analysis_eligible"),
            "legacy_recommendation": record.get("recommendation"),
            "official_decision_field": record.get("official_decision_field"),
        }
        missing_information = tuple(
            dict.fromkeys(
                (*missing_evidence, *_non_empty_strings(record.get("evidence_needed")))
            )
        )
        recommended_actions = _non_empty_strings(record.get("next_actions_ar"))
        automatic_purchase = bool(
            record.get("automatic_purchase_decision")
            or record.get("automatic_purchase")
        )

        return cls(
            opportunity_id=opportunity_id,
            market=market,
            source=source,
            identity=identity,
            listing_status=listing_status,
            verification_status=verification_status,
            commercial_status=commercial_status,
            workflow_status=workflow_status,
            evidence=tuple(evidence_items),
            cost_estimate=cost_estimate,
            risk=risk,
            final_decision=final_decision,
            missing_information=missing_information,
            recommended_actions=recommended_actions,
            automatic_purchase_decision=automatic_purchase,
        )
