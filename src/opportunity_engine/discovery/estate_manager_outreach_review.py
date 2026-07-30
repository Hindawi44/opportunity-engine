"""Create human-review outreach packets for bankruptcy estate managers.

The module consumes the persistent pre-market case registry and operator action
queue. It performs no network requests, does not discover or guess email
addresses, and never sends messages. It only prepares conservative Norwegian
message drafts for cases where the operator action is
``ASK_ESTATE_MANAGER_FOR_SALE_CHANNEL``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.discovery.pre_market_case_tracker import (
    NO_PUBLIC_SALE_CHANNEL_FOUND,
    REGISTRY_SCHEMA_VERSION,
)

OUTREACH_SCHEMA_VERSION = "estate-manager-outreach-review-1.0"
ELIGIBLE_ACTION = "ASK_ESTATE_MANAGER_FOR_SALE_CHANNEL"
DRAFT_STATUS = "DRAFT_READY_FOR_HUMAN_REVIEW"
CONTACT_STATUS = "REQUIRES_VERIFIED_PUBLIC_PROFESSIONAL_CONTACT"


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _valid_orgnr(value: object) -> str:
    digits = "".join(character for character in str(value or "") if character.isdigit())
    if len(digits) != 9:
        raise ValueError("organisation number must contain exactly nine digits")
    return digits


def _require_mapping(value: object, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _require_sequence(value: object, *, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} must be a JSON array")
    return value


def _priority_rank(value: str) -> int:
    return {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(value, 4)


def _subject(debtor_name: str) -> str:
    return f"Forespørsel om varelager i konkursboet etter {debtor_name}"


def _body(
    *,
    debtor_name: str,
    debtor_orgnr: str,
    estate_orgnr: str,
    sender_name: str,
    sender_business: str,
) -> str:
    return "\n".join(
        (
            "Hei,",
            "",
            (
                f"Jeg viser til konkursboet etter {debtor_name} "
                f"(org.nr. {debtor_orgnr}, boets org.nr. {estate_orgnr})."
            ),
            (
                f"Jeg driver {sender_business} og undersøker muligheten for å kjøpe "
                "et samlet parti med klær, sko eller tilbehør fra boet."
            ),
            "",
            "Kan dere opplyse om:",
            "1. Boet har klær, sko eller tilbehør som fortsatt er tilgjengelig.",
            (
                "2. Salget håndteres av bostyrer, takstmann, avviklingsselskap "
                "eller auksjon."
            ),
            "3. Hvor og når salget eventuelt blir publisert.",
            "4. Det er mulig å gi tilbud på hele eller deler av varelageret.",
            (
                "5. Det finnes en vareliste, bilder, antall, størrelser, lokasjon "
                "og prisforventning."
            ),
            "",
            "Dette er kun en forespørsel om informasjon og ikke et bindende tilbud.",
            "",
            "Vennlig hilsen",
            sender_name,
            sender_business,
        )
    )


@dataclass(frozen=True, slots=True)
class OutreachPacket:
    packet_id: str
    case_id: str
    estate_orgnr: str
    estate_name: str
    debtor_orgnr: str
    debtor_name: str
    opened_date: str | None
    municipality: str | None
    estate_manager_name: str
    case_state: str
    priority: str
    created_at: str
    sender_name: str
    sender_business: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "case_id": self.case_id,
            "estate_orgnr": self.estate_orgnr,
            "estate_name": self.estate_name,
            "debtor_orgnr": self.debtor_orgnr,
            "debtor_name": self.debtor_name,
            "opened_date": self.opened_date,
            "municipality": self.municipality,
            "estate_manager_name": self.estate_manager_name,
            "case_state": self.case_state,
            "priority": self.priority,
            "recommended_action": ELIGIBLE_ACTION,
            "draft_status": DRAFT_STATUS,
            "recipient_status": CONTACT_STATUS,
            "recipient_name": self.estate_manager_name,
            "recipient_email": None,
            "subject_nb": _subject(self.debtor_name),
            "body_nb": _body(
                debtor_name=self.debtor_name,
                debtor_orgnr=self.debtor_orgnr,
                estate_orgnr=self.estate_orgnr,
                sender_name=self.sender_name,
                sender_business=self.sender_business,
            ),
            "required_human_checks": [
                "Verify a current public professional contact channel.",
                "Verify the estate and debtor organisation numbers.",
                "Review and edit the Norwegian draft before any manual send.",
                "Record the reply and any stated sale channel in the case record.",
            ],
            "created_at": self.created_at,
            "human_approval_required": True,
            "automatic_contact_lookup": False,
            "automatic_email": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
            "binding_offer": False,
        }


@dataclass(frozen=True, slots=True)
class OutreachReviewResult:
    captured_at: str
    eligible_action_count: int
    packets: tuple[OutreachPacket, ...]
    skipped: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OUTREACH_SCHEMA_VERSION,
            "captured_at": self.captured_at,
            "eligible_action_count": self.eligible_action_count,
            "packet_count": len(self.packets),
            "skipped_count": len(self.skipped),
            "packets": [packet.to_dict() for packet in self.packets],
            "skipped": list(self.skipped),
            "human_approval_required": True,
            "automatic_contact_lookup": False,
            "automatic_email": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


def build_outreach_review(
    registry_payload: Mapping[str, Any],
    operator_actions: Sequence[object],
    *,
    sender_name: str = "Mahmoud",
    sender_business: str = "Namsos Skredderhus",
    captured_at: str | None = None,
) -> OutreachReviewResult:
    """Build idempotent outreach packets from eligible operator actions."""
    if registry_payload.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise ValueError("unsupported pre-market case registry schema")

    sender_name = _compact(sender_name)
    sender_business = _compact(sender_business)
    if not sender_name or not sender_business:
        raise ValueError("sender name and business are required")

    raw_cases = _require_sequence(registry_payload.get("cases"), label="registry cases")
    cases: dict[str, Mapping[str, Any]] = {}
    for raw_case in raw_cases:
        case = _require_mapping(raw_case, label="registry case")
        case_id = _compact(case.get("case_id"))
        if not case_id:
            raise ValueError("registry case lacks case_id")
        if case_id in cases:
            raise ValueError(f"duplicate registry case: {case_id}")
        cases[case_id] = case

    generated_at = captured_at or _now()
    eligible_count = 0
    packets_by_id: dict[str, OutreachPacket] = {}
    skipped: list[dict[str, str]] = []

    for raw_action in operator_actions:
        action = _require_mapping(raw_action, label="operator action")
        if _compact(action.get("recommended_action")) != ELIGIBLE_ACTION:
            continue
        eligible_count += 1
        case_id = _compact(action.get("case_id"))
        case = cases.get(case_id)
        if case is None:
            skipped.append({"case_id": case_id, "reason": "CASE_NOT_FOUND"})
            continue

        state = _compact(case.get("state"))
        if state != NO_PUBLIC_SALE_CHANNEL_FOUND:
            skipped.append({"case_id": case_id, "reason": "CASE_STATE_NOT_ELIGIBLE"})
            continue

        manager_name = _compact(case.get("estate_manager_name"))
        if not bool(case.get("estate_manager_identified")) or not manager_name:
            skipped.append({"case_id": case_id, "reason": "ESTATE_MANAGER_NOT_IDENTIFIED"})
            continue

        estate_orgnr = _valid_orgnr(case.get("estate_orgnr"))
        debtor_orgnr = _valid_orgnr(case.get("debtor_orgnr"))
        debtor_name = _compact(case.get("debtor_name"))
        estate_name = _compact(case.get("estate_name"))
        if not debtor_name or not estate_name:
            skipped.append({"case_id": case_id, "reason": "COMPANY_IDENTITY_INCOMPLETE"})
            continue

        packet = OutreachPacket(
            packet_id=f"outreach:{estate_orgnr}",
            case_id=case_id,
            estate_orgnr=estate_orgnr,
            estate_name=estate_name,
            debtor_orgnr=debtor_orgnr,
            debtor_name=debtor_name,
            opened_date=_compact(case.get("opened_date")) or None,
            municipality=_compact(case.get("municipality")) or None,
            estate_manager_name=manager_name,
            case_state=state,
            priority=_compact(action.get("priority")) or "MEDIUM",
            created_at=generated_at,
            sender_name=sender_name,
            sender_business=sender_business,
        )
        packets_by_id[packet.packet_id] = packet

    packets = tuple(
        sorted(
            packets_by_id.values(),
            key=lambda packet: (
                _priority_rank(packet.priority),
                packet.opened_date or "",
                packet.packet_id,
            ),
        )
    )
    return OutreachReviewResult(
        captured_at=generated_at,
        eligible_action_count=eligible_count,
        packets=packets,
        skipped=tuple(skipped),
    )


def write_outreach_review_artifacts(
    result: OutreachReviewResult,
    output_dir: str | Path,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    queue_path = target / "estate-manager-outreach-review-queue.json"
    drafts_path = target / "estate-manager-outreach-drafts.md"
    summary_path = target / "operator-summary.txt"

    queue_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Estate-manager outreach drafts",
        "",
        "> Human review is required. No recipient address is discovered or used automatically.",
        "",
    ]
    for packet in result.packets:
        payload = packet.to_dict()
        lines.extend(
            (
                f"## {packet.debtor_name}",
                "",
                f"- Packet: `{packet.packet_id}`",
                f"- Estate manager: {packet.estate_manager_name}",
                f"- Recipient status: `{CONTACT_STATUS}`",
                f"- Subject: {payload['subject_nb']}",
                "",
                "```text",
                str(payload["body_nb"]),
                "```",
                "",
            )
        )
    if not result.packets:
        lines.append("No cases currently require an estate-manager outreach draft.")
    drafts_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary_lines = [
        "Estate-manager outreach review",
        f"Eligible operator actions: {result.eligible_action_count}",
        f"Draft packets created: {len(result.packets)}",
        f"Cases skipped: {len(result.skipped)}",
        "Automatic contact lookup/email/contact: false",
        "Human approval required: true",
    ]
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    return {"queue": queue_path, "drafts": drafts_path, "summary": summary_path}
