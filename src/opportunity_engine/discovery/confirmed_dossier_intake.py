"""Source-agnostic intake for confirmed active Clothing Inventory dossiers.

The intake validates a human-verified, machine-readable evidence package before
creating any Discovery or Opportunity Dossier object. Missing decision evidence
remains unknown and the opportunity is retained for later evidence collection.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from opportunity_engine.discovery.classifier import to_canonical_opportunity
from opportunity_engine.discovery.e2e_checkpoint import (
    CheckpointOutcome,
    OpportunityDossier,
    build_opportunity_dossier,
    evaluate_analysis_eligibility,
)
from opportunity_engine.discovery.models import DiscoveryCandidate, DiscoveryResult


SCHEMA_VERSION = "confirmed-clothing-inventory-dossier-intake-v1"
EXECUTION_MODE = "CONFIRMED_DOSSIER_INTAKE"

EXPECTED_DOMAIN = "CLOTHING_INVENTORY"
EXPECTED_RECORD_TYPE = "SALE_LISTING"
EXPECTED_QUALIFICATION_STATUS = "SALE_CONFIRMED"
EXPECTED_OPPORTUNITY_STATUS = "CONFIRMED_ACTIVE_CLOTHING_INVENTORY_OPPORTUNITY"
EXPECTED_LISTING_STATUS = "ACTIVE"

DOSSIER_STATUS = "DOSSIER_EVIDENCE_REQUIRED"
FINAL_OUTCOME = "EVIDENCE_REQUIRED"
FINAL_DECISION = "NO_DECISION"

ALLOWED_SCENARIOS = {
    "STORE_CLOSING",
    "COMPANY_BANKRUPTCY",
    "INVENTORY_LIQUIDATION",
    "AUCTION",
    "WAREHOUSE_SURPLUS",
    "IMPORTER_LIQUIDATION",
    "MANUFACTURER_EXCESS",
    "LARGE_LOT_SALE",
    "BUSINESS_MODEL_CHANGE",
    "BRANCH_CLOSURE",
}

ALLOWED_CLASSIFICATIONS = {
    "CONFIRMED_SOURCE_FACT",
    "CONFIRMED_IMAGE_FACT",
    "SELLER_CLAIM_UNVERIFIED",
    "UNKNOWN",
    "CONFLICTING_EVIDENCE",
}

CONFIRMED_CLASSIFICATIONS = {
    "CONFIRMED_SOURCE_FACT",
    "CONFIRMED_IMAGE_FACT",
}
CANDIDATE_SELLER_CLAIM_CLASSIFICATIONS = {
    "CONFIRMED_SOURCE_FACT",
    "CONFIRMED_IMAGE_FACT",
    "SELLER_CLAIM_UNVERIFIED",
}

REQUIRED_FIELD_KEYS = {
    "location",
    "what_is_sold",
    "quantity",
    "asking_price_nok",
    "contact",
    "vat_statement",
    "buyer_fees_nok",
    "condition",
    "pickup_terms",
    "packing_terms",
    "transport_terms",
}

ALLOWED_PROVENANCE_KINDS = {
    "PUBLIC_WEB_PAGE",
    "PUBLIC_COMPANY_RECORD",
    "PUBLIC_BANKRUPTCY_RECORD",
    "PUBLIC_IMAGE",
    "PUBLIC_ATTACHMENT",
    "HUMAN_VERIFIED_EVIDENCE_PACKAGE",
}

WEB_PROVENANCE_KINDS = {
    "PUBLIC_WEB_PAGE",
    "PUBLIC_COMPANY_RECORD",
    "PUBLIC_BANKRUPTCY_RECORD",
    "PUBLIC_IMAGE",
}

SAFETY_KEYS = {
    "automatic_purchase_decision",
    "automatic_bid",
    "automatic_contact",
    "automatic_reservation",
    "automatic_payment",
}


@dataclass(frozen=True, slots=True)
class IntakeValidationOutcome:
    """Structured validation result used by the CLI and focused tests."""

    status: str
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "errors": list(self.errors)}


class ConfirmedDossierIntakeError(ValueError):
    """Raised when confirmed-dossier intake validation fails."""

    def __init__(self, status: str, errors: Iterable[str]):
        self.outcome = IntakeValidationOutcome(status=status, errors=tuple(errors))
        message = "; ".join(self.outcome.errors) or status
        super().__init__(message)

    @property
    def status(self) -> str:
        return self.outcome.status

    @property
    def errors(self) -> tuple[str, ...]:
        return self.outcome.errors

    def to_dict(self) -> dict[str, Any]:
        return self.outcome.to_dict()


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _aware_iso_timestamp(value: object) -> bool:
    if not _is_non_empty_string(value):
        return False
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _https_hostname(value: object) -> str | None:
    if not _is_non_empty_string(value):
        return None
    parsed = urlparse(str(value).strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return None
    return parsed.hostname.casefold().rstrip(".")


def _string_list(value: object, *, allow_empty: bool = True) -> bool:
    if not isinstance(value, list):
        return False
    if not allow_empty and not value:
        return False
    return all(_is_non_empty_string(item) for item in value)


def _dedupe_strings(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if _is_non_empty_string(value)))


def _raise(status: str, errors: list[str]) -> None:
    raise ConfirmedDossierIntakeError(status, errors)


def _validate_top_level(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    required = {
        "schema_version",
        "opportunity_id",
        "domain",
        "primary_scenario",
        "record_type",
        "qualification_status",
        "opportunity_status",
        "listing_status",
        "title",
        "description",
        "observed_at",
        "source",
        "fields",
        "supported_inferences",
        "missing_evidence",
        "seller_questions",
        "provenance",
        "safety",
    }
    missing = sorted(required - payload.keys())
    if missing:
        errors.append("missing top-level keys: " + ", ".join(missing))

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not _is_non_empty_string(payload.get("opportunity_id")):
        errors.append("opportunity_id must be a non-empty string")
    if payload.get("domain") != EXPECTED_DOMAIN:
        errors.append(f"domain must be {EXPECTED_DOMAIN}")
    if payload.get("primary_scenario") not in ALLOWED_SCENARIOS:
        errors.append("primary_scenario is not an approved Clothing Inventory scenario")
    if not _is_non_empty_string(payload.get("title")):
        errors.append("title must be a non-empty string")
    description = payload.get("description")
    if description is not None and not isinstance(description, str):
        errors.append("description must be a string or null")
    if not _aware_iso_timestamp(payload.get("observed_at")):
        errors.append("observed_at must be a timezone-aware ISO-8601 timestamp")

    for key in ("source", "fields", "provenance", "safety"):
        if not isinstance(payload.get(key), dict):
            errors.append(f"{key} must be an object")
    for key in ("supported_inferences", "missing_evidence", "seller_questions"):
        if not isinstance(payload.get(key), list):
            errors.append(f"{key} must be a list")

    if errors:
        _raise("INTAKE_VALIDATION_FAILED", errors)


def _validate_statuses(payload: dict[str, Any]) -> None:
    if payload.get("listing_status") != EXPECTED_LISTING_STATUS:
        _raise(
            "INTAKE_REJECTED_NOT_ACTIVE",
            [f"listing_status must be {EXPECTED_LISTING_STATUS}"],
        )

    errors: list[str] = []
    if payload.get("record_type") != EXPECTED_RECORD_TYPE:
        errors.append(f"record_type must be {EXPECTED_RECORD_TYPE}")
    if payload.get("qualification_status") != EXPECTED_QUALIFICATION_STATUS:
        errors.append(
            f"qualification_status must be {EXPECTED_QUALIFICATION_STATUS}"
        )
    if payload.get("opportunity_status") != EXPECTED_OPPORTUNITY_STATUS:
        errors.append(f"opportunity_status must be {EXPECTED_OPPORTUNITY_STATUS}")
    if errors:
        _raise("INTAKE_REJECTED_NOT_CONFIRMED", errors)


def _validate_provenance(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    provenance = payload["provenance"]
    records = provenance.get("records")
    if not isinstance(records, list) or not records:
        _raise(
            "INTAKE_REJECTED_UNTRACEABLE",
            ["provenance.records must contain at least one evidence record"],
        )

    errors: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        prefix = f"provenance.records[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix} must be an object")
            continue

        evidence_id = record.get("evidence_id")
        if not _is_non_empty_string(evidence_id):
            errors.append(f"{prefix}.evidence_id must be a non-empty string")
            continue
        evidence_id = str(evidence_id).strip()
        if evidence_id in by_id:
            errors.append(f"duplicate evidence_id: {evidence_id}")
            continue

        kind = record.get("kind")
        if kind not in ALLOWED_PROVENANCE_KINDS:
            errors.append(f"{prefix}.kind is not allowed")

        url = record.get("url")
        file_reference = record.get("file_reference")
        if kind in WEB_PROVENANCE_KINDS and _https_hostname(url) is None:
            errors.append(f"{prefix}.url must be a traceable HTTPS URL")
        elif url is not None and _https_hostname(url) is None:
            errors.append(f"{prefix}.url must be HTTPS when supplied")

        if kind == "HUMAN_VERIFIED_EVIDENCE_PACKAGE":
            if not _is_non_empty_string(file_reference):
                errors.append(
                    f"{prefix}.file_reference is required for a human-verified package"
                )
        elif kind == "PUBLIC_ATTACHMENT":
            if _https_hostname(url) is None and not _is_non_empty_string(file_reference):
                errors.append(
                    f"{prefix} requires an HTTPS URL or preserved file_reference"
                )

        if not _aware_iso_timestamp(record.get("observed_at")):
            errors.append(
                f"{prefix}.observed_at must be a timezone-aware ISO-8601 timestamp"
            )
        if not _string_list(record.get("supports"), allow_empty=True):
            errors.append(f"{prefix}.supports must be a list of non-empty strings")

        by_id[evidence_id] = record

    if errors:
        _raise("INTAKE_REJECTED_UNTRACEABLE", errors)
    return by_id


def _validate_source(
    payload: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> None:
    source = payload["source"]
    errors: list[str] = []

    if not _is_non_empty_string(source.get("name")):
        errors.append("source.name must be a non-empty string")
    if not _is_non_empty_string(source.get("source_type")):
        errors.append("source.source_type must be a non-empty string")

    hostname = _https_hostname(source.get("primary_url"))
    if hostname is None:
        errors.append("source.primary_url must be a traceable HTTPS URL")
    source_domain = source.get("source_domain")
    if not _is_non_empty_string(source_domain):
        errors.append("source.source_domain must be a non-empty string")
    elif hostname is not None and str(source_domain).casefold().rstrip(".") != hostname:
        errors.append("source.source_domain must match source.primary_url hostname")

    refs = source.get("evidence_refs")
    if not _string_list(refs, allow_empty=False):
        errors.append("source.evidence_refs must contain at least one evidence ID")
    else:
        unresolved = sorted(set(refs) - evidence_by_id.keys())
        if unresolved:
            errors.append(
                "source.evidence_refs contain unknown IDs: " + ", ".join(unresolved)
            )

    if errors:
        _raise("INTAKE_REJECTED_UNTRACEABLE", errors)


def _validate_fields(
    payload: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> None:
    fields = payload["fields"]
    errors: list[str] = []

    missing = sorted(REQUIRED_FIELD_KEYS - fields.keys())
    if missing:
        errors.append("missing required field envelopes: " + ", ".join(missing))

    for key, envelope in fields.items():
        prefix = f"fields.{key}"
        if not isinstance(envelope, dict):
            errors.append(f"{prefix} must be an evidence envelope")
            continue

        classification = envelope.get("classification")
        value = envelope.get("value")
        refs = envelope.get("evidence_refs")

        if classification not in ALLOWED_CLASSIFICATIONS:
            errors.append(f"{prefix}.classification is not allowed")
            continue
        if not _string_list(refs, allow_empty=True):
            errors.append(f"{prefix}.evidence_refs must be a list of evidence IDs")
            continue

        unresolved = sorted(set(refs) - evidence_by_id.keys())
        if unresolved:
            errors.append(
                f"{prefix}.evidence_refs contain unknown IDs: "
                + ", ".join(unresolved)
            )

        if value is None:
            if classification != "UNKNOWN" or refs:
                errors.append(
                    f"{prefix} null values require UNKNOWN and empty evidence_refs"
                )
        elif classification == "UNKNOWN":
            errors.append(f"{prefix} non-null values may not use UNKNOWN")

        if classification in (
            "CONFIRMED_SOURCE_FACT",
            "CONFIRMED_IMAGE_FACT",
            "SELLER_CLAIM_UNVERIFIED",
        ) and not refs:
            errors.append(f"{prefix} classification requires evidence_refs")
        if classification == "CONFLICTING_EVIDENCE" and len(refs) < 2:
            errors.append(
                f"{prefix} conflicting evidence requires at least two evidence_refs"
            )

        if key == "quantity" and value is not None:
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                errors.append(f"{prefix}.value must be a positive integer or null")
            unit = envelope.get("unit")
            if unit is not None and not _is_non_empty_string(unit):
                errors.append(f"{prefix}.unit must be a non-empty string when supplied")

        if key in {"asking_price_nok", "buyer_fees_nok"} and value is not None:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
            ):
                errors.append(
                    f"{prefix}.value must be a non-negative number or null"
                )

    if errors:
        status = (
            "INTAKE_REJECTED_UNTRACEABLE"
            if any("unknown IDs" in error for error in errors)
            else "INTAKE_VALIDATION_FAILED"
        )
        _raise(status, errors)


def _validate_inferences(
    payload: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> None:
    errors: list[str] = []
    for index, inference in enumerate(payload["supported_inferences"]):
        prefix = f"supported_inferences[{index}]"
        if not isinstance(inference, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if not _is_non_empty_string(inference.get("field")):
            errors.append(f"{prefix}.field must be a non-empty string")
        if inference.get("value") is None:
            errors.append(f"{prefix}.value must not be null")
        if inference.get("confidence") not in {"LOW", "MEDIUM", "HIGH"}:
            errors.append(f"{prefix}.confidence must be LOW, MEDIUM, or HIGH")
        if not _is_non_empty_string(inference.get("reason")):
            errors.append(f"{prefix}.reason must be a non-empty string")
        refs = inference.get("evidence_refs")
        if not _string_list(refs, allow_empty=False):
            errors.append(f"{prefix}.evidence_refs must not be empty")
            continue
        unresolved = sorted(set(refs) - evidence_by_id.keys())
        if unresolved:
            errors.append(
                f"{prefix}.evidence_refs contain unknown IDs: "
                + ", ".join(unresolved)
            )

    if errors:
        status = (
            "INTAKE_REJECTED_UNTRACEABLE"
            if any("unknown IDs" in error for error in errors)
            else "INTAKE_VALIDATION_FAILED"
        )
        _raise(status, errors)


def _validate_lists_and_safety(payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if not _string_list(payload["missing_evidence"], allow_empty=True):
        errors.append("missing_evidence must be a list of non-empty strings")
    if not _string_list(payload["seller_questions"], allow_empty=True):
        errors.append("seller_questions must be a list of non-empty strings")

    safety = payload["safety"]
    if set(safety) != SAFETY_KEYS:
        errors.append("safety must contain exactly the approved automatic-action keys")
    for key in SAFETY_KEYS:
        if safety.get(key) is not False:
            errors.append(f"safety.{key} must be false")

    if errors:
        _raise("INTAKE_VALIDATION_FAILED", errors)


def validate_confirmed_dossier_intake(payload: object) -> dict[str, Any]:
    """Validate and return one confirmed active intake payload.

    Validation happens completely before DiscoveryCandidate, DiscoveryResult, or
    OpportunityDossier construction.
    """
    if not isinstance(payload, dict):
        _raise("INTAKE_VALIDATION_FAILED", ["intake payload must be a JSON object"])

    _validate_top_level(payload)
    _validate_statuses(payload)
    evidence_by_id = _validate_provenance(payload)
    _validate_source(payload, evidence_by_id)
    _validate_fields(payload, evidence_by_id)
    _validate_inferences(payload, evidence_by_id)
    _validate_lists_and_safety(payload)
    return payload


def load_confirmed_dossier_intake(path: Path) -> dict[str, Any]:
    """Load and validate one JSON intake file."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _raise("INTAKE_VALIDATION_FAILED", [f"unable to load intake JSON: {exc}"])
    return validate_confirmed_dossier_intake(payload)


def _field_value(
    fields: dict[str, dict[str, Any]],
    key: str,
    allowed_classifications: set[str],
) -> Any:
    envelope = fields[key]
    if envelope["classification"] in allowed_classifications:
        return envelope["value"]
    return None


def _build_candidate_and_result(
    payload: dict[str, Any],
) -> tuple[DiscoveryCandidate, DiscoveryResult]:
    fields = payload["fields"]
    candidate = DiscoveryCandidate(
        title=payload["title"].strip(),
        url=payload["source"]["primary_url"].strip(),
        source=payload["source"]["name"].strip(),
        discovered_at=payload["observed_at"].strip(),
        text=(payload.get("description") or payload["title"]).strip(),
        location=_field_value(fields, "location", CONFIRMED_CLASSIFICATIONS),
        quantity=_field_value(
            fields,
            "quantity",
            CANDIDATE_SELLER_CLAIM_CLASSIFICATIONS,
        ),
        price_nok=_field_value(
            fields,
            "asking_price_nok",
            CANDIDATE_SELLER_CLAIM_CLASSIFICATIONS,
        ),
        contact=_field_value(fields, "contact", CONFIRMED_CLASSIFICATIONS),
    )
    result = DiscoveryResult(
        candidate=candidate,
        scenario=payload["primary_scenario"],
        record_type=EXPECTED_RECORD_TYPE,
        status=EXPECTED_QUALIFICATION_STATUS,
        reason="confirmed active opportunity intake validated",
        evidence=tuple(payload["source"]["evidence_refs"]),
    )
    return candidate, result


def _classified_field_groups(
    fields: dict[str, dict[str, Any]],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, dict[str, Any]],
    tuple[str, ...],
    dict[str, dict[str, Any]],
]:
    confirmed: dict[str, Any] = {}
    seller_claims: dict[str, Any] = {}
    conflicts: dict[str, dict[str, Any]] = {}
    unknowns: list[str] = []
    field_evidence: dict[str, dict[str, Any]] = {}

    for key, envelope in fields.items():
        classification = envelope["classification"]
        field_evidence[key] = {
            "classification": classification,
            "evidence_refs": list(envelope["evidence_refs"]),
        }
        if "unit" in envelope:
            field_evidence[key]["unit"] = envelope.get("unit")

        if classification in CONFIRMED_CLASSIFICATIONS:
            confirmed[key] = envelope["value"]
        elif classification == "SELLER_CLAIM_UNVERIFIED":
            seller_claims[key] = envelope["value"]
        elif classification == "CONFLICTING_EVIDENCE":
            conflicts[key] = {
                "value": envelope["value"],
                "classification": classification,
                "evidence_refs": list(envelope["evidence_refs"]),
            }
        elif classification == "UNKNOWN":
            unknowns.append(key)

    return confirmed, seller_claims, conflicts, tuple(unknowns), field_evidence


def _enrich_dossier(
    *,
    payload: dict[str, Any],
    baseline: OpportunityDossier,
) -> OpportunityDossier:
    (
        confirmed_fields,
        seller_claim_fields,
        conflicts,
        unknown_fields,
        field_evidence,
    ) = _classified_field_groups(payload["fields"])

    confirmed_facts = dict(baseline.confirmed_facts)
    confirmed_facts.update(
        {
            "opportunity_status": payload["opportunity_status"],
            "listing_status": payload["listing_status"],
            "source_domain": payload["source"]["source_domain"],
        }
    )
    confirmed_facts.update(confirmed_fields)
    if conflicts:
        confirmed_facts["conflicting_evidence"] = conflicts

    seller_claims = dict(baseline.seller_claims)
    seller_claims.update(seller_claim_fields)

    missing_evidence = _dedupe_strings(
        (*baseline.missing_evidence, *payload["missing_evidence"])
    )
    seller_questions = _dedupe_strings(
        (*baseline.seller_questions, *payload["seller_questions"])
    )

    provenance = {
        "source": dict(payload["source"]),
        "records": [dict(record) for record in payload["provenance"]["records"]],
        "field_evidence": field_evidence,
        "baseline": dict(baseline.provenance),
    }

    return OpportunityDossier(
        opportunity_id=payload["opportunity_id"],
        domain=EXPECTED_DOMAIN,
        primary_scenario=payload["primary_scenario"],
        qualification_status=EXPECTED_QUALIFICATION_STATUS,
        confirmed_facts=confirmed_facts,
        seller_claims=seller_claims,
        supported_inferences=tuple(
            dict(inference) for inference in payload["supported_inferences"]
        ),
        unknown_fields=unknown_fields,
        missing_evidence=missing_evidence,
        seller_questions=seller_questions,
        provenance=provenance,
    )


def build_confirmed_dossier_report(payload: object) -> dict[str, Any]:
    """Build a retained evidence-required report from one valid intake payload."""
    validated = validate_confirmed_dossier_intake(payload)
    _, result = _build_candidate_and_result(validated)

    baseline = build_opportunity_dossier(result)
    dossier = _enrich_dossier(payload=validated, baseline=baseline)
    eligibility = evaluate_analysis_eligibility(result, dossier)

    canonical = to_canonical_opportunity(result)
    if canonical is not None:
        canonical = dict(canonical)
        canonical["opportunity_id"] = validated["opportunity_id"]

    outcome = CheckpointOutcome(
        outcome_type=FINAL_OUTCOME,
        discovery_result=result,
        dossier=dossier,
        eligibility=eligibility,
        canonical_opportunity=canonical,
        analysis_invoked=False,
        automatic_purchase_decision=False,
    )
    report = outcome.to_dict()
    report.update(
        {
            "schema_version": SCHEMA_VERSION,
            "execution_mode": EXECUTION_MODE,
            "domain": EXPECTED_DOMAIN,
            "opportunity_status": EXPECTED_OPPORTUNITY_STATUS,
            "dossier_status": DOSSIER_STATUS,
            "final_outcome": FINAL_OUTCOME,
            "final_decision": FINAL_DECISION,
            "retained_in_opportunity_report": True,
            "analysis_invoked": False,
            "market_analysis_invoked": False,
            "acquisition_cost_analysis_invoked": False,
            "scoring_invoked": False,
            "decision_intelligence_invoked": False,
            "automatic_purchase_decision": False,
            "automatic_bid": False,
            "automatic_contact": False,
            "automatic_reservation": False,
            "automatic_payment": False,
        }
    )
    return report
