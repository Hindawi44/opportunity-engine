"""Durable entity-scent memory for signal follow-up continuity."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.discovery.brave_market_signal_continuity import stabilize_brave_signal
from opportunity_engine.discovery.signal_follow_up_engine import (
    DEFAULT_MAX_CASES,
    MAX_CASES,
    _canonical_url,
    _explicit_commercial_links,
    _normalise,
)
from opportunity_engine.persistence import (
    MarketSignalRepository,
    create_database_engine,
    create_session_factory,
    session_scope,
)

SCHEMA_VERSION = "signal-follow-up-continuity-1.0"
MEMORY_BACKEND = "RESTORED_SOURCE_SQLITE_MARKET_SIGNALS"

_MEMORY_DATABASES = {
    "NO": Path("no-finn-email/opportunity_engine.db"),
    "SE": Path("se-blinto/opportunity_engine.db"),
    "DE": Path("de-riegermann/opportunity_engine.db"),
}

_STAGE_QUERIES: dict[str, tuple[tuple[str, str], ...]] = {
    "DE": (
        ("WARENBESTAND", '"{label}" (Warenbestand OR Lagerbestand) (Bekleidung OR Mode OR Textil)'),
        ("AUKTION", '"{label}" (Auktion OR Versteigerung OR Insolvenzauktion)'),
        ("LAGERVERKAUF", '"{label}" (Lagerverkauf OR Lagerauflösung OR Räumungsverkauf)'),
        ("VERWERTUNG", '"{label}" (Verwertung OR Insolvenzverwalter OR Masseverwertung)'),
        ("KONKRETE_LOTS", '"{label}" (Los OR Lose OR Posten OR Warenposten) (Auktion OR Verkauf OR Verwertung)'),
    ),
    "SE": (
        ("VARULAGER", '"{label}" (varulager OR butikslager OR restlager) (kläder OR mode OR textil)'),
        ("AUKTION", '"{label}" (auktion OR konkursauktion)'),
        ("LAGERFÖRSÄLJNING", '"{label}" (lagerförsäljning OR utförsäljning OR lagerrensning)'),
        ("FÖRVALTARFÖRSÄLJNING", '"{label}" (konkursförvaltare OR försäljning OR avveckling)'),
        ("KONKRETA_PARTIER", '"{label}" (lagerparti OR parti OR auktionsobjekt) (auktion OR försäljning)'),
    ),
    "NO": (
        ("VARELAGER", '"{label}" (varelager OR restlager) (klær OR tekstil OR bekledning)'),
        ("AUKSJON", '"{label}" (auksjon OR konkursauksjon)'),
        ("LAGERSALG", '"{label}" (lagersalg OR opphørssalg OR avviklingssalg)'),
        ("BOREALISASJON", '"{label}" (bostyrer OR realisasjon OR salg)'),
        ("KONKRETE_PARTIER", '"{label}" (parti OR vareparti OR auksjonsobjekt) (auksjon OR salg)'),
    ),
}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _parse_time(value: object, fallback: datetime) -> datetime:
    text = _compact(value)
    if text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    return fallback


def _metadata(signal: Mapping[str, Any]) -> dict[str, Any]:
    value = signal.get("metadata")
    return dict(value) if isinstance(value, Mapping) else {}


def _eligible_signal(signal: Mapping[str, Any]) -> bool:
    metadata = _metadata(signal)
    market = _compact(signal.get("source_country")).upper()
    return (
        market in _MEMORY_DATABASES
        and _compact(metadata.get("entity_scent_classification")).upper() == "ENTITY_SCENT"
        and bool(_compact(metadata.get("entity_key")))
        and bool(_compact(metadata.get("entity_label")))
    )


def dedupe_entity_signals(signals: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for raw in signals:
        if not isinstance(raw, Mapping) or not _eligible_signal(raw):
            continue
        signal_id = _compact(raw.get("signal_id"))
        if signal_id:
            by_id[signal_id] = stabilize_brave_signal(raw)
    return [by_id[key] for key in sorted(by_id)]


def _database_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def persist_entity_scent_signals(
    signals: Sequence[Mapping[str, Any]], *, input_root: str | Path
) -> dict[str, Any]:
    root = Path(input_root)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stable = dedupe_entity_signals(signals)
    for signal in stable:
        grouped[_compact(signal.get("source_country")).upper()].append(signal)

    saved = changed = 0
    databases: list[str] = []
    errors: list[str] = []
    for market, rows in sorted(grouped.items()):
        path = root / _MEMORY_DATABASES[market]
        if not path.exists():
            errors.append(f"{market}: memory database missing: {path.as_posix()}")
            continue
        engine = create_database_engine(_database_url(path))
        try:
            factory = create_session_factory(engine)
            with session_scope(factory) as session:
                repository = MarketSignalRepository(session)
                for row in rows:
                    result = repository.upsert_signal(row)
                    saved += 1
                    changed += int(bool(result.get("created") or result.get("changed")))
            databases.append(path.as_posix())
        except Exception as exc:  # continuity must not block the daily bulletin
            errors.append(f"{market}: {type(exc).__name__}: {_compact(exc)[:300]}")
        finally:
            engine.dispose()
    return {
        "backend": MEMORY_BACKEND,
        "input_entity_signal_count": len(stable),
        "persisted_signal_count": saved,
        "new_or_changed_signal_count": changed,
        "databases": databases,
        "errors": errors,
    }


def load_persisted_entity_scent_signals(
    *, input_root: str | Path
) -> tuple[list[dict[str, Any]], list[str]]:
    root = Path(input_root)
    signals: list[dict[str, Any]] = []
    errors: list[str] = []
    for market, relative in sorted(_MEMORY_DATABASES.items()):
        path = root / relative
        if not path.exists():
            continue
        engine = create_database_engine(_database_url(path))
        try:
            factory = create_session_factory(engine)
            with session_scope(factory) as session:
                repository = MarketSignalRepository(session)
                for model in repository.list_current():
                    payload = model.payload_json
                    if isinstance(payload, Mapping) and _eligible_signal(payload):
                        signals.append(dict(payload))
        except Exception as exc:
            errors.append(f"{market}: {type(exc).__name__}: {_compact(exc)[:300]}")
        finally:
            engine.dispose()
    return dedupe_entity_signals(signals), errors


def build_persistent_entity_cases(
    signals: Sequence[Mapping[str, Any]], *, observed_at: datetime | None = None
) -> list[dict[str, Any]]:
    now = _utc(observed_at)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for signal in dedupe_entity_signals(signals):
        metadata = _metadata(signal)
        market = _compact(signal.get("source_country")).upper()
        entity_key = _normalise(metadata.get("entity_key"))
        if entity_key:
            groups[(market, entity_key)].append(signal)

    cases: list[dict[str, Any]] = []
    for (market, entity_key), rows in groups.items():
        first_seen = min(_parse_time(row.get("first_observed_at"), now) for row in rows)
        last_seen = max(
            _parse_time(row.get("latest_observed_at") or row.get("observed_at"), now)
            for row in rows
        )
        labels = [_compact(_metadata(row).get("entity_label")) for row in rows]
        labels = [label for label in labels if label]
        label = max(labels, key=len) if labels else entity_key
        score = max(int(_metadata(row).get("entity_cluster_score") or 0) for row in rows)
        urls = sorted(
            {url for row in rows if (url := _canonical_url(row.get("source_url"))) is not None}
        )
        stable_id = sha256(f"{market}|{entity_key}".encode("utf-8")).hexdigest()[:24]
        cases.append(
            {
                "case_id": f"persistent-entity-case:{stable_id}",
                "case_type": "COMPANY_LIQUIDATION",
                "case_title": label,
                "case_status": "WATCH",
                "countries": [market],
                "grouping_basis": "COMPANY",
                "grouping_key": f"{market}:{entity_key}",
                "commercial_strength": score,
                "first_seen": first_seen.isoformat(),
                "last_seen": last_seen.isoformat(),
                "source_urls": urls[:30],
                "persistent_entity_scent": True,
                "entity_key": entity_key,
                "entity_label": label,
                "entity_source_signal_count": len(rows),
            }
        )
    cases.sort(
        key=lambda item: (
            -int(item.get("commercial_strength") or 0),
            _compact((item.get("countries") or [""])[0]),
            _compact(item.get("entity_key")),
        )
    )
    return cases


def _stage(case: Mapping[str, Any], observed_at: datetime) -> tuple[int, str, str]:
    market = _compact((case.get("countries") or [""])[0]).upper()
    stages = _STAGE_QUERIES[market]
    first_seen = _parse_time(case.get("first_seen"), observed_at)
    index = max(0, (observed_at.date() - first_seen.date()).days) % len(stages)
    name, template = stages[index]
    label = _compact(case.get("entity_label") or case.get("case_title")).replace('"', "")
    return index, name, template.format(label=label)


def build_persistent_entity_follow_up_plan(
    cases: Sequence[Mapping[str, Any]],
    *,
    all_current_cases: Sequence[Mapping[str, Any]] = (),
    observed_at: datetime | None = None,
    max_cases: int = DEFAULT_MAX_CASES,
) -> list[dict[str, Any]]:
    now = _utc(observed_at)
    bounded = max(0, min(MAX_CASES, int(max_cases)))
    plan: list[dict[str, Any]] = []
    for raw in cases[:bounded]:
        case = dict(raw)
        market = _compact((case.get("countries") or [""])[0]).upper()
        label = _compact(case.get("entity_label") or case.get("case_title"))
        if market not in _STAGE_QUERIES or not label:
            continue
        stage_index, stage_name, query = _stage(case, now)
        source_case = dict(case)
        source_case.update(
            {
                "_follow_up_market": market,
                "_follow_up_target": label,
                "_follow_up_target_kind": "PERSISTENT_ENTITY_SCENT",
            }
        )
        plan.append(
            {
                "case_id": case.get("case_id"),
                "case_type": case.get("case_type"),
                "case_title": case.get("case_title"),
                "country": market,
                "target_label": label,
                "target_kind": "PERSISTENT_ENTITY_SCENT",
                "query": query,
                "first_seen": case.get("first_seen"),
                "last_seen": case.get("last_seen"),
                "follow_up_stage_index": stage_index,
                "follow_up_stage": stage_name,
                "source_urls": list(case.get("source_urls") or [])[:30],
                "explicit_linked_commercial_case_ids": _explicit_commercial_links(case, all_current_cases),
                "memory_backend": MEMORY_BACKEND,
                "_source_case": source_case,
            }
        )
    return plan
