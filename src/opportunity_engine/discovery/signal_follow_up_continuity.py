"""Cross-run, entity-first wrapper above SIGNAL_FOLLOW_UP_ENGINE_V1."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider
from opportunity_engine.discovery.signal_follow_up_engine import (
    DECISION_OWNER,
    DEFAULT_MAX_CASES,
    DEFAULT_RESULTS_PER_CASE,
    MAX_CASES,
    MAX_RESULTS_PER_CASE,
    OUTPUT_FILENAME,
    _attach_to_domain_brief,
    _canonical_url,
    _default_provider_factory,
    _normalise,
    _significant_tokens,
    run_signal_follow_up_engine,
)
from opportunity_engine.discovery.signal_follow_up_memory import (
    MEMORY_BACKEND,
    SCHEMA_VERSION,
    build_persistent_entity_cases,
    build_persistent_entity_follow_up_plan,
    dedupe_entity_signals,
    load_persisted_entity_scent_signals,
    persist_entity_scent_signals,
)

MEMORY_FILENAME = "signal-follow-up-memory.json"
PREVIOUS_SCENT_SEED_FILENAME = "previous-cross-source-scent-v2.json"
CURRENT_SCENT_REPORT = Path("cross-source-scent-v2/cross-source-scent-expansion-v2.json")
ProviderFactory = Callable[[str, str], SearchProvider]

_COMMERCIAL_TERMS = {
    "DE": ("warenbestand", "lagerbestand", "auktion", "versteigerung", "insolvenzauktion", "lagerverkauf", "lagerauflösung", "räumungsverkauf", "verwertung", "insolvenzverwalter", "masseverwertung", "warenposten", "posten", "verkauf"),
    "SE": ("varulager", "butikslager", "restlager", "auktion", "konkursauktion", "lagerförsäljning", "utförsäljning", "lagerrensning", "konkursförvaltare", "försäljning", "avveckling", "lagerparti", "auktionsobjekt"),
    "NO": ("varelager", "restlager", "auksjon", "konkursauksjon", "lagersalg", "opphørssalg", "avviklingssalg", "bostyrer", "realisasjon", "vareparti", "auksjonsobjekt", "salg"),
}
_AUCTION_TERMS = {
    "DE": ("auktion", "versteigerung", "insolvenzauktion"),
    "SE": ("auktion", "konkursauktion", "auktionsobjekt"),
    "NO": ("auksjon", "konkursauksjon", "auksjonsobjekt"),
}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _utc(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _matched(text: str, terms: Sequence[str]) -> list[str]:
    folded = text.casefold()
    return sorted({term for term in terms if term.casefold() in folded})


def _lead(hit: SearchHit, *, case: Mapping[str, Any], rank: int) -> dict[str, Any] | None:
    market = _compact(case.get("_follow_up_market")).upper()
    target = _compact(case.get("_follow_up_target"))
    source_url = _canonical_url(hit.url)
    if not source_url or market not in _COMMERCIAL_TERMS:
        return None
    existing = {_canonical_url(url) for url in case.get("source_urls") or []}
    if source_url in existing:
        return None
    title = _compact(hit.title)
    combined = f"{title} {_compact(hit.description)}".strip()
    commercial = _matched(combined, _COMMERCIAL_TERMS[market])
    if not commercial:
        return None
    target_tokens = _significant_tokens(target)
    normalized = _normalise(combined)
    matched_target = [token for token in target_tokens if token in normalized]
    if target_tokens and not matched_target:
        return None
    title_terms = _matched(title, _COMMERCIAL_TERMS[market])
    relevance = min(95, 55 + min(20, 5 * len(matched_target)) + min(20, 5 * len(title_terms)))
    kind = "AUCTION_OR_VERSTEIGERUNG_LEAD" if _matched(combined, _AUCTION_TERMS[market]) else "INVENTORY_OR_LIQUIDATION_SALE_LEAD"
    return {
        "lead_id": "follow-up-lead:" + sha256(f"{case.get('case_id')}|{source_url}".encode("utf-8")).hexdigest()[:24],
        "case_id": case.get("case_id"),
        "lead_kind": kind,
        "title": title,
        "source_url": source_url,
        "provider": _compact(hit.provider) or "Brave Search",
        "search_rank": rank,
        "matched_target_tokens": matched_target,
        "matched_commercial_terms": commercial,
        "follow_up_relevance_score": relevance,
        "verification_status": "UNVERIFIED_PUBLIC_WEB_SEARCH_HIT",
        "source_page_verification_required": True,
        "commercial_facts_confirmed": False,
        "promotion_to_opportunity_allowed": False,
        "decision_owner": DECISION_OWNER,
    }


def _run_memory_plan(
    plan: Sequence[Mapping[str, Any]], *, environment: Mapping[str, str], provider_factory: ProviderFactory | None, results_per_case: int
) -> dict[str, Any]:
    api_key = _compact(environment.get("BRAVE_SEARCH_API_KEY"))
    factory = provider_factory or _default_provider_factory
    limit = max(1, min(MAX_RESULTS_PER_CASE, int(results_per_case)))
    rows: list[dict[str, Any]] = []
    searched = errors = lead_count = linked_count = 0
    for raw in plan:
        item = dict(raw)
        source_case = item.pop("_source_case")
        links = list(item.get("explicit_linked_commercial_case_ids") or [])
        linked_count += int(bool(links))
        row = {**item, "leads": [], "search_status": "PLANNED"}
        if not api_key:
            row["search_status"] = "SKIPPED_NO_API_KEY"
        else:
            try:
                provider = factory(_compact(item.get("country")).upper(), api_key)
                hits = provider.search(_compact(item.get("query")), count=limit)
                searched += 1
                seen: set[str] = set()
                leads: list[dict[str, Any]] = []
                for rank, hit in enumerate(hits, start=1):
                    lead = _lead(hit, case=source_case, rank=rank)
                    if lead is None or str(lead["source_url"]) in seen:
                        continue
                    seen.add(str(lead["source_url"]))
                    leads.append(lead)
                leads.sort(key=lambda x: (-int(x.get("follow_up_relevance_score") or 0), int(x.get("search_rank") or 999), _compact(x.get("source_url"))))
                row["leads"] = leads[:limit]
                lead_count += len(row["leads"])
                row["search_status"] = "SUCCESS"
            except Exception as exc:
                errors += 1
                row.update({"search_status": "FAILED", "error_type": type(exc).__name__, "error": _compact(exc)[:500]})
        row["follow_up_state"] = "EXPLICIT_COMMERCIAL_CASE_LINK_EXISTS" if links else ("COMMERCIAL_LEAD_REQUIRES_SOURCE_VERIFICATION" if row["leads"] else "MONITORING")
        row.update({"search_hit_is_not_commercial_proof": True, "promotion_to_opportunity_allowed": False, "automatic_contact": False, "automatic_bid": False, "automatic_purchase": False, "automatic_payment": False})
        rows.append(row)
    return {"cases": rows, "search_request_count": searched, "search_error_count": errors, "commercial_lead_count": lead_count, "explicit_commercial_case_link_count": linked_count}


def _same_entity(case: Mapping[str, Any], memory: Mapping[str, Any]) -> bool:
    countries = case.get("countries")
    memory_countries = memory.get("countries")
    if not isinstance(countries, Sequence) or isinstance(countries, (str, bytes)) or not countries:
        return False
    if not isinstance(memory_countries, Sequence) or isinstance(memory_countries, (str, bytes)) or not memory_countries:
        return False
    if _compact(countries[0]).upper() != _compact(memory_countries[0]).upper():
        return False
    title = _normalise(case.get("case_title"))
    tokens = _significant_tokens(memory.get("entity_label"))
    return bool(tokens) and all(token in title for token in tokens)


def _filtered_report(report: Mapping[str, Any], memory_cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    payload = dict(report)
    payload["cases"] = [dict(case) for case in report.get("cases") or [] if isinstance(case, Mapping) and not any(_same_entity(case, memory) for memory in memory_cases)]
    return payload


def _top_lead(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    leads = [dict(lead) for row in rows for lead in row.get("leads") or [] if isinstance(lead, Mapping)]
    if not leads:
        return None
    leads.sort(key=lambda x: (-int(x.get("follow_up_relevance_score") or 0), _compact(x.get("source_url"))))
    return leads[0]


def run_signal_follow_up_engine_with_continuity(
    cases_report: Mapping[str, Any], *, entity_signals: Sequence[Mapping[str, Any]], environment: Mapping[str, str] | None = None, provider_factory: ProviderFactory | None = None, observed_at: datetime | None = None, max_cases: int = DEFAULT_MAX_CASES, results_per_case: int = DEFAULT_RESULTS_PER_CASE
) -> dict[str, Any]:
    env = environment if environment is not None else os.environ
    now = _utc(observed_at)
    bounded = max(0, min(MAX_CASES, int(max_cases)))
    current_cases = [dict(item) for item in cases_report.get("cases") or [] if isinstance(item, Mapping)]
    memory_cases = build_persistent_entity_cases(entity_signals, observed_at=now)
    selected_memory = memory_cases[:bounded]
    memory_plan = build_persistent_entity_follow_up_plan(selected_memory, all_current_cases=current_cases, observed_at=now, max_cases=bounded)
    memory_result = _run_memory_plan(memory_plan, environment=env, provider_factory=provider_factory, results_per_case=results_per_case)
    remaining = max(0, bounded - len(memory_plan))
    fallback = run_signal_follow_up_engine(_filtered_report(cases_report, selected_memory), environment=env, provider_factory=provider_factory, observed_at=now, max_cases=remaining, results_per_case=results_per_case)
    rows = list(memory_result["cases"]) + list(fallback.get("cases") or [])
    searched = int(memory_result["search_request_count"]) + int(fallback.get("search_request_count") or 0)
    errors = int(memory_result["search_error_count"]) + int(fallback.get("search_error_count") or 0)
    lead_count = int(memory_result["commercial_lead_count"]) + int(fallback.get("commercial_lead_count") or 0)
    link_count = int(memory_result["explicit_commercial_case_link_count"]) + int(fallback.get("explicit_commercial_case_link_count") or 0)
    api_key = _compact(env.get("BRAVE_SEARCH_API_KEY"))
    status = "VALID_ZERO_NO_FOLLOW_UP_CASES" if not rows else ("SKIPPED_NO_API_KEY" if not api_key else ("PARTIAL_SUCCESS" if errors and searched else ("FAILED" if errors else "SUCCESS")))
    return {
        "schema_version": fallback.get("schema_version") or "signal-follow-up-engine-1.0",
        "continuity_schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "status": status,
        "purpose": "FOLLOW_EARLY_SIGNAL_ACROSS_RUNS_UNTIL_SOURCE_VERIFIABLE_COMMERCIAL_EVIDENCE_APPEARS",
        "memory_backend": MEMORY_BACKEND,
        "persistent_entity_case_count": len(memory_cases),
        "persistent_entity_selected_count": len(memory_plan),
        "persistent_entity_signal_count": len(dedupe_entity_signals(entity_signals)),
        "eligible_follow_up_case_count": len(memory_cases) + int(fallback.get("eligible_follow_up_case_count") or 0),
        "selected_case_count": len(rows),
        "search_request_count": searched,
        "search_error_count": errors,
        "commercial_lead_count": lead_count,
        "explicit_commercial_case_link_count": link_count,
        "top_follow_up_lead": _top_lead(rows),
        "cases": rows,
        "search_result_is_not_commercial_proof": True,
        "source_page_verification_required": True,
        "promotion_to_opportunity_allowed": False,
        "decision_owner": DECISION_OWNER,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _memory_snapshot(signals: Sequence[Mapping[str, Any]], observed_at: datetime) -> dict[str, Any]:
    cases = build_persistent_entity_cases(signals, observed_at=observed_at)
    plan = build_persistent_entity_follow_up_plan(cases, observed_at=observed_at, max_cases=MAX_CASES)
    by_id = {row.get("case_id"): row for row in plan}
    rows = []
    for case in cases:
        current = by_id.get(case.get("case_id"), {})
        rows.append({"case_id": case.get("case_id"), "country": (case.get("countries") or [None])[0], "entity_key": case.get("entity_key"), "entity_label": case.get("entity_label"), "first_seen": case.get("first_seen"), "last_seen": case.get("last_seen"), "source_signal_count": case.get("entity_source_signal_count"), "current_stage_index": current.get("follow_up_stage_index"), "current_stage": current.get("follow_up_stage"), "current_query": current.get("query")})
    return {"schema_version": SCHEMA_VERSION, "generated_at": observed_at.isoformat(), "memory_backend": MEMORY_BACKEND, "persistent_entity_case_count": len(rows), "cases": rows, "promotion_to_opportunity_allowed": False, "decision_owner": DECISION_OWNER}


def write_signal_follow_up_engine_with_continuity(
    output_dir: str | Path, *, environment: Mapping[str, str] | None = None, provider_factory: ProviderFactory | None = None, observed_at: datetime | None = None, max_cases: int = DEFAULT_MAX_CASES, results_per_case: int = DEFAULT_RESULTS_PER_CASE
) -> dict[str, Any]:
    directory = Path(output_dir)
    env = environment if environment is not None else os.environ
    now = _utc(observed_at)
    cases_report = _read_json(directory / "unified-market-cases.json") or {"cases": []}
    reports = [_read_json(directory / CURRENT_SCENT_REPORT), _read_json(directory / PREVIOUS_SCENT_SEED_FILENAME)]
    current_signals = dedupe_entity_signals([dict(signal) for report in reports if isinstance(report, Mapping) for signal in report.get("signals") or [] if isinstance(signal, Mapping)])
    input_root = Path(_compact(env.get("INPUT_ROOT")) or (directory.parent / "multi-market-inputs").as_posix())
    persistence = persist_entity_scent_signals(current_signals, input_root=input_root)
    persisted, load_errors = load_persisted_entity_scent_signals(input_root=input_root)
    combined = dedupe_entity_signals([*persisted, *current_signals])
    report = run_signal_follow_up_engine_with_continuity(cases_report, entity_signals=combined, environment=env, provider_factory=provider_factory, observed_at=now, max_cases=max_cases, results_per_case=results_per_case)
    report["continuity_persistence"] = {**persistence, "load_error_count": len(load_errors), "load_errors": load_errors, "persisted_entity_signal_count_loaded": len(persisted), "combined_entity_signal_count": len(combined), "previous_cross_source_seed_used": (directory / PREVIOUS_SCENT_SEED_FILENAME).exists(), "current_cross_source_report_used": (directory / CURRENT_SCENT_REPORT).exists()}
    _write_json(directory / OUTPUT_FILENAME, report)
    _write_json(directory / MEMORY_FILENAME, _memory_snapshot(combined, now))
    _attach_to_domain_brief(directory, report)
    return report
