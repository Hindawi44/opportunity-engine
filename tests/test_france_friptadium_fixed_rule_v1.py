"""Historical French route remains auditable but is no longer active after operator exclusion."""
from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.unified_memory_v2 import build_unified_memory_v2

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config/learning/unified-memory-rule-registry-v2.json"
FR_PATTERN_KEY = "ROUTE_SUCCESS|FR|CLOTHING_INVENTORY|exa|AGGREGATE_CHILD|friptadium.com"
FR_RULE_ID = "rule:fr-exa-friptadium-aggregate-child-v1"


def _record(evidence_id: str, *, market: str, source: str, outcome: str,
            provider: str | None = None, query: str | None = None,
            route: str | None = None, source_identity: str | None = None,
            result_type: str = "SEARCH_ROUTE", supporting_run_ids: list[str] | None = None,
            metadata: dict | None = None) -> dict:
    return {
        "learning_evidence_id": evidence_id, "evidence_kind": "SEARCH_ROUTE_SUCCESS",
        "market_code": market, "project_domain": "CLOTHING_INVENTORY",
        "source_name": source, "provider": provider, "query": query,
        "url": "https://friptadium.com/products/hauts-femme-au-kilo" if market == "FR" else "https://example.test/candidate",
        "result_type": result_type, "outcome": outcome, "miss_reason": None,
        "route": route, "source_identity": source_identity,
        "observed_at": "2026-08-23T21:10:00Z",
        "supporting_run_ids": supporting_run_ids or [], "metadata": metadata or {},
    }


def _spine(records: list[dict]) -> dict:
    return {
        "schema_version": "unified-learning-spine-1.0", "status": "SUCCESS",
        "generated_at": "2026-08-23T21:10:00Z", "evidence_record_count": len(records),
        "market_counts": {row["market_code"]: 1 for row in records},
        "domain_counts": {"CLOTHING_INVENTORY": len(records)},
        "evidence_kind_counts": {"SEARCH_ROUTE_SUCCESS": len(records)},
        "records": records, "project_domain_gate_enforced": True,
        "automatic_query_activation": False, "automatic_provider_activation": False,
        "automatic_source_promotion": False, "automatic_code_change": False,
        "production_query_mutation": False, "production_mutation": False,
        "automatic_contact": False, "automatic_bid": False,
        "automatic_reservation": False, "automatic_purchase": False,
        "automatic_payment": False,
    }


def test_historical_friptadium_rule_is_preserved_but_inactive() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    active = [row for row in registry["rules"] if row.get("status") == "ACTIVE"]
    historical = [row for row in registry["rules"] if row.get("rule_id") == FR_RULE_ID]
    assert active == []
    assert len(historical) == 1
    assert historical[0]["pattern_key"] == FR_PATTERN_KEY
    assert historical[0]["status"] == "OPERATOR_EXCLUDED"
    assert historical[0]["historical_status"] == "ACTIVE"
    assert historical[0]["deterministic_scope"]["source_identity"] == "friptadium.com"
    assert historical[0]["automatic_query_activation"] is False
    assert historical[0]["production_mutation"] is False


def test_proven_historical_france_route_is_not_promoted_to_active_rule() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    spine = _spine([
        _record(
            "fr-route", market="FR", source="friptadium.com", provider="exa",
            query="France lot vêtements prix quantité stock", outcome="REPLICATED_FOR_REVIEW",
            route="AGGREGATE_CHILD", source_identity="friptadium.com",
            supporting_run_ids=["32655969884", "32657298412", "32659936703", "32661201074", "32663784799"],
            metadata={"independent_run_count": 5},
        ),
        _record(
            "de-route", market="DE", source="example.de", provider="exa",
            query="Deutschland Bekleidung Restposten", outcome="CANDIDATE",
            route="DIRECT_ITEM", source_identity="example.de",
            supporting_run_ids=["32666511842"], metadata={"independent_run_count": 1},
        ),
    ])
    memory = build_unified_memory_v2(
        existing_memory=None, unified_learning_spine=spine,
        run_id="32666511842", rule_registry=registry,
    )
    france = next(row for row in memory["patterns"] if row["market_code"] == "FR")
    germany = next(row for row in memory["patterns"] if row["market_code"] == "DE")
    assert france["pattern_key"] == FR_PATTERN_KEY
    assert france["pattern_status"] == "PROVEN"  # historical evidence not erased
    assert france["converted_to_rule"] is False
    assert france.get("rule_id") in {None, ""}
    assert germany["pattern_status"] == "CANDIDATE"
    assert germany["converted_to_rule"] is False
    assert memory["fixed_rule_pattern_count"] == 0
    assert memory["automatic_query_activation"] is False
    assert memory["automatic_provider_activation"] is False
    assert memory["automatic_source_promotion"] is False
    assert memory["production_mutation"] is False
