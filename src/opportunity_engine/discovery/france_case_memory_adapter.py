"""France discovery adapter for durable entity memory and existing Follow-Up.

France discovery stays signal-only. When a concrete French company identity is
visible, this adapter converts the signal into the existing ENTITY_SCENT contract
and reuses SIGNAL_FOLLOW_UP_ENGINE_V1. Generic auction, stock and editorial pages
never become company cases merely because they matched a France query.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence

from opportunity_engine.discovery import signal_follow_up_continuity as continuity
from opportunity_engine.discovery import signal_follow_up_memory as memory
from opportunity_engine.discovery.france_market_discovery import FEED_FAMILY
from opportunity_engine.discovery.search_provider import SearchProvider
from opportunity_engine.persistence import upgrade_database


SCHEMA_VERSION = "france-case-memory-adapter-1.0"
ENGINE_VERSION = "FRANCE_CASE_MEMORY_ADAPTER_V1"
MARKET_CODE = "FR"
FRANCE_MEMORY_RELATIVE_PATH = Path("fr-market/opportunity_engine.db")

_FRANCE_STAGE_QUERIES: tuple[tuple[str, str], ...] = (
    (
        "STOCK_MARCHANDISES",
        '"{label}" ("stock marchandises" OR "stock vêtements" OR inventaire OR palettes) '
        '(vêtements OR "prêt-à-porter" OR textile OR chaussures)',
    ),
    (
        "VENTE_AUX_ENCHERES",
        '"{label}" ("vente aux enchères" OR "vente judiciaire" OR enchères OR adjudication)',
    ),
    (
        "DESTOCKAGE",
        '"{label}" (déstockage OR destockage OR "liquidation totale" OR "vente de stock")',
    ),
    (
        "LIQUIDATEUR",
        '"{label}" ("liquidation judiciaire" OR liquidateur OR "mandataire judiciaire" '
        'OR "procédure collective")',
    ),
    (
        "LOTS_CONCRETS",
        '"{label}" (lot OR lots OR palettes OR "stock entier") '
        '(vente OR enchères OR estimation OR prix)',
    ),
)

_FRANCE_COMMERCIAL_TERMS = (
    "stock marchandises", "stock vêtements", "stock de vêtements", "inventaire",
    "palettes", "vente aux enchères", "vente judiciaire", "enchères", "adjudication",
    "déstockage", "destockage", "liquidation totale", "vente de stock",
    "liquidation judiciaire", "liquidateur", "mandataire judiciaire",
    "procédure collective", "lot", "lots", "stock entier", "vente", "estimation", "prix",
)
_FRANCE_AUCTION_TERMS = (
    "vente aux enchères", "vente aux encheres", "vente judiciaire", "enchères",
    "encheres", "adjudication", "lot judiciaire",
)

_LEGAL_FORM = r"(?:sasu|sas|sarl|eurl|sa|snc|sca|scs|selarl|selas)"
_EVENT_PREFIX = re.compile(
    r"^(?:liquidation\s+judiciaire\s+(?:de|du|de\s+la)\s+|"
    r"redressement\s+judiciaire\s+(?:de|du|de\s+la)\s+|"
    r"vente\s+judiciaire\s+(?:de|du|de\s+la)?\s*|"
    r"vente\s+aux\s+ench[eè]res\s+(?:de|du|de\s+la)?\s*)",
    flags=re.IGNORECASE,
)
_LEGAL_SUFFIX_RE = re.compile(
    rf"(?P<label>[A-ZÀ-ÖØ-Þ0-9][^|:;!?]{{1,105}}?\b{_LEGAL_FORM}\b)",
    flags=re.IGNORECASE,
)
_LEGAL_PREFIX_RE = re.compile(
    rf"\b(?P<form>{_LEGAL_FORM})\s+(?P<name>[A-ZÀ-ÖØ-Þ0-9][A-ZÀ-ÖØ-Þ0-9 &'’._-]{{1,100}})",
    flags=re.IGNORECASE,
)
_DENOMINATION_RE = re.compile(
    r"\bd[ée]nomination\s*:\s*(?P<label>[A-ZÀ-ÖØ-Þ0-9][A-ZÀ-ÖØ-Þ0-9 &'’._-]{1,100}?)"
    r"(?=\s+(?:forme\s+juridique|activit[ée]|adresse|n[°o]\s*rcs|rcs|siret|greffe)\b|$)",
    flags=re.IGNORECASE,
)
_GENERIC_ENTITY_TOKENS = {
    "boutique", "chaussures", "fashion", "france", "friperie", "habillement",
    "lingerie", "mariage", "mode", "outlet", "pret", "porter", "stock", "textile",
    "vetement", "vetements", "vêtement", "vêtements",
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
    tokens = [token for token in key.split() if len(token) >= 2]
    if not tokens:
        return False
    return any(token not in _GENERIC_ENTITY_TOKENS for token in tokens)


def _evidence_text(signal: Mapping[str, Any]) -> str:
    parts = [_compact(signal.get("title")), _compact(signal.get("value"))]
    evidence = signal.get("evidence")
    if isinstance(evidence, Sequence) and not isinstance(evidence, (str, bytes)):
        for item in evidence:
            if isinstance(item, Mapping):
                parts.append(_compact(item.get("value")))
    return " ".join(part for part in parts if part)


def _extract_entity(signal: Mapping[str, Any]) -> tuple[str | None, str | None, str, int]:
    explicit = _compact(signal.get("company_name") or signal.get("seller_name"))
    if explicit:
        key = _entity_key(explicit)
        if _plausible_entity(explicit, key):
            return explicit, key, "EXPLICIT_SIGNAL_COMPANY", 88

    text = _evidence_text(signal)
    if not text:
        return None, None, "NO_TEXT", 0

    denomination = _DENOMINATION_RE.search(text)
    if denomination:
        label = _compact(denomination.group("label")).strip(" -–—|:,.;")
        key = _entity_key(label)
        if _plausible_entity(label, key):
            return label, key, "BODACC_DENOMINATION", 95

    title = _compact(signal.get("title"))
    candidate_text = _EVENT_PREFIX.sub("", title, count=1).strip() if title else text
    suffix = _LEGAL_SUFFIX_RE.search(candidate_text)
    if suffix:
        label = _compact(suffix.group("label")).strip(" -–—|:,.;")
        key = _entity_key(label)
        if _plausible_entity(label, key):
            return label, key, "FRENCH_LEGAL_FORM_IN_TITLE", 82

    prefix = _LEGAL_PREFIX_RE.search(candidate_text)
    if prefix:
        label = _compact(f"{prefix.group('name')} {prefix.group('form')}").strip(" -–—|:,.;")
        key = _entity_key(label)
        if _plausible_entity(label, key):
            return label, key, "FRENCH_LEGAL_FORM_PREFIX", 80

    return None, None, "NO_EXPLICIT_FRENCH_ENTITY", 0


def register_france_follow_up_contract() -> None:
    memory._MEMORY_DATABASES[MARKET_CODE] = FRANCE_MEMORY_RELATIVE_PATH
    memory._STAGE_QUERIES[MARKET_CODE] = _FRANCE_STAGE_QUERIES
    continuity._COMMERCIAL_TERMS[MARKET_CODE] = _FRANCE_COMMERCIAL_TERMS
    continuity._AUCTION_TERMS[MARKET_CODE] = _FRANCE_AUCTION_TERMS


def adapt_france_signal_to_entity_memory(
    signal: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(signal, Mapping):
        return None, "INVALID_SIGNAL"
    metadata = _metadata(signal)
    if _compact(signal.get("source_country")).upper() != MARKET_CODE:
        return None, "NOT_FRANCE"
    if _compact(metadata.get("feed_family")) != FEED_FAMILY:
        return None, "NOT_FRANCE_DISCOVERY_FEED"

    label, key, shape, score = _extract_entity(signal)
    if not label or not key:
        return None, shape

    payload = deepcopy(dict(signal))
    payload["company_name"] = _compact(payload.get("company_name")) or label
    payload["source"] = "France market discovery radar + case memory adapter V1"
    adapted_metadata = _metadata(payload)
    adapted_metadata.update({
        "entity_scent_classification": "ENTITY_SCENT",
        "entity_scent_quality_gate": ENGINE_VERSION,
        "entity_key": key,
        "entity_label": label,
        "entity_shape": shape,
        "entity_cluster_score": score,
        "entity_evidence_count": 1,
        "entity_independent_source_count": 1,
        "france_case_memory_adapter": ENGINE_VERSION,
        "signal_only": True,
        "source_page_verification_required": True,
        "promotion_to_opportunity_allowed": False,
        "top5_eligible": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    })
    payload["metadata"] = adapted_metadata
    return payload, None


def build_france_case_memory_adapter(
    signals: Sequence[Mapping[str, Any]],
    *,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    register_france_follow_up_contract()
    now = _utc(observed_at)
    adapted: list[dict[str, Any]] = []
    rejections: dict[str, int] = {}
    for signal in signals:
        payload, reason = adapt_france_signal_to_entity_memory(signal)
        if payload is not None:
            adapted.append(payload)
            continue
        rejection = reason or "REJECTED"
        rejections[rejection] = rejections.get(rejection, 0) + 1

    stable = memory.dedupe_entity_signals(adapted)
    cases = memory.build_persistent_entity_cases(stable, observed_at=now)
    plan = memory.build_persistent_entity_follow_up_plan(cases, observed_at=now, max_cases=memory.MAX_CASES)
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


def ensure_france_memory_database(
    input_root: str | Path,
    *,
    config_path: str | Path = "alembic.ini",
) -> Path:
    register_france_follow_up_contract()
    path = Path(input_root) / FRANCE_MEMORY_RELATIVE_PATH
    database_url = f"sqlite:///{path.resolve().as_posix()}"
    upgrade_database(database_url, config_path=config_path)
    return path


def run_france_case_memory_cycle(
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
    register_france_follow_up_contract()
    now = _utc(observed_at)
    adapter = build_france_case_memory_adapter(current_signals, observed_at=now)
    ensure_france_memory_database(input_root, config_path=config_path)
    persistence = memory.persist_entity_scent_signals(adapter["entity_signals"], input_root=input_root)
    loaded, load_errors = memory.load_persisted_entity_scent_signals(input_root=input_root)
    france_loaded = [
        signal for signal in loaded
        if _compact(signal.get("source_country")).upper() == MARKET_CODE
    ]
    combined = memory.dedupe_entity_signals([*france_loaded, *adapter["entity_signals"]])
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
        "market_role": "OFFICIAL_EXPANSION_MARKET",
        "memory_database": (Path(input_root) / FRANCE_MEMORY_RELATIVE_PATH).as_posix(),
        "adapter": adapter,
        "persistence": {
            **persistence,
            "load_error_count": len(load_errors),
            "load_errors": load_errors,
            "loaded_france_entity_signal_count": len(france_loaded),
            "combined_france_entity_signal_count": len(combined),
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
