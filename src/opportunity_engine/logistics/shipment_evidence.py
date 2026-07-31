"""Generate deterministic shipment-evidence tasks from transport-input gaps.

The workflow turns missing structured logistics inputs into human-review tasks.
It never parses listing prose, contacts a seller, calculates a route, or changes
an opportunity decision.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any


SCHEMA_VERSION = "shipment-evidence-queue-v1"
_ALLOWED_PRIORITIES = frozenset({"CRITICAL", "HIGH", "MEDIUM"})
_ALLOWED_STATUSES = frozenset({"OPEN", "RESOLVED", "NOT_AVAILABLE", "NOT_REQUIRED"})
_ALLOWED_SOURCES = frozenset(
    {"LISTING_OR_SELLER", "BUYER_OR_CARRIER", "OPERATOR", "MANUAL_REVIEW"}
)
_ALLOWED_WORKFLOW_STATUSES = frozenset(
    {
        "NO_ELIGIBLE_OPPORTUNITY",
        "EVIDENCE_REQUIRED_FOR_QUOTE",
        "EVIDENCE_REVIEW_OPTIONAL",
        "READY_FOR_MANUAL_QUOTE",
        "TRANSPORT_COMPONENT_READY",
    }
)
_SAFE_ID = re.compile(r"[^a-z0-9]+")


class ShipmentEvidenceError(ValueError):
    """Raised when shipment-evidence input or output violates the contract."""


def _non_empty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ShipmentEvidenceError(f"{field_name} must be a non-empty string")
    return value.strip()


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ShipmentEvidenceError(f"{field_name} must be a list or tuple")
    result = tuple(_non_empty(item, f"{field_name}[]") for item in value)
    if len(set(result)) != len(result):
        raise ShipmentEvidenceError(f"{field_name} must not contain duplicates")
    return result


def _safe_suffix(value: str) -> str:
    normalized = _SAFE_ID.sub("-", value.casefold()).strip("-")
    return normalized or "task"


@dataclass(frozen=True, slots=True)
class ShipmentEvidenceTaskV1:
    """One auditable human-review task for missing shipment evidence."""

    task_id: str
    opportunity_id: str
    task_type: str
    requested_fields: tuple[str, ...]
    source_channel: str
    priority: str
    status: str
    blocks_manual_quote: bool
    blocks_qualification: bool
    question_nb: str
    question_ar: str
    reason: str
    current_value: Any
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _non_empty(self.task_id, "task_id")
        _non_empty(self.opportunity_id, "opportunity_id")
        _non_empty(self.task_type, "task_type")
        if not self.requested_fields:
            raise ShipmentEvidenceError("requested_fields must not be empty")
        _string_tuple(self.requested_fields, "requested_fields")
        if self.source_channel not in _ALLOWED_SOURCES:
            raise ShipmentEvidenceError(
                f"unsupported source_channel: {self.source_channel}"
            )
        if self.priority not in _ALLOWED_PRIORITIES:
            raise ShipmentEvidenceError(f"unsupported priority: {self.priority}")
        if self.status not in _ALLOWED_STATUSES:
            raise ShipmentEvidenceError(f"unsupported status: {self.status}")
        if not isinstance(self.blocks_manual_quote, bool):
            raise ShipmentEvidenceError("blocks_manual_quote must be boolean")
        if not isinstance(self.blocks_qualification, bool):
            raise ShipmentEvidenceError("blocks_qualification must be boolean")
        _non_empty(self.question_nb, "question_nb")
        _non_empty(self.question_ar, "question_ar")
        _non_empty(self.reason, "reason")
        _string_tuple(self.evidence_refs, "evidence_refs")
        if self.status == "OPEN" and self.current_value is not None:
            raise ShipmentEvidenceError("OPEN tasks must not contain current_value")

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "opportunity_id": self.opportunity_id,
            "task_type": self.task_type,
            "requested_fields": list(self.requested_fields),
            "source_channel": self.source_channel,
            "priority": self.priority,
            "status": self.status,
            "blocks_manual_quote": self.blocks_manual_quote,
            "blocks_qualification": self.blocks_qualification,
            "question_nb": self.question_nb,
            "question_ar": self.question_ar,
            "reason": self.reason,
            "current_value": deepcopy(self.current_value),
            "evidence_refs": list(self.evidence_refs),
        }


_TASK_SPECS: dict[str, dict[str, Any]] = {
    "origin.city_or_postal_code_or_coordinates": {
        "task_type": "ORIGIN_LOCATION",
        "requested_fields": (
            "origin.city",
            "origin.postal_code",
            "origin.coordinates",
        ),
        "source_channel": "LISTING_OR_SELLER",
        "priority": "CRITICAL",
        "question_nb": "Hva er nøyaktig henteadresse eller postnummer for varene?",
        "question_ar": "ما عنوان الاستلام الدقيق أو الرمز البريدي للبضاعة؟",
        "reason": "A route cannot be prepared without a structured pickup location.",
        "blocks": True,
    },
    "shipment.cargo_type": {
        "task_type": "CARGO_TYPE",
        "requested_fields": ("shipment.cargo_type",),
        "source_channel": "LISTING_OR_SELLER",
        "priority": "HIGH",
        "question_nb": "Hvordan er varene pakket – løst, i esker eller på pall?",
        "question_ar": "كيف تم تجهيز البضاعة: مفردة، داخل صناديق، أم على طبالي؟",
        "reason": "The carrier needs the packing form to choose suitable equipment.",
        "blocks": True,
    },
    "shipment.one_of_weight_volume_pallet_package_item_or_length": {
        "task_type": "SHIPMENT_MEASUREMENTS",
        "requested_fields": (
            "shipment.weight_kg",
            "shipment.volume_m3",
            "shipment.pallet_count",
            "shipment.package_count",
            "shipment.item_count",
            "shipment.longest_length_m",
        ),
        "source_channel": "LISTING_OR_SELLER",
        "priority": "CRITICAL",
        "question_nb": (
            "Kan dere oppgi totalvekt, pakkede mål eller volum, og antall paller, "
            "kolli eller deler?"
        ),
        "question_ar": (
            "هل يمكن تزويدنا بالوزن الإجمالي، والأبعاد بعد التغليف أو الحجم، "
            "وعدد الطبالي أو الطرود أو القطع؟"
        ),
        "reason": "At least one structured size or mass basis is required for a quote.",
        "blocks": True,
    },
    "transport_mode": {
        "task_type": "TRANSPORT_MODE",
        "requested_fields": ("transport_mode",),
        "source_channel": "OPERATOR",
        "priority": "HIGH",
        "question_nb": (
            "Skal varene hentes selv, med budbil eller av transportør/fraktfirma?"
        ),
        "question_ar": (
            "هل سيكون الاستلام ذاتيًا، بسيارة توصيل، أم بواسطة شركة نقل وشحن؟"
        ),
        "reason": "A transport method must be selected before requesting a comparable quote.",
        "blocks": True,
    },
    "handling.loading_required": {
        "task_type": "LOADING_REQUIREMENT",
        "requested_fields": ("handling.loading_required",),
        "source_channel": "LISTING_OR_SELLER",
        "priority": "HIGH",
        "question_nb": "Laster selger varene, eller må transportøren stå for lasting?",
        "question_ar": "هل سيقوم البائع بتحميل البضاعة أم يجب على شركة النقل تحميلها؟",
        "reason": "Loading responsibility can materially change the quote.",
        "blocks": True,
    },
    "handling.unloading_required": {
        "task_type": "UNLOADING_REQUIREMENT",
        "requested_fields": ("handling.unloading_required",),
        "source_channel": "BUYER_OR_CARRIER",
        "priority": "HIGH",
        "question_nb": "Kreves det hjelp eller utstyr ved lossing i Namsos?",
        "question_ar": "هل نحتاج إلى مساعدة أو معدات عند تفريغ البضاعة في نامسوس؟",
        "reason": "Unloading responsibility must be known for an operational quote.",
        "blocks": True,
    },
    "handling.forklift_required": {
        "task_type": "FORKLIFT_REQUIREMENT",
        "requested_fields": ("handling.forklift_required",),
        "source_channel": "LISTING_OR_SELLER",
        "priority": "HIGH",
        "question_nb": (
            "Er truck tilgjengelig ved henting, eller må transportøren ha med løfteutstyr?"
        ),
        "question_ar": (
            "هل توجد رافعة شوكية عند الاستلام أم يجب على شركة النقل إحضار معدات الرفع؟"
        ),
        "reason": "Forklift availability affects vehicle and handling requirements.",
        "blocks": True,
    },
    "handling.tail_lift_required": {
        "task_type": "TAIL_LIFT_REQUIREMENT",
        "requested_fields": ("handling.tail_lift_required",),
        "source_channel": "BUYER_OR_CARRIER",
        "priority": "HIGH",
        "question_nb": "Er bakløfter nødvendig ved henting eller levering?",
        "question_ar": "هل يلزم مصعد خلفي للشاحنة عند الاستلام أو التسليم؟",
        "reason": "Tail-lift requirements affect carrier and vehicle selection.",
        "blocks": True,
    },
    "handling.dismantling_required": {
        "task_type": "DISMANTLING_REQUIREMENT",
        "requested_fields": ("handling.dismantling_required",),
        "source_channel": "LISTING_OR_SELLER",
        "priority": "HIGH",
        "question_nb": (
            "Er varene demontert og klare for transport, eller må de demonteres først?"
        ),
        "question_ar": (
            "هل البضاعة مفككة وجاهزة للنقل أم يجب تفكيكها أولًا؟"
        ),
        "reason": "Dismantling changes handling time, dimensions, and total cost.",
        "blocks": True,
    },
}


def _generic_spec(missing_input: str) -> dict[str, Any]:
    return {
        "task_type": "UNMAPPED_TRANSPORT_INPUT",
        "requested_fields": (missing_input,),
        "source_channel": "MANUAL_REVIEW",
        "priority": "HIGH",
        "question_nb": f"Kontroller og dokumenter det manglende transportfeltet: {missing_input}.",
        "question_ar": f"تحقق ووثّق حقل النقل الناقص: {missing_input}.",
        "reason": "An unmapped transport input must be reviewed rather than ignored.",
        "blocks": True,
    }


def _task_from_missing_input(
    opportunity_id: str,
    missing_input: str,
    *,
    transport_component_ready: bool,
) -> ShipmentEvidenceTaskV1:
    spec = _TASK_SPECS.get(missing_input, _generic_spec(missing_input))
    task_suffix = f"{spec['task_type']}-{missing_input}"
    default_blocking = bool(spec["blocks"])
    blocking = default_blocking and not transport_component_ready
    return ShipmentEvidenceTaskV1(
        task_id=f"shipment-evidence-{opportunity_id}-{_safe_suffix(task_suffix)}",
        opportunity_id=opportunity_id,
        task_type=spec["task_type"],
        requested_fields=tuple(spec["requested_fields"]),
        source_channel=spec["source_channel"],
        priority=spec["priority"],
        status="OPEN",
        blocks_manual_quote=blocking,
        blocks_qualification=blocking,
        question_nb=spec["question_nb"],
        question_ar=spec["question_ar"],
        reason=spec["reason"],
        current_value=None,
        evidence_refs=(),
    )


def _scope() -> dict[str, bool]:
    return {
        "listing_prose_extraction_enabled": False,
        "automatic_seller_contact_allowed": False,
        "automatic_carrier_contact_allowed": False,
        "automatic_quote_request_allowed": False,
        "persistent_task_state_enabled": False,
        "changes_final_decision": False,
        "changes_ranking": False,
        "changes_top5": False,
        "changes_alerts": False,
        "automatic_purchase_allowed": False,
    }


def build_shipment_evidence_queue(
    operational_transport_payload: dict[str, Any],
) -> dict[str, Any]:
    """Build a deterministic zero-safe evidence queue from transport gaps."""
    if not isinstance(operational_transport_payload, dict):
        raise ShipmentEvidenceError("operational transport payload must be an object")

    base = {
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": operational_transport_payload.get("schema_version"),
        "scope": _scope(),
    }
    selection_status = operational_transport_payload.get("selection_status")
    if selection_status == "NO_ELIGIBLE_OPPORTUNITY":
        return {
            **base,
            "selection_status": "NO_ELIGIBLE_OPPORTUNITY",
            "workflow_status": "NO_ELIGIBLE_OPPORTUNITY",
            "next_action": "NONE",
            "source_opportunity": None,
            "manual_quote_readiness": {"ready": False, "transport_status": None},
            "task_count": 0,
            "blocking_task_count": 0,
            "tasks": [],
        }
    if selection_status != "SELECTED":
        raise ShipmentEvidenceError(
            "selection_status must be SELECTED or NO_ELIGIBLE_OPPORTUNITY"
        )

    source = operational_transport_payload.get("source_opportunity")
    transport_input = operational_transport_payload.get("transport_input")
    snapshot = operational_transport_payload.get("transport_snapshot")
    if not isinstance(source, dict):
        raise ShipmentEvidenceError("selected payload requires source_opportunity")
    if not isinstance(transport_input, dict):
        raise ShipmentEvidenceError("selected payload requires transport_input")
    if not isinstance(snapshot, dict):
        raise ShipmentEvidenceError("selected payload requires transport_snapshot")

    opportunity_id = _non_empty(
        source.get("opportunity_id"), "source_opportunity.opportunity_id"
    )
    if transport_input.get("opportunity_id") != opportunity_id:
        raise ShipmentEvidenceError("transport_input opportunity_id does not match source")
    if snapshot.get("opportunity_id") != opportunity_id:
        raise ShipmentEvidenceError("transport_snapshot opportunity_id does not match source")

    missing_inputs = snapshot.get("missing_inputs")
    if not isinstance(missing_inputs, list):
        raise ShipmentEvidenceError("transport_snapshot.missing_inputs must be a list")
    normalized_missing = [
        _non_empty(item, "transport_snapshot.missing_inputs[]")
        for item in missing_inputs
    ]
    if len(set(normalized_missing)) != len(normalized_missing):
        raise ShipmentEvidenceError("transport_snapshot.missing_inputs contains duplicates")

    readiness = snapshot.get("landed_cost_input_readiness")
    if not isinstance(readiness, dict) or not isinstance(readiness.get("ready"), bool):
        raise ShipmentEvidenceError(
            "transport_snapshot.landed_cost_input_readiness is invalid"
        )
    transport_component_ready = readiness["ready"]
    transport_status = _non_empty(
        snapshot.get("transport_status"), "transport_snapshot.transport_status"
    )

    tasks = tuple(
        _task_from_missing_input(
            opportunity_id,
            missing_input,
            transport_component_ready=transport_component_ready,
        )
        for missing_input in normalized_missing
    )
    blocking_task_count = sum(task.blocks_manual_quote for task in tasks)

    if tasks and transport_component_ready:
        workflow_status = "EVIDENCE_REVIEW_OPTIONAL"
        next_action = "REVIEW_OPTIONAL_SHIPMENT_EVIDENCE"
    elif tasks:
        workflow_status = "EVIDENCE_REQUIRED_FOR_QUOTE"
        next_action = "COLLECT_SHIPMENT_EVIDENCE"
    elif transport_component_ready:
        workflow_status = "TRANSPORT_COMPONENT_READY"
        next_action = "CONTINUE_LANDED_COST_REVIEW"
    else:
        workflow_status = "READY_FOR_MANUAL_QUOTE"
        next_action = "REQUEST_MANUAL_TRANSPORT_QUOTE"

    if workflow_status not in _ALLOWED_WORKFLOW_STATUSES:
        raise ShipmentEvidenceError(f"unsupported workflow_status: {workflow_status}")

    return {
        **base,
        "selection_status": "SELECTED",
        "workflow_status": workflow_status,
        "next_action": next_action,
        "source_opportunity": {
            "opportunity_id": opportunity_id,
            "title": source.get("title"),
            "url": source.get("url"),
            "source_city": source.get("source_city"),
            "final_decision": source.get("final_decision"),
            "opportunity_score": source.get("opportunity_score"),
        },
        "manual_quote_readiness": {
            "ready": transport_component_ready,
            "transport_status": transport_status,
        },
        "task_count": len(tasks),
        "blocking_task_count": blocking_task_count,
        "tasks": [task.to_dict() for task in tasks],
    }
