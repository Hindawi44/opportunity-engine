"""Italy discovery adapter for durable entity memory and existing follow-up continuity.

The Italy market radar deliberately emits signal-only public-web evidence. This
adapter adds one conservative bridge: when an Italy signal contains a concrete
company identity, it is converted into the ENTITY_SCENT contract already used by
SIGNAL_FOLLOW_UP_ENGINE_V1. The existing memory/case/follow-up implementation is
reused; no second follow-up engine is created.

Generic fashion, outlet, stock and editorial pages are never promoted into entity
memory merely because they matched an Italy discovery query.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence

from opportunity_engine.discovery import signal_follow_up_continuity as continuity
from opportunity_engine.discovery import signal_follow_up_memory as memory
from opportunity_engine.discovery.italy_market_discovery import FEED_FAMILY
from opportunity_engine.discovery.search_provider import SearchProvider
from opportunity_engine.persistence import upgrade_database


SCHEMA_VERSION = "italy-case-memory-adapter-1.0"
ENGINE_VERSION = "ITALY_CASE_MEMORY_ADAPTER_V1"
MARKET_CODE = "IT"
ITALY_MEMORY_RELATIVE_PATH = Path("it-market/opportunity_engine.db")

_ITALY_STAGE_QUERIES: tuple[tuple[str, str], ...] = (
    (
        "MAGAZZINO",
        '"{label}" (magazzino OR rimanenze OR stock) '
        '(abbigliamento OR moda OR tessile OR calzature)',
    ),
    (
        "ASTA",
        '"{label}" (asta OR "asta giudiziaria" OR "vendita giudiziaria" '
        'OR "vendita fallimentare")',
    ),
    (
        "SVENDITA",
        '"{label}" (svendita OR "liquidazione totale" OR "vendita stock" '
        'OR "cessazione attività")',
    ),
    (
        "LIQUIDAZIONE",
        '"{label}" ("liquidazione giudiziale" OR curatore '
        'OR "procedura concorsuale" OR fallimento)',
    ),
    (
        "LOTTI_CONCRETI",
        '"{label}" (lotto OR lotti OR stock OR rimanenze) '
        '(vendita OR asta OR prezzo OR disponibile)',
    ),
)

_ITALY_COMMERCIAL_TERMS = (
    "magazzino",
    "rimanenze",
    "stock",
    "asta",
    "asta giudiziaria",
    "vendita giudiziaria",
    "vendita fallimentare",
    "svendita",
    "liquidazione totale",
    "vendita stock",
    "cessazione attività",
    "liquidazione giudiziale",
    "curatore",
    "procedura concorsuale",
    "fallimento",
    "lotto",
    "lotti",
    "in vendita",
    "vendita",
    "prezzo",
    "disponibile",
    "disponibili",
    "pronta consegna",
)

_ITALY_AUCTION_TERMS = (
    "asta",
    "asta giudiziaria",
    "vendita giudiziaria",
    "vendita fallimentare",
)

_LEGAL_FORM = (
    r"(?:s\.?\s*r\.?\s*l\.?|s\.?\s*p\.?\s*a\.?|s\.?\s*n\.?\s*c\.?|"
    r"s\.?\s*a\.?\s*s\.?|societ[aà]\s+cooperativa)"
)
_EVENT_PREFIX = re.compile(
    r"^(?:"
    r"liquidazione\s+giudiziale\s+(?:di|del|della)\s+|"
    r"fallimento\s+(?:di|del|della)\s+|"
    r"procedura\s+concorsuale\s+(?:di|del|della)\s+|"
    r"cessazione\s+(?:dell['’]\s*)?attivit[aà]\s+(?:di|del|della)?\s*|"
    r"asta\s+giudiziaria\s+(?:di|del|della)?\s*"
    r")",
    flags=re.IGNORECASE,
)
_LEGAL_ENTITY_RE = re.compile(
    rf"(?P<label>[A-ZÀ-ÖØ-Þ0-9][^|:;!?]{{1,110}}?\b{_LEGAL_FORM}\b)",
    flags=re.IGNORECASE,
)
_GENERIC_ENTITY_TOKENS = {
    "abbigliamento",
    "atelier",
    "calzature",
    "fashion",
    "italia",
    "italy",
    "moda",
    "outlet",
    "scarpe",
    "sposa",
    "spose",
    "stock",
    "tessile",
    "tessili",
}

ProviderFactory = Callable[[str, str], SearchProvider]


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _metadata(signal: Mapping[str, Any]) -> dict[str, Any]:
    raw = signal.get("metadata")
    return dict(raw) if isinstance(raw, Mapping) else {}


def _entity_key(label: str) -> str:
    value = label.casefold()
    value = re.sub(rf"\b{_LEGAL_FORM}\b", " ", value, flags=re.IGNORECASE)
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9à-öø-ÿ]+", " ", value)
    return " ".join(value.split()).strip()


def _plausible_entity(label: str, key: str) -> bool:
    if not 2 <= len(label) <= 120 or not 2 <= len(key) <= 100:
        return False
    tokens = [token for token in key.split() if len(token) >= 3]
    if not tokens:
        return False
    return any(token not in _GENERIC_ENTITY_TOKENS for token in tokens)


def _extract_entity(signal: Mapping[str, Any]) -> tuple[str | None, str | None, str, int]:
    explicit = _compact(signal.get("company_name") or signal.get("seller_name"))
    if explicit:
        key = _entity_key(explicit)
        if _plausible_entity(explicit, key):
            return explicit, key, "EXPLICIT_SIGNAL_COMPANY", 85

    title = _compact(signal.get("title"))
    if not title:
        return None, None, "NO_TITLE", 0
    candidate_text = _EVENT_PREFIX.sub("", title, count=1).strip()
    match = _LEGAL_ENTITY_RE.search(candidate_text)
    if not match:
        return None, None, "NO_EXPLICIT_ITALIAN_ENTITY", 0
    label = _compact(match.group("label")).strip(" -–—|:,.;")
    key = _entity_key(label)
    if not _plausible_entity(label, key):
        return None, None, "GENERIC_OR_IMPLAUSIBLE_ENTITY", 0
    return label, key, "ITALIAN_LEGAL_FORM_IN_TITLE", 78


def register_italy_follow_up_contract() -> None:
    """Register Italy with the existing memory and continuity engines.

    Registration is intentionally local to callers that opt into the Italy adapter;
    importing the legacy NO/SE/DE modules alone keeps their behaviour unchanged.
    """
    memory._MEMORY_DATABASES[MARKET_CODE] = ITALY_MEMORY_RELATIVE_PATH
    memory._STAGE_QUERIES[MARKET_CODE] = _ITALY_STAGE_QUERIES
    continuity._COMMERCIAL_TERMS[MARKET_CODE] = _ITALY_COMMERCIAL_TERMS
    continuity._AUCTION_TERMS[MARKET_CODE] = _ITALY_AUCTION_TERMS


def adapt_italy_signal_to_entity_memory(
    signal: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """Convert one clean Italy discovery signal into the existing ENTITY_SCENT contract."""
    if not isinstance(signal, Mapping):
        return None, "INVALID_SIGNAL"
    metadata = _metadata(signal)
    if _compact(signal.get("source_country")).upper() != MARKET_CODE:
        return None, "NOT_ITALY"
    if _compact(metadata.get("feed_family")) != FEED_FAMILY:
        return None, "NOT_ITALY_DISCOVERY_FEED"

    label, key, shape, score = _extract_entity(signal)
    if not label or not key:
        return None, shape

    payload = deepcopy(dict(signal))
    payload["company_name"] = _compact(payload.get("company_name")) or label
    payload["source"] = "Italy market discovery radar + case memory adapter V1"
    adapted_metadata = _metadata(payload)
    adapted_metadata.update(
        {
            "entity_scent_classification": "ENTITY_SCENT",
            "entity_scent_quality_gate": ENGINE_VERSION,
            "entity_key": key,
            "entity_label": label,
            "entity_shape": shape,
            "entity_cluster_score": score,
            "entity_evidence_count": 1,
            "entity_independent_source_count": 1,
            "italy_case_memory_adapter": ENGINE_VERSION,
            "signal_only": True,
            "source_page_verification_required": True,
            "promotion_to_opportunity_allowed": False,
            "top5_eligible": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        }
    )
    payload["metadata"] = adapted_metadata
    return payload, None


def build_italy_case_memory_adapter(
    signals: Sequence[Mapping[str, Any]],
    *,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Adapt clean Italy signals and project stable entity cases without persistence."""
    register_italy_follow_up_contract()
    now = _utc(observed_at)
    adapted: list[dict[str, Any]] = []
    rejections: dict[str, int] = {}
    for signal in signals:
        payload, reason = adapt_italy_signal_to_entity_memory(signal)
        if payload is not None:
            adapted.append(payload)
            continue
        key = reason or "REJECTED"
        rejections[key] = rejections.get(key, 0) + 1

    stable = memory.dedupe_entity_signals(adapted)
    cases = memory.build_persistent_entity_cases(stable, observed_at=now)
    plan = memory.build_persistent_entity_follow_up_plan(
        cases,
        observed_at=now,
        max_cases=memory.MAX_CASES,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "generated_at": now.isoformat(),
        "source_country": MARKET_CODE,
        "input_signal_count": len(signals),
        "adapted_entity_signal_count": len(stable),
        "rejected_signal_count": len(signals) - len(stable),
        "rejection_counts": dict(sorted(rejections.items())),
        "persistent_case_count": len(cases),
        "entity_signals": stable,
        "cases": cases,
        "follow_up_plan": [
            {key: value for key, value in row.items() if key != "_source_case"}
            for row in plan
        ],
        "promotion_to_opportunity_allowed": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def ensure_italy_memory_database(
    input_root: str | Path,
    *,
    config_path: str | Path = "alembic.ini",
) -> Path:
    """Create or migrate the dedicated Italy market-signal SQLite database."""
    register_italy_follow_up_contract()
    path = Path(input_root) / ITALY_MEMORY_RELATIVE_PATH
    database_url = f"sqlite:///{path.resolve().as_posix()}"
    upgrade_database(database_url, config_path=config_path)
    return path


def run_italy_case_memory_cycle(
    current_signals: Sequence[Mapping[str, Any]],
    *,
    input_root: str | Path,
    cases_report: Mapping[str, Any] | None = None,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory | None = None,
    observed_at: datetime | None = None,
    max_cases: int = memory.DEFAULT_MAX_CASES,
    results_per_case: int = continuity.DEFAULT_RESULTS_PER_CASE,
    config_path: str | Path = "alembic.ini",
) -> dict[str, Any]:
    """Persist Italy entity scents, reload memory, and run the existing Follow-Up engine."""
    register_italy_follow_up_contract()
    now = _utc(observed_at)
    adapter = build_italy_case_memory_adapter(current_signals, observed_at=now)
    ensure_italy_memory_database(input_root, config_path=config_path)
    persistence = memory.persist_entity_scent_signals(
        adapter["entity_signals"],
        input_root=input_root,
    )
    loaded, load_errors = memory.load_persisted_entity_scent_signals(input_root=input_root)
    italy_loaded = [
        signal
        for signal in loaded
        if _compact(signal.get("source_country")).upper() == MARKET_CODE
    ]
    combined = memory.dedupe_entity_signals(
        [*italy_loaded, *adapter["entity_signals"]]
    )
    follow_up = continuity.run_signal_follow_up_engine_with_continuity(
        cases_report or {"cases": []},
        entity_signals=combined,
        environment=environment or {},
        provider_factory=provider_factory,
        observed_at=now,
        max_cases=max_cases,
        results_per_case=results_per_case,
    )
    cases = memory.build_persistent_entity_cases(combined, observed_at=now)
    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "generated_at": now.isoformat(),
        "source_country": MARKET_CODE,
        "memory_database": (Path(input_root) / ITALY_MEMORY_RELATIVE_PATH).as_posix(),
        "adapter": adapter,
        "persistence": {
            **persistence,
            "load_error_count": len(load_errors),
            "load_errors": load_errors,
            "loaded_italy_entity_signal_count": len(italy_loaded),
            "combined_italy_entity_signal_count": len(combined),
        },
        "persistent_case_count": len(cases),
        "cases": cases,
        "follow_up": follow_up,
        "promotion_to_opportunity_allowed": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
