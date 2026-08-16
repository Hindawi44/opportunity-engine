"""Build a domain-specific market-intelligence bulletin from existing outputs."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.market_intelligence import (
    MarketSignalRecord,
    MarketSignalStatus,
    MarketSignalType,
)
from opportunity_engine.persistence.database import (
    create_database_engine,
    create_session_factory,
    session_scope,
    upgrade_database,
)
from opportunity_engine.persistence.market_signal_repository import MarketSignalRepository


BRIEF_SCHEMA_VERSION = "domain-market-intelligence-brief-1.0"
DIRECT_WORKFLOWS = {
    "REQUIRES_VERIFICATION",
    "ACTIVE_OPPORTUNITY",
    "QUALIFIED_OPPORTUNITY",
}
EARLY_SIGNAL_TYPES = {
    MarketSignalType.AUCTION_EVENT.value,
    MarketSignalType.BUSINESS_CLOSURE.value,
    MarketSignalType.INSOLVENCY_OR_LIQUIDATION.value,
    MarketSignalType.WAREHOUSE_SURPLUS.value,
    MarketSignalType.REPEATED_SELLER_ACTIVITY.value,
    MarketSignalType.RELATED_INVENTORY_ACTIVITY.value,
}


class DomainMarketIntelligenceError(ValueError):
    """Raised when checkpoint intelligence inputs contradict their contracts."""


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _read_json(path: Path, *, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DomainMarketIntelligenceError(f"Invalid JSON artifact {path}: {exc}") from exc


def _timestamp(value: object) -> datetime:
    text = _compact(value)
    if not text:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _signal_type(record: Mapping[str, Any]) -> MarketSignalType:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), Mapping) else {}
    explicit = _compact(metadata.get("market_signal_type")).upper()
    if explicit:
        try:
            return MarketSignalType(explicit)
        except ValueError:
            pass

    scenario = _compact(record.get("scenario")).upper()
    page_role = _compact(metadata.get("page_role")).upper()
    joined = f"{scenario} {page_role}"
    if "INSOLV" in joined or "LIQUIDATION" in joined or "KONKURS" in joined:
        return MarketSignalType.INSOLVENCY_OR_LIQUIDATION
    if "CLOSURE" in joined or "BUSINESS_CLOSING" in joined or "GESCHÄFTSAUFGABE" in joined:
        return MarketSignalType.BUSINESS_CLOSURE
    if "WAREHOUSE_SURPLUS" in joined or "RESTLAGER" in joined or "LAGERBESTAND" in joined:
        return MarketSignalType.WAREHOUSE_SURPLUS
    if metadata.get("repeated_seller_activity") is True:
        return MarketSignalType.REPEATED_SELLER_ACTIVITY
    if page_role == "EVENT_LEAD" or "AUCTION_EVENT" in joined:
        return MarketSignalType.AUCTION_EVENT
    return MarketSignalType.ITEM_LISTING


def _signal_status(record: Mapping[str, Any]) -> MarketSignalStatus:
    listing = _compact(record.get("listing_status")).upper()
    workflow = _compact(record.get("workflow_status")).upper()
    if listing in {"ENDED", "SOLD", "UNAVAILABLE"} or workflow in {
        "CLOSED",
        "REJECTED",
        "HISTORICAL_MARKET_EVIDENCE",
    }:
        return MarketSignalStatus.CLOSED
    if workflow in {"EARLY_SIGNAL", "CANDIDATE"}:
        return MarketSignalStatus.WATCH
    return MarketSignalStatus.ACTIVE


def _confidence(record: Mapping[str, Any]) -> float | None:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), Mapping) else {}
    score = metadata.get("discovery_score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None
    return min(1.0, max(0.0, float(score) / 100.0))


def market_signal_from_opportunity_record(
    record: Mapping[str, Any],
    *,
    generated_at: datetime,
) -> MarketSignalRecord:
    """Adapt one canonical opportunity snapshot into one durable market signal."""
    opportunity_id = _compact(record.get("opportunity_id"))
    if not opportunity_id:
        raise DomainMarketIntelligenceError("opportunity record has no opportunity_id")
    source_url = _compact(record.get("source_url"))
    if not source_url:
        raise DomainMarketIntelligenceError(f"{opportunity_id} has no source_url")
    title = _compact(record.get("title"))
    if not title:
        raise DomainMarketIntelligenceError(f"{opportunity_id} has no title")
    metadata = record.get("metadata") if isinstance(record.get("metadata"), Mapping) else {}
    evidence = record.get("evidence") if isinstance(record.get("evidence"), list) else []
    signal_type = _signal_type(record)
    value = _compact(metadata.get("reason")) or title
    return MarketSignalRecord(
        signal_id=f"opportunity-signal:{opportunity_id}",
        signal_type=signal_type,
        value=value,
        source=_compact(record.get("source_provider")) or "UNKNOWN_SOURCE",
        observed_at=generated_at,
        confidence=_confidence(record),
        source_country=_compact(record.get("market_code")).upper(),
        source_url=source_url,
        title=title,
        company_name=record.get("company_name"),
        seller_name=metadata.get("seller_name"),
        location=record.get("location"),
        first_observed_at=generated_at,
        latest_observed_at=generated_at,
        event_date=record.get("published_at"),
        evidence=evidence,
        related_opportunity_id=opportunity_id,
        status=_signal_status(record),
        metadata={
            "scenario": record.get("scenario"),
            "workflow_status": record.get("workflow_status"),
            "listing_status": record.get("listing_status"),
            "analysis_eligible": record.get("analysis_eligible") is True,
            "top5_eligible": record.get("top5_eligible") is True,
        },
    )


def _explicit_signals(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path, default=None)
    if payload is None:
        return []
    if isinstance(payload, list):
        raw_signals = payload
    elif isinstance(payload, Mapping):
        raw_signals = payload.get("signals") or []
    else:
        raise DomainMarketIntelligenceError(f"Explicit signal report must be a list or object: {path}")
    if not isinstance(raw_signals, list):
        raise DomainMarketIntelligenceError(f"signals must be a list: {path}")
    return [MarketSignalRecord.model_validate(item).model_dump(mode="json") for item in raw_signals]


def _database_url(path: Path) -> str:
    return f"sqlite:///{path}"


def persist_manifest_market_signals(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    config_path: str | Path = "alembic.ini",
) -> dict[str, Any]:
    """Persist signals for all bounded sources and preserve prior-run signals."""
    root_path = Path(root)
    source_summaries: list[dict[str, Any]] = []
    all_current: dict[str, dict[str, Any]] = {}
    created_ids: list[str] = []
    changed_ids: list[str] = []

    for spec in manifest.get("sources") or []:
        if not isinstance(spec, Mapping):
            continue
        source_name = _compact(spec.get("source_name") or spec.get("source"))
        market_code = _compact(spec.get("market_code")).upper()
        artifact_dir = root_path / _compact(spec.get("artifact_dir"))
        unified_path = artifact_dir / _compact(
            spec.get("unified_report_file") or "unified-opportunity-report.json"
        )
        explicit_path = artifact_dir / _compact(
            spec.get("market_signal_report_file") or "market-signal-report.json"
        )
        database_path = artifact_dir / _compact(
            spec.get("database_file") or "opportunity_engine.db"
        )
        unified = _read_json(unified_path, default=None)
        if not isinstance(unified, Mapping):
            source_summaries.append(
                {
                    "market_code": market_code,
                    "source_name": source_name,
                    "status": "UNAVAILABLE",
                    "signal_count_this_run": 0,
                    "signals_created": 0,
                    "signals_changed": 0,
                    "database_path": None,
                }
            )
            continue

        generated_at = _timestamp(unified.get("generated_at"))
        signals: dict[str, dict[str, Any]] = {}
        records = unified.get("records") or []
        if not isinstance(records, list):
            raise DomainMarketIntelligenceError(f"records must be a list: {unified_path}")
        for raw in records:
            if not isinstance(raw, Mapping):
                continue
            signal = market_signal_from_opportunity_record(raw, generated_at=generated_at)
            signals[signal.signal_id] = signal.model_dump(mode="json")
        for explicit in _explicit_signals(explicit_path):
            signals[str(explicit["signal_id"])] = explicit

        database_path.parent.mkdir(parents=True, exist_ok=True)
        database_url = _database_url(database_path)
        upgrade_database(database_url, config_path=config_path)
        engine = create_database_engine(database_url)
        source_created: list[str] = []
        source_changed: list[str] = []
        try:
            factory = create_session_factory(engine)
            with session_scope(factory) as session:
                repository = MarketSignalRepository(session)
                for signal_id in sorted(signals):
                    outcome = repository.upsert_signal(signals[signal_id])
                    if outcome["created"]:
                        source_created.append(signal_id)
                    elif outcome["changed"]:
                        source_changed.append(signal_id)
                current = repository.list_current()
                for model in current:
                    if isinstance(model.payload_json, Mapping):
                        all_current[model.signal_id] = dict(model.payload_json)
        finally:
            engine.dispose()

        created_ids.extend(source_created)
        changed_ids.extend(source_changed)
        source_summaries.append(
            {
                "market_code": market_code,
                "source_name": source_name,
                "status": "SUCCESS",
                "signal_count_this_run": len(signals),
                "signals_created": len(source_created),
                "created_signal_ids": source_created,
                "signals_changed": len(source_changed),
                "changed_signal_ids": source_changed,
                "database_path": database_path.relative_to(root_path).as_posix(),
            }
        )

    return {
        "schema_version": "domain-market-signal-persistence-1.0",
        "source_count": len(source_summaries),
        "sources": source_summaries,
        "created_signal_ids": sorted(set(created_ids)),
        "changed_signal_ids": sorted(set(changed_ids)),
        "current_signal_count": len(all_current),
        "current_signals": [all_current[key] for key in sorted(all_current)],
    }


def _first_source_name(item: Mapping[str, Any]) -> str | None:
    direct = _compact(item.get("source_name"))
    if direct:
        return direct
    raw = item.get("source_names")
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        for value in raw:
            text = _compact(value)
            if text:
                return text
    return None


def _direct_opportunities(checkpoint: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in checkpoint.get("deduplicated_opportunities") or []:
        if not isinstance(item, Mapping):
            continue
        workflow = _compact(item.get("workflow_status")).upper()
        if workflow not in DIRECT_WORKFLOWS:
            continue
        missing = item.get("missing_evidence")
        if not isinstance(missing, list):
            missing = item.get("missing_information")
        result.append(
            {
                "opportunity_identity": item.get("opportunity_identity"),
                "title": item.get("title"),
                "market_code": item.get("market_code"),
                "source_name": _first_source_name(item),
                "source_url": item.get("source_url") or item.get("canonical_url"),
                "workflow_status": workflow,
                "listing_status": item.get("listing_status"),
                "discovery_score": item.get("discovery_score"),
                "location": item.get("location"),
                "quantity": item.get("quantity"),
                "analysis_eligible": item.get("analysis_eligible") is True,
                "top5_eligible": item.get("top5_eligible") is True,
                "missing_information": list(missing or []),
            }
        )
    return result


def _early_signals(signals: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = [
        dict(signal)
        for signal in signals
        if (
            not _compact(signal.get("related_opportunity_id"))
            or _compact(signal.get("signal_type")).upper() in EARLY_SIGNAL_TYPES
        )
        and _compact(signal.get("status")).upper() in {"ACTIVE", "WATCH"}
    ]
    return sorted(
        result,
        key=lambda item: (
            -(float(item.get("confidence")) if isinstance(item.get("confidence"), (int, float)) else -1.0),
            _compact(item.get("signal_id")),
        ),
    )


def _selected_action(
    checkpoint: Mapping[str, Any], early_signals: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    existing = checkpoint.get("next_human_action")
    if isinstance(existing, Mapping):
        action = _compact(existing.get("action")).upper()
        if action and action != "NO_IMMEDIATE_ACTION":
            return {
                "action": action,
                "reason": existing.get("reason"),
                "opportunity_identity": existing.get("opportunity_identity"),
                "signal_id": None,
            }
    if early_signals:
        signal = early_signals[0]
        signal_type = _compact(signal.get("signal_type")).upper()
        if signal_type == MarketSignalType.REPEATED_SELLER_ACTIVITY.value:
            action = "INVESTIGATE_RELATED_INVENTORY"
            reason = "Repeated seller activity may indicate additional clothing inventory."
        elif signal_type in {
            MarketSignalType.BUSINESS_CLOSURE.value,
            MarketSignalType.INSOLVENCY_OR_LIQUIDATION.value,
        }:
            action = "MONITOR_INVENTORY_RELEASE"
            reason = "The business event may produce a clothing inventory sale later."
        else:
            action = "VERIFY_MARKET_SIGNAL"
            reason = "The strongest early signal should be checked before it becomes a direct opportunity."
        return {
            "action": action,
            "reason": reason,
            "opportunity_identity": None,
            "signal_id": signal.get("signal_id"),
        }
    return {
        "action": "NO_IMMEDIATE_ACTION",
        "reason": "No credible direct opportunity or early market signal requires action.",
        "opportunity_identity": None,
        "signal_id": None,
    }


def build_domain_market_intelligence_brief(
    checkpoint: Mapping[str, Any],
    signal_persistence: Mapping[str, Any],
) -> dict[str, Any]:
    """Separate early market news from direct actionable opportunities."""
    current = [
        dict(item)
        for item in signal_persistence.get("current_signals") or []
        if isinstance(item, Mapping)
    ]
    by_id = {_compact(item.get("signal_id")): item for item in current}
    created_ids = [_compact(item) for item in signal_persistence.get("created_signal_ids") or []]
    changed_ids = [_compact(item) for item in signal_persistence.get("changed_signal_ids") or []]
    new_signals = [by_id[item] for item in created_ids if item in by_id]
    changed_signals = [by_id[item] for item in changed_ids if item in by_id]
    early = _early_signals(current)
    direct = _direct_opportunities(checkpoint)
    coverage = [
        {
            "market_code": item.get("market_code"),
            "source_name": item.get("source_name"),
            "execution_status": item.get("execution_status"),
            "persistence_status": item.get("persistence_status"),
        }
        for item in checkpoint.get("sources") or []
        if isinstance(item, Mapping)
    ]
    unavailable = [
        item
        for item in coverage
        if _compact(item.get("execution_status")).upper() in {"FAILURE", "BLOCKED"}
    ]
    action = _selected_action(checkpoint, early)
    return {
        "schema_version": BRIEF_SCHEMA_VERSION,
        "generated_at": checkpoint.get("generated_at"),
        "market_coverage": checkpoint.get("market_coverage") or ["NO", "SE", "DE"],
        "new_signals_today": new_signals,
        "changed_signals_since_previous_checkpoint": changed_signals,
        "early_signals_to_watch": early,
        "current_direct_opportunities": direct,
        "selected_human_action": action,
        "source_coverage": coverage,
        "unavailable_or_failed_sources": unavailable,
        "counts": {
            "new_signals_today": len(new_signals),
            "changed_signals_since_previous_checkpoint": len(changed_signals),
            "early_signals_to_watch": len(early),
            "current_direct_opportunities": len(direct),
            "unavailable_or_failed_sources": len(unavailable),
        },
        "truthful_zero_result": not new_signals and not changed_signals and not early and not direct,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def render_domain_market_intelligence_brief(brief: Mapping[str, Any]) -> str:
    counts = brief.get("counts") or {}
    action = brief.get("selected_human_action") or {}
    lines = [
        "نشرة استخبارات سوق مخزون الملابس",
        f"الوقت: {brief.get('generated_at')}",
        "الأسواق: النرويج | السويد | ألمانيا",
        f"إشارات جديدة اليوم: {counts.get('new_signals_today', 0)}",
        f"إشارات تغيرت: {counts.get('changed_signals_since_previous_checkpoint', 0)}",
        f"إشارات مبكرة للمراقبة: {counts.get('early_signals_to_watch', 0)}",
        f"فرص مباشرة حالية: {counts.get('current_direct_opportunities', 0)}",
        f"مصادر فاشلة أو محجوبة: {counts.get('unavailable_or_failed_sources', 0)}",
        f"الإجراء البشري الوحيد: {action.get('action', 'NO_IMMEDIATE_ACTION')}",
        f"السبب: {action.get('reason', '')}",
        "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي.",
    ]
    return "\n".join(lines) + "\n"


def write_domain_market_intelligence_artifacts(
    brief: Mapping[str, Any],
    *,
    json_path: str | Path,
    text_path: str | Path,
) -> None:
    Path(json_path).write_text(
        json.dumps(dict(brief), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path(text_path).write_text(
        render_domain_market_intelligence_brief(brief),
        encoding="utf-8",
    )
