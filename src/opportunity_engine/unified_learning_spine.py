"""Canonical read-only evidence spine across markets and learning subsystems.

Unified Learning Spine V1 sits above the existing Unified Market Intelligence
River.  It does not rebuild collectors or replace their artifacts.  Instead it
normalises current in-domain market observations, verified search-success
routes and durable missed-opportunity cases into one stable evidence contract
that later memory/AI layers can consume without knowing every source schema.

The spine is deliberately read-only.  It never activates a query/provider,
promotes a source, mutates production, or performs a commercial action.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.project_domain_boundary import (
    CLOTHING_INVENTORY,
    FABRIC_PROCUREMENT,
    OUT_OF_DOMAIN,
    classify_project_domain,
)

SCHEMA_VERSION = "unified-learning-spine-1.0"
OUTPUT_FILENAME = "unified-learning-spine.json"
RIVER_ITEMS_FILENAME = "unified-intelligence-items.json"
DAILY_LEARNING_FILENAME = "daily-learning-cycle.json"
SEARCH_SUCCESS_RELATIVE_PATH = Path("learning/search-success-memory.json")
MISSED_OPPORTUNITIES_RELATIVE_PATH = Path("learning/missed-opportunities.json")

_ALLOWED_DOMAINS = {CLOTHING_INVENTORY, FABRIC_PROCUREMENT}
_ROUTE_SUCCESS_STATUSES = {"CANDIDATE", "REPLICATED_FOR_REVIEW"}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _upper(value: object) -> str:
    return _text(value).upper()


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item) for item in value if _text(item)]


def _hash_id(kind: str, identity: str) -> str:
    digest = sha256(f"{kind}|{identity}".encode("utf-8")).hexdigest()[:24]
    return f"learning-evidence:{digest}"


def _compact_json_text(value: object) -> str:
    if isinstance(value, Mapping):
        parts: list[str] = []
        for key in sorted(value):
            item = value[key]
            if isinstance(item, (str, int, float)) and not isinstance(item, bool):
                text = _text(item)
                if text:
                    parts.append(f"{key} {text}")
            elif isinstance(item, list):
                compact = " ".join(_text(entry) for entry in item if _text(entry))
                if compact:
                    parts.append(f"{key} {compact}")
        return " ".join(parts)
    return _text(value)


def _river_item_domain(item: Mapping[str, Any]) -> str:
    kind = _upper(item.get("record_kind"))
    details = _mapping(item.get("details"))
    metadata = _mapping(details.get("metadata"))

    if kind == "FABRIC_PROCUREMENT_ITEM":
        category = FABRIC_PROCUREMENT
    elif kind == "BRIDAL_LIQUIDATION_SIGNAL":
        category = "BRIDAL"
    else:
        category = (
            details.get("inventory_type")
            or details.get("inventory_focus")
            or details.get("catalog_scope")
            or ""
        )

    evidence_text = " ".join(
        _text(row.get("value"))
        for row in _rows(item.get("evidence"))
        if _text(row.get("value"))
    )
    combined = " ".join(
        part
        for part in (
            _text(item.get("title")),
            _text(item.get("source_name")),
            _text(item.get("company_name")),
            _text(item.get("seller_name")),
            _compact_json_text(details),
            evidence_text,
        )
        if part
    )
    return classify_project_domain(
        text=combined,
        category=category,
        industry_codes=_string_list(metadata.get("nace_codes")),
    )


def _search_route_domain(route: Mapping[str, Any]) -> str:
    return classify_project_domain(
        text=" ".join(
            part
            for part in (
                _text(route.get("query")),
                _text(route.get("parent_domain")),
                " ".join(_string_list(route.get("verified_exact_lot_urls"))),
            )
            if part
        )
    )


def _miss_domain(case: Mapping[str, Any]) -> str:
    return classify_project_domain(
        category=case.get("opportunity_type"),
        text=case.get("learning_evidence_text"),
    )


def _base_record(
    *,
    evidence_kind: str,
    identity: str,
    market_code: object,
    project_domain: str,
    source_name: object = None,
    provider: object = None,
    query: object = None,
    url: object = None,
    result_type: object = None,
    outcome: object = None,
    miss_reason: object = None,
    route: object = None,
    source_identity: object = None,
    observed_at: object = None,
    supporting_run_ids: object = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "learning_evidence_id": _hash_id(evidence_kind, identity),
        "evidence_kind": evidence_kind,
        "market_code": _upper(market_code),
        "project_domain": project_domain,
        "source_name": _text(source_name) or None,
        "provider": _text(provider).lower() or None,
        "query": _text(query) or None,
        "url": _text(url) or None,
        "result_type": _upper(result_type) or None,
        "outcome": _upper(outcome) or None,
        "miss_reason": _upper(miss_reason) or None,
        "route": _upper(route) or None,
        "source_identity": _text(source_identity) or None,
        "observed_at": _text(observed_at) or None,
        "supporting_run_ids": _string_list(supporting_run_ids),
        "metadata": dict(metadata or {}),
    }


def _market_observation_record(item: Mapping[str, Any], domain: str) -> dict[str, Any]:
    intelligence_id = _text(item.get("intelligence_id"))
    details = _mapping(item.get("details"))
    return _base_record(
        evidence_kind="MARKET_OBSERVATION",
        identity=intelligence_id or _text(item.get("source_url")) or _text(item.get("title")),
        market_code=item.get("source_country"),
        project_domain=domain,
        source_name=item.get("source_name"),
        url=item.get("source_url"),
        result_type=item.get("record_kind"),
        outcome=item.get("commercial_state") or item.get("lifecycle_status") or "OBSERVED",
        route=details.get("discovery_method") or details.get("sale_mode"),
        source_identity=intelligence_id,
        observed_at=item.get("latest_seen"),
        metadata={
            "title": _text(item.get("title")) or None,
            "commercial_state": _upper(item.get("commercial_state")) or None,
            "lifecycle_status": _upper(item.get("lifecycle_status")) or None,
            "score": item.get("score"),
            "source_artifacts": _string_list(item.get("source_artifacts")),
            "missing_information": _string_list(item.get("missing_information")),
            "input_observation_count": _int(item.get("input_observation_count")),
        },
    )


def _search_route_record(route: Mapping[str, Any], domain: str) -> dict[str, Any]:
    provider = _text(route.get("provider")).lower()
    market = _upper(route.get("market_code"))
    parent = _text(route.get("parent_domain") or route.get("result_domain"))
    pathway = _upper(route.get("pathway"))
    query = _text(route.get("query"))
    urls = _string_list(route.get("verified_exact_lot_urls") or route.get("exact_lot_urls"))
    identity = "|".join((provider, market, parent, pathway, query))
    return _base_record(
        evidence_kind="SEARCH_ROUTE_SUCCESS",
        identity=identity,
        market_code=market,
        project_domain=domain,
        source_name=parent,
        provider=provider,
        query=query,
        url=urls[0] if urls else None,
        result_type="SEARCH_ROUTE",
        outcome=route.get("status"),
        route=pathway,
        source_identity=parent,
        supporting_run_ids=route.get("supporting_run_ids"),
        metadata={
            "parent_domain": parent or None,
            "independent_run_count": _int(route.get("independent_run_count")),
            "verified_exact_lot_url_count": _int(route.get("verified_exact_lot_url_count"))
            or len(urls),
            "verified_exact_lot_urls": urls,
            "automatic_activation": route.get("automatic_activation") is True,
            "production_query_mutation": route.get("production_query_mutation") is True,
        },
    )


def _miss_record(case: Mapping[str, Any], domain: str) -> dict[str, Any]:
    case_id = _text(case.get("case_id"))
    truth = _mapping(case.get("ground_truth"))
    return _base_record(
        evidence_kind="MISSED_OPPORTUNITY",
        identity=case_id,
        market_code=case.get("market_code"),
        project_domain=domain,
        source_name=case.get("discovered_by"),
        url=truth.get("url"),
        result_type=case.get("opportunity_type"),
        outcome="MISSED",
        miss_reason=case.get("root_cause") or "UNDIAGNOSED",
        source_identity=case_id,
        observed_at=case.get("observed_at"),
        metadata={
            "ground_truth_company": _text(truth.get("company")) or None,
            "stock_proven": case.get("stock_proven") is True,
            "learning_status": _upper(case.get("learning_status")) or None,
            "repeat_miss": case.get("repeat_miss") is True,
            "diagnosed_query_gap_terms": _string_list(case.get("diagnosed_query_gap_terms")),
            "learned_patterns": _string_list(case.get("learned_patterns")),
        },
    )


def _record_sort_key(record: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        _upper(record.get("market_code")),
        _upper(record.get("evidence_kind")),
        _text(record.get("source_identity")),
        _text(record.get("learning_evidence_id")),
    )


def build_unified_learning_spine(
    *,
    unified_intelligence_items: Mapping[str, Any] | None,
    search_success_memory: Mapping[str, Any] | None,
    missed_opportunity_memory: Mapping[str, Any] | None,
    daily_learning: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build the common in-domain learning evidence contract."""
    river = _mapping(unified_intelligence_items)
    success = _mapping(search_success_memory)
    misses = _mapping(missed_opportunity_memory)
    daily = _mapping(daily_learning)

    records: list[dict[str, Any]] = []
    excluded_ids: list[str] = []

    for item in _rows(river.get("items")):
        domain = _river_item_domain(item)
        identity = _text(item.get("intelligence_id")) or _text(item.get("source_url"))
        if domain not in _ALLOWED_DOMAINS:
            if identity:
                excluded_ids.append(identity)
            continue
        records.append(_market_observation_record(item, domain))

    for route in _rows(success.get("route_learning")):
        status = _upper(route.get("status"))
        urls = _string_list(route.get("verified_exact_lot_urls") or route.get("exact_lot_urls"))
        verified_count = _int(route.get("verified_exact_lot_url_count")) or len(urls)
        if status not in _ROUTE_SUCCESS_STATUSES or verified_count <= 0:
            continue
        domain = _search_route_domain(route)
        identity = "route:" + "|".join(
            (
                _text(route.get("provider")),
                _upper(route.get("market_code")),
                _text(route.get("parent_domain") or route.get("result_domain")),
                _upper(route.get("pathway")),
            )
        )
        if domain not in _ALLOWED_DOMAINS:
            excluded_ids.append(identity)
            continue
        records.append(_search_route_record(route, domain))

    for case in _rows(misses.get("cases")):
        domain = _miss_domain(case)
        case_id = _text(case.get("case_id"))
        if domain not in _ALLOWED_DOMAINS:
            if case_id:
                excluded_ids.append(case_id)
            continue
        records.append(_miss_record(case, domain))

    # Stable de-duplication protects downstream memory from duplicate adapters.
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        by_id[record["learning_evidence_id"]] = record
    ordered_records = sorted(by_id.values(), key=_record_sort_key)

    market_counts = dict(
        sorted(Counter(_upper(row.get("market_code")) for row in ordered_records if _upper(row.get("market_code"))).items())
    )
    domain_counts = dict(
        sorted(Counter(_upper(row.get("project_domain")) for row in ordered_records).items())
    )
    kind_counts = dict(
        sorted(Counter(_upper(row.get("evidence_kind")) for row in ordered_records).items())
    )

    status = "SUCCESS" if ordered_records else "VALID_ZERO"
    generated_at = _text(daily.get("generated_at") or river.get("generated_at")) or None

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": generated_at,
        "input_presence": {
            "unified_intelligence_items": bool(river),
            "search_success_memory": bool(success),
            "missed_opportunity_memory": bool(misses),
            "daily_learning": bool(daily),
        },
        "evidence_record_count": len(ordered_records),
        "market_counts": market_counts,
        "domain_counts": domain_counts,
        "evidence_kind_counts": kind_counts,
        "out_of_domain_excluded_count": len(sorted(set(excluded_ids))),
        "out_of_domain_excluded_ids": sorted(set(excluded_ids)),
        "daily_learning_context": {
            "known_missed_opportunity_count": _int(daily.get("known_missed_opportunity_count")),
            "shadow_proven_term_count": _int(daily.get("shadow_proven_term_count")),
            "safe_learning_promotion_eligible_count": _int(
                daily.get("safe_learning_promotion_eligible_count")
            ),
            "out_of_domain_excluded_case_count": _int(
                daily.get("out_of_domain_excluded_case_count")
            ),
        },
        "records": ordered_records,
        "learning_contract": (
            "Source artifacts -> Unified Market Intelligence River -> Unified Learning Spine. "
            "The spine standardises evidence only; persistence/promotion remain separate explicit gates."
        ),
        "project_domain_gate_enforced": True,
        "automatic_query_activation": False,
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "automatic_code_change": False,
        "production_query_mutation": False,
        "production_mutation": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON artifact {path.as_posix()}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"artifact root must be an object: {path.as_posix()}")
    return dict(payload)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _attach_summary(output_dir: Path, spine: Mapping[str, Any]) -> None:
    brief_path = output_dir / "domain-market-intelligence-brief.json"
    if brief_path.exists():
        brief = _read_optional_json(brief_path)
        brief["unified_learning_spine"] = {
            "schema_version": spine.get("schema_version"),
            "status": spine.get("status"),
            "evidence_record_count": spine.get("evidence_record_count", 0),
            "market_counts": spine.get("market_counts", {}),
            "domain_counts": spine.get("domain_counts", {}),
            "evidence_kind_counts": spine.get("evidence_kind_counts", {}),
            "out_of_domain_excluded_count": spine.get("out_of_domain_excluded_count", 0),
            "output_file": OUTPUT_FILENAME,
            "project_domain_gate_enforced": True,
            "production_mutation": False,
        }
        _write_json(brief_path, brief)

    phone_path = output_dir / "multi-market-phone-summary.txt"
    if phone_path.exists():
        current = phone_path.read_text(encoding="utf-8")
        marker = "UNIFIED LEARNING SPINE:"
        if marker not in current:
            market_counts = _mapping(spine.get("market_counts"))
            markets = ", ".join(
                f"{market}={market_counts[market]}" for market in sorted(market_counts)
            ) or "NONE"
            with phone_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    "\nUNIFIED LEARNING SPINE:\n"
                    f"status: {spine.get('status')}\n"
                    f"evidence records: {spine.get('evidence_record_count', 0)}\n"
                    f"markets: {markets}\n"
                    f"out-of-domain excluded: {spine.get('out_of_domain_excluded_count', 0)}\n"
                    "production mutation: false\n"
                )


def write_unified_learning_spine(
    output_dir: str | Path,
    *,
    input_root: str | Path,
) -> dict[str, Any]:
    """Read current daily artifacts, write the spine and attach a compact summary."""
    output = Path(output_dir)
    root = Path(input_root)
    output.mkdir(parents=True, exist_ok=True)

    spine = build_unified_learning_spine(
        unified_intelligence_items=_read_optional_json(output / RIVER_ITEMS_FILENAME),
        search_success_memory=_read_optional_json(root / SEARCH_SUCCESS_RELATIVE_PATH),
        missed_opportunity_memory=_read_optional_json(root / MISSED_OPPORTUNITIES_RELATIVE_PATH),
        daily_learning=_read_optional_json(output / DAILY_LEARNING_FILENAME),
    )
    _write_json(output / OUTPUT_FILENAME, spine)
    _attach_summary(output, spine)
    return spine