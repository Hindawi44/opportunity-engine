"""Persistent lifecycle tracker for pre-market clothing bankruptcy cases.

The tracker consumes already-produced sale-channel search reports. It does not
perform network requests, open listing pages, contact anyone, or make commercial
decisions. Its job is to remember each estate, derive a conservative lifecycle
state, detect material changes, and create a human operator action queue.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REGISTRY_SCHEMA_VERSION = "pre-market-case-registry-1.0"
TRACKER_SCHEMA_VERSION = "pre-market-case-tracker-run-1.0"

PRE_MARKET_LEAD = "PRE_MARKET_LEAD"
ESTATE_MANAGER_IDENTIFIED = "ESTATE_MANAGER_IDENTIFIED"
NO_PUBLIC_SALE_CHANNEL_FOUND = "NO_PUBLIC_SALE_CHANNEL_FOUND"
LIQUIDATION_CHANNEL_CANDIDATE = (
    "LIQUIDATION_CHANNEL_CANDIDATE_REQUIRES_PAGE_VERIFICATION"
)
SALE_LISTING_CANDIDATE = "SALE_LISTING_CANDIDATE_REQUIRES_PAGE_VERIFICATION"
VERIFIED_ACTIVE_INVENTORY_SALE = "VERIFIED_ACTIVE_INVENTORY_SALE"

ALLOWED_STATES = frozenset(
    {
        PRE_MARKET_LEAD,
        ESTATE_MANAGER_IDENTIFIED,
        NO_PUBLIC_SALE_CHANNEL_FOUND,
        LIQUIDATION_CHANNEL_CANDIDATE,
        SALE_LISTING_CANDIDATE,
        VERIFIED_ACTIVE_INVENTORY_SALE,
    }
)

_STATE_RANK = {
    PRE_MARKET_LEAD: 0,
    ESTATE_MANAGER_IDENTIFIED: 1,
    NO_PUBLIC_SALE_CHANNEL_FOUND: 2,
    LIQUIDATION_CHANNEL_CANDIDATE: 3,
    SALE_LISTING_CANDIDATE: 4,
    VERIFIED_ACTIVE_INVENTORY_SALE: 5,
}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _valid_orgnr(value: object) -> str:
    text = "".join(character for character in str(value or "") if character.isdigit())
    if len(text) != 9:
        raise ValueError("organisation number must contain exactly nine digits")
    return text


def _string_tuple(values: object) -> tuple[str, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return ()
    cleaned = {_compact(value) for value in values if _compact(value)}
    return tuple(sorted(cleaned))


def _candidate_urls(
    candidates: object,
    *,
    expected_state: str,
) -> tuple[str, ...]:
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        return ()
    urls: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        if _compact(candidate.get("candidate_state")) != expected_state:
            continue
        url = _compact(candidate.get("url"))
        if url.startswith("https://"):
            urls.add(url)
    return tuple(sorted(urls))


@dataclass(frozen=True, slots=True)
class CaseObservation:
    captured_at: str
    estate_orgnr: str
    estate_name: str
    debtor_orgnr: str
    debtor_name: str
    opened_date: str | None
    municipality: str | None
    estate_manager_name: str | None
    estate_manager_identified: bool
    scan_complete: bool
    sale_listing_candidate_urls: tuple[str, ...]
    liquidation_channel_candidate_urls: tuple[str, ...]
    public_sale_found: bool
    inventory_sale_verified: bool
    liquidation_channel_verified: bool
    source_report: str | None = None

    @property
    def case_id(self) -> str:
        return f"estate:{self.estate_orgnr}"

    @property
    def state(self) -> str:
        if self.public_sale_found and self.inventory_sale_verified:
            return VERIFIED_ACTIVE_INVENTORY_SALE
        if self.sale_listing_candidate_urls:
            return SALE_LISTING_CANDIDATE
        if self.liquidation_channel_candidate_urls:
            return LIQUIDATION_CHANNEL_CANDIDATE
        if self.scan_complete and self.estate_manager_identified:
            return NO_PUBLIC_SALE_CHANNEL_FOUND
        if self.estate_manager_identified:
            return ESTATE_MANAGER_IDENTIFIED
        return PRE_MARKET_LEAD


@dataclass(frozen=True, slots=True)
class CaseSnapshot:
    case_id: str
    estate_orgnr: str
    estate_name: str
    debtor_orgnr: str
    debtor_name: str
    opened_date: str | None
    municipality: str | None
    estate_manager_name: str | None
    estate_manager_identified: bool
    state: str
    first_seen_at: str
    last_checked_at: str
    last_changed_at: str
    scan_complete: bool
    sale_listing_candidate_urls: tuple[str, ...]
    liquidation_channel_candidate_urls: tuple[str, ...]
    public_sale_found: bool
    inventory_sale_verified: bool
    liquidation_channel_verified: bool
    source_reports: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        verified = self.state == VERIFIED_ACTIVE_INVENTORY_SALE
        return {
            "case_id": self.case_id,
            "estate_orgnr": self.estate_orgnr,
            "estate_name": self.estate_name,
            "debtor_orgnr": self.debtor_orgnr,
            "debtor_name": self.debtor_name,
            "opened_date": self.opened_date,
            "municipality": self.municipality,
            "estate_manager_name": self.estate_manager_name,
            "estate_manager_identified": self.estate_manager_identified,
            "state": self.state,
            "first_seen_at": self.first_seen_at,
            "last_checked_at": self.last_checked_at,
            "last_changed_at": self.last_changed_at,
            "scan_complete": self.scan_complete,
            "sale_listing_candidate_urls": list(self.sale_listing_candidate_urls),
            "liquidation_channel_candidate_urls": list(
                self.liquidation_channel_candidate_urls
            ),
            "public_sale_found": self.public_sale_found,
            "inventory_sale_verified": self.inventory_sale_verified,
            "liquidation_channel_verified": self.liquidation_channel_verified,
            "source_reports": list(self.source_reports),
            "top5_eligible": verified,
            "analysis_eligible": verified,
            "operator_review_required": True,
            "automatic_page_open": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CaseSnapshot":
        state = _compact(value.get("state"))
        if state not in ALLOWED_STATES:
            raise ValueError(f"unsupported case state: {state}")
        estate_orgnr = _valid_orgnr(value.get("estate_orgnr"))
        case_id = _compact(value.get("case_id"))
        if case_id != f"estate:{estate_orgnr}":
            raise ValueError("case_id does not match estate organisation number")
        return cls(
            case_id=case_id,
            estate_orgnr=estate_orgnr,
            estate_name=_compact(value.get("estate_name")),
            debtor_orgnr=_valid_orgnr(value.get("debtor_orgnr")),
            debtor_name=_compact(value.get("debtor_name")),
            opened_date=_compact(value.get("opened_date")) or None,
            municipality=_compact(value.get("municipality")) or None,
            estate_manager_name=_compact(value.get("estate_manager_name")) or None,
            estate_manager_identified=bool(value.get("estate_manager_identified")),
            state=state,
            first_seen_at=_compact(value.get("first_seen_at")),
            last_checked_at=_compact(value.get("last_checked_at")),
            last_changed_at=_compact(value.get("last_changed_at")),
            scan_complete=bool(value.get("scan_complete")),
            sale_listing_candidate_urls=_string_tuple(
                value.get("sale_listing_candidate_urls")
            ),
            liquidation_channel_candidate_urls=_string_tuple(
                value.get("liquidation_channel_candidate_urls")
            ),
            public_sale_found=bool(value.get("public_sale_found")),
            inventory_sale_verified=bool(value.get("inventory_sale_verified")),
            liquidation_channel_verified=bool(
                value.get("liquidation_channel_verified")
            ),
            source_reports=_string_tuple(value.get("source_reports")),
        )


@dataclass(frozen=True, slots=True)
class CaseChange:
    case_id: str
    debtor_name: str
    change_type: str
    detected_at: str
    previous_state: str | None
    current_state: str
    new_urls: tuple[str, ...] = ()

    @property
    def alert_worthy(self) -> bool:
        return self.change_type in {
            "STATE_CHANGED",
            "NEW_SALE_LISTING_CANDIDATE",
            "NEW_LIQUIDATION_CHANNEL_CANDIDATE",
            "VERIFIED_ACTIVE_INVENTORY_SALE",
        } and self.current_state in {
            LIQUIDATION_CHANNEL_CANDIDATE,
            SALE_LISTING_CANDIDATE,
            VERIFIED_ACTIVE_INVENTORY_SALE,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "debtor_name": self.debtor_name,
            "change_type": self.change_type,
            "detected_at": self.detected_at,
            "previous_state": self.previous_state,
            "current_state": self.current_state,
            "new_urls": list(self.new_urls),
            "alert_worthy": self.alert_worthy,
        }


@dataclass(frozen=True, slots=True)
class OperatorAction:
    case_id: str
    debtor_name: str
    state: str
    action: str
    reason: str
    priority: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "debtor_name": self.debtor_name,
            "state": self.state,
            "recommended_action": self.action,
            "reason": self.reason,
            "priority": self.priority,
            "human_approval_required": True,
            "automatic_email": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


@dataclass(frozen=True, slots=True)
class CaseTrackerResult:
    captured_at: str
    previous_case_count: int
    observed_case_count: int
    cases: tuple[CaseSnapshot, ...]
    changes: tuple[CaseChange, ...]
    operator_actions: tuple[OperatorAction, ...]

    @property
    def alerts(self) -> tuple[CaseChange, ...]:
        return tuple(change for change in self.changes if change.alert_worthy)

    @property
    def verified_cases(self) -> tuple[CaseSnapshot, ...]:
        return tuple(
            case for case in self.cases if case.state == VERIFIED_ACTIVE_INVENTORY_SALE
        )

    def registry_dict(self) -> dict[str, Any]:
        return {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "updated_at": self.captured_at,
            "case_count": len(self.cases),
            "cases": [case.to_dict() for case in self.cases],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TRACKER_SCHEMA_VERSION,
            "captured_at": self.captured_at,
            "previous_case_count": self.previous_case_count,
            "observed_case_count": self.observed_case_count,
            "case_count": len(self.cases),
            "change_count": len(self.changes),
            "alert_count": len(self.alerts),
            "operator_action_count": len(self.operator_actions),
            "verified_active_inventory_sale_count": len(self.verified_cases),
            "changes": [change.to_dict() for change in self.changes],
            "alerts": [change.to_dict() for change in self.alerts],
            "operator_actions": [action.to_dict() for action in self.operator_actions],
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


def observation_from_sale_channel_report(
    report: Mapping[str, Any],
    *,
    source_report: str | None = None,
) -> CaseObservation:
    estate = report.get("estate")
    if not isinstance(estate, Mapping):
        raise ValueError("sale-channel report lacks an estate object")

    estate_orgnr = _valid_orgnr(estate.get("estate_orgnr"))
    debtor_orgnr = _valid_orgnr(estate.get("debtor_orgnr"))
    candidates = report.get("candidates")

    return CaseObservation(
        captured_at=_compact(report.get("captured_at")) or _now(),
        estate_orgnr=estate_orgnr,
        estate_name=_compact(estate.get("estate_name")),
        debtor_orgnr=debtor_orgnr,
        debtor_name=_compact(estate.get("debtor_name")),
        opened_date=_compact(estate.get("opened_date")) or None,
        municipality=_compact(estate.get("municipality")) or None,
        estate_manager_name=_compact(estate.get("estate_manager_name")) or None,
        estate_manager_identified=bool(estate.get("estate_manager_identified")),
        scan_complete=bool(report.get("scan_complete")),
        sale_listing_candidate_urls=_candidate_urls(
            candidates,
            expected_state=SALE_LISTING_CANDIDATE,
        ),
        liquidation_channel_candidate_urls=_candidate_urls(
            candidates,
            expected_state=LIQUIDATION_CHANNEL_CANDIDATE,
        ),
        public_sale_found=bool(report.get("public_sale_found")),
        inventory_sale_verified=bool(report.get("inventory_sale_verified")),
        liquidation_channel_verified=bool(
            report.get("liquidation_channel_verified")
        ),
        source_report=_compact(source_report) or None,
    )


def load_case_registry(path: str | Path | None) -> dict[str, CaseSnapshot]:
    if path is None:
        return {}
    source = Path(path)
    if not source.exists():
        return {}
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("case registry must be a JSON object")
    if payload.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise ValueError("unsupported case registry schema")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, Sequence) or isinstance(raw_cases, (str, bytes)):
        raise ValueError("case registry lacks a cases array")
    cases: dict[str, CaseSnapshot] = {}
    for raw_case in raw_cases:
        if not isinstance(raw_case, Mapping):
            raise ValueError("case registry contains a non-object case")
        case = CaseSnapshot.from_dict(raw_case)
        if case.case_id in cases:
            raise ValueError(f"duplicate case id in registry: {case.case_id}")
        cases[case.case_id] = case
    return cases


def _snapshot_from_observation(
    observation: CaseObservation,
    *,
    previous: CaseSnapshot | None,
    detected_at: str,
) -> CaseSnapshot:
    state = observation.state
    previous_reports = previous.source_reports if previous else ()
    reports = set(previous_reports)
    if observation.source_report:
        reports.add(observation.source_report)

    changed = previous is None or any(
        (
            previous.state != state,
            previous.sale_listing_candidate_urls
            != observation.sale_listing_candidate_urls,
            previous.liquidation_channel_candidate_urls
            != observation.liquidation_channel_candidate_urls,
            previous.public_sale_found != observation.public_sale_found,
            previous.inventory_sale_verified != observation.inventory_sale_verified,
            previous.liquidation_channel_verified
            != observation.liquidation_channel_verified,
        )
    )

    return CaseSnapshot(
        case_id=observation.case_id,
        estate_orgnr=observation.estate_orgnr,
        estate_name=observation.estate_name,
        debtor_orgnr=observation.debtor_orgnr,
        debtor_name=observation.debtor_name,
        opened_date=observation.opened_date,
        municipality=observation.municipality,
        estate_manager_name=observation.estate_manager_name,
        estate_manager_identified=observation.estate_manager_identified,
        state=state,
        first_seen_at=previous.first_seen_at if previous else detected_at,
        last_checked_at=observation.captured_at,
        last_changed_at=(
            detected_at if changed else previous.last_changed_at if previous else detected_at
        ),
        scan_complete=observation.scan_complete,
        sale_listing_candidate_urls=observation.sale_listing_candidate_urls,
        liquidation_channel_candidate_urls=(
            observation.liquidation_channel_candidate_urls
        ),
        public_sale_found=observation.public_sale_found,
        inventory_sale_verified=observation.inventory_sale_verified,
        liquidation_channel_verified=observation.liquidation_channel_verified,
        source_reports=tuple(sorted(reports)),
    )


def _detect_changes(
    previous: CaseSnapshot | None,
    current: CaseSnapshot,
    *,
    detected_at: str,
) -> tuple[CaseChange, ...]:
    if previous is None:
        return (
            CaseChange(
                case_id=current.case_id,
                debtor_name=current.debtor_name,
                change_type="CASE_CREATED",
                detected_at=detected_at,
                previous_state=None,
                current_state=current.state,
            ),
        )

    changes: list[CaseChange] = []
    if previous.state != current.state:
        changes.append(
            CaseChange(
                case_id=current.case_id,
                debtor_name=current.debtor_name,
                change_type=(
                    "VERIFIED_ACTIVE_INVENTORY_SALE"
                    if current.state == VERIFIED_ACTIVE_INVENTORY_SALE
                    else "STATE_CHANGED"
                ),
                detected_at=detected_at,
                previous_state=previous.state,
                current_state=current.state,
            )
        )

    new_sale_urls = tuple(
        sorted(
            set(current.sale_listing_candidate_urls)
            - set(previous.sale_listing_candidate_urls)
        )
    )
    if new_sale_urls:
        changes.append(
            CaseChange(
                case_id=current.case_id,
                debtor_name=current.debtor_name,
                change_type="NEW_SALE_LISTING_CANDIDATE",
                detected_at=detected_at,
                previous_state=previous.state,
                current_state=current.state,
                new_urls=new_sale_urls,
            )
        )

    new_liquidation_urls = tuple(
        sorted(
            set(current.liquidation_channel_candidate_urls)
            - set(previous.liquidation_channel_candidate_urls)
        )
    )
    if new_liquidation_urls:
        changes.append(
            CaseChange(
                case_id=current.case_id,
                debtor_name=current.debtor_name,
                change_type="NEW_LIQUIDATION_CHANNEL_CANDIDATE",
                detected_at=detected_at,
                previous_state=previous.state,
                current_state=current.state,
                new_urls=new_liquidation_urls,
            )
        )
    return tuple(changes)


def _operator_action(case: CaseSnapshot) -> OperatorAction:
    if case.state == VERIFIED_ACTIVE_INVENTORY_SALE:
        return OperatorAction(
            case_id=case.case_id,
            debtor_name=case.debtor_name,
            state=case.state,
            action="REVIEW_FOR_COMMERCIAL_ANALYSIS",
            reason="Current inventory sale has been verified.",
            priority="URGENT",
        )
    if case.state == SALE_LISTING_CANDIDATE:
        return OperatorAction(
            case_id=case.case_id,
            debtor_name=case.debtor_name,
            state=case.state,
            action="VERIFY_PUBLIC_SALE_PAGE",
            reason="A new sale-listing candidate requires current page evidence.",
            priority="HIGH",
        )
    if case.state == LIQUIDATION_CHANNEL_CANDIDATE:
        return OperatorAction(
            case_id=case.case_id,
            debtor_name=case.debtor_name,
            state=case.state,
            action="VERIFY_LIQUIDATION_CHANNEL_MANDATE",
            reason="A possible liquidator or sale agent requires mandate verification.",
            priority="HIGH",
        )
    if case.state == NO_PUBLIC_SALE_CHANNEL_FOUND:
        return OperatorAction(
            case_id=case.case_id,
            debtor_name=case.debtor_name,
            state=case.state,
            action="ASK_ESTATE_MANAGER_FOR_SALE_CHANNEL",
            reason="No public sale or liquidation channel passed the strict search gate.",
            priority="MEDIUM",
        )
    if case.state == ESTATE_MANAGER_IDENTIFIED:
        return OperatorAction(
            case_id=case.case_id,
            debtor_name=case.debtor_name,
            state=case.state,
            action="RUN_TARGETED_SALE_CHANNEL_SEARCH",
            reason="Estate manager is known but sale-channel search is incomplete.",
            priority="MEDIUM",
        )
    return OperatorAction(
        case_id=case.case_id,
        debtor_name=case.debtor_name,
        state=case.state,
        action="IDENTIFY_ESTATE_MANAGER",
        reason="The case has not yet been enriched with an estate manager.",
        priority="LOW",
    )


def update_case_registry(
    previous_cases: Mapping[str, CaseSnapshot],
    observations: Iterable[CaseObservation],
    *,
    captured_at: str | None = None,
) -> CaseTrackerResult:
    detected_at = captured_at or _now()
    current_cases = dict(previous_cases)
    changes: list[CaseChange] = []
    observed_ids: set[str] = set()

    for observation in observations:
        if observation.case_id in observed_ids:
            raise ValueError(f"duplicate observation for {observation.case_id}")
        observed_ids.add(observation.case_id)
        previous = current_cases.get(observation.case_id)
        current = _snapshot_from_observation(
            observation,
            previous=previous,
            detected_at=detected_at,
        )
        current_cases[current.case_id] = current
        changes.extend(_detect_changes(previous, current, detected_at=detected_at))

    ordered_cases = tuple(
        sorted(
            current_cases.values(),
            key=lambda case: (
                -_STATE_RANK[case.state],
                case.opened_date or "",
                case.case_id,
            ),
        )
    )
    actions = tuple(_operator_action(case) for case in ordered_cases)
    return CaseTrackerResult(
        captured_at=detected_at,
        previous_case_count=len(previous_cases),
        observed_case_count=len(observed_ids),
        cases=ordered_cases,
        changes=tuple(changes),
        operator_actions=actions,
    )


def write_case_tracker_artifacts(
    result: CaseTrackerResult,
    output_dir: str | Path,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    registry_path = target / "pre-market-cases.json"
    changes_path = target / "pre-market-case-changes.json"
    alerts_path = target / "sale-channel-alerts.json"
    actions_path = target / "operator-action-queue.json"
    commercial_path = target / "live-clothing-top5.json"
    summary_path = target / "operator-summary.txt"

    registry_path.write_text(
        json.dumps(result.registry_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    changes_path.write_text(
        json.dumps(
            [change.to_dict() for change in result.changes],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    alerts_path.write_text(
        json.dumps(
            [alert.to_dict() for alert in result.alerts],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    actions_path.write_text(
        json.dumps(
            [action.to_dict() for action in result.operator_actions],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    commercial_path.write_text(
        json.dumps(
            [case.to_dict() for case in result.verified_cases[:5]],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    lines = [
        "Pre-market case lifecycle tracker",
        f"Previous cases: {result.previous_case_count}",
        f"Cases observed this run: {result.observed_case_count}",
        f"Cases retained: {len(result.cases)}",
        f"Material changes: {len(result.changes)}",
        f"Alert-worthy changes: {len(result.alerts)}",
        f"Operator actions: {len(result.operator_actions)}",
        f"Verified active inventory sales: {len(result.verified_cases)}",
        "Automatic contact/bid/purchase/payment: false",
        "",
    ]
    for action in result.operator_actions[:10]:
        lines.append(
            f"- {action.priority} | {action.debtor_name} | {action.state} | "
            f"{action.action}"
        )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "registry": registry_path,
        "changes": changes_path,
        "alerts": alerts_path,
        "operator_actions": actions_path,
        "commercial_top5": commercial_path,
        "summary": summary_path,
    }
