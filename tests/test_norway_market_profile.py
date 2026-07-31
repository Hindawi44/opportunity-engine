from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from opportunity_engine.markets.norway import (
    build_norway_market_profile_snapshot,
    load_norway_market_profile,
)
from opportunity_engine.markets.profile import (
    MarketProfileError,
    MarketProfileV1,
    build_market_profile_snapshot,
    load_json_object,
)
from scripts.build_norway_market_profile import main as build_profile_main


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "config/markets/no_v1.json"
PLAN_PATH = ROOT / "config/source_expansion_plan.json"
GAP_PATH = ROOT / "data/source_gap_matrix.json"


def test_norway_profile_defines_stable_market_identity_without_calculators() -> None:
    profile = load_norway_market_profile(ROOT)

    assert profile.profile_id == "NO_DOMESTIC_V1"
    assert profile.market_code == "NO"
    assert profile.market_name == "Norway"
    assert profile.currency_code == "NOK"
    assert profile.language_codes == ("nb", "nn")
    assert profile.fallback_language_codes == ("en",)
    assert profile.transaction_scope == "DOMESTIC"
    assert profile.tax_policy["calculation_enabled"] is False
    assert profile.customs_policy["calculation_enabled"] is False
    assert profile.logistics_policy["calculation_enabled"] is False
    assert profile.customs_policy["cross_border_import_supported"] is False
    assert profile.qualification_policy["automatic_purchase_allowed"] is False


def test_real_norway_source_registries_resolve_without_duplicate_truth() -> None:
    snapshot = build_norway_market_profile_snapshot(ROOT)
    source_snapshot = snapshot["source_registry_snapshot"]
    sources = source_snapshot["sources"]

    plan = load_json_object(PLAN_PATH)
    norway_plan = next(
        market for market in plan["markets"] if market["market"] == "Norway"
    )
    expected_names = {row["source"] for row in norway_plan["sources"]}

    assert source_snapshot["source_count"] == len(expected_names)
    assert {row["source"] for row in sources} == expected_names
    assert sum(source_snapshot["status_counts"].values()) == len(sources)
    assert all(row["runtime_status"] for row in sources)
    assert all(row["qualification_mode"] for row in sources)


def test_signal_channels_are_kept_out_of_direct_sale_qualification() -> None:
    snapshot = build_norway_market_profile_snapshot(ROOT)
    by_name = {
        row["source"]: row
        for row in snapshot["source_registry_snapshot"]["sources"]
    }

    assert by_name["Konkurs.app"]["channel"] == "bankruptcy_lead"
    assert by_name["Konkurs.app"]["qualification_mode"] == "SIGNAL_ONLY"
    assert by_name["Politiet.no"]["channel"] == "public_auction_event_lead"
    assert by_name["Politiet.no"]["qualification_mode"] == "SIGNAL_ONLY"
    assert by_name["Auksjonen.no"]["qualification_mode"] == "REQUIRES_RECORD_VERIFICATION"


def test_profile_preserves_conservative_failure_and_unknown_cost_rules() -> None:
    snapshot = build_norway_market_profile_snapshot(ROOT)

    assert snapshot["risk_policy"]["source_failure_is_not_zero_opportunities"] is True
    assert snapshot["risk_policy"]["unknown_costs_block_qualification"] is True
    assert snapshot["source_registry"]["qualification_requires_verified_sale_listing"] is True
    assert snapshot["qualification_policy"]["listing_status_required"] == "ACTIVE"
    assert snapshot["qualification_policy"]["verification_status_required"] == "VERIFIED"
    assert snapshot["safety"] == {
        "calculates_tax": False,
        "calculates_customs": False,
        "calculates_logistics": False,
        "changes_final_decision": False,
        "automatic_purchase": False,
    }


def test_source_registry_drift_fails_instead_of_hiding_a_source() -> None:
    profile = MarketProfileV1.from_path(PROFILE_PATH)
    plan = load_json_object(PLAN_PATH)
    gap = deepcopy(load_json_object(GAP_PATH))
    gap["sources"] = [
        row
        for row in gap["sources"]
        if not (row.get("market") == "Norway" and row.get("source") == "Auksjonen.no")
    ]

    with pytest.raises(MarketProfileError, match="source registry drift"):
        build_market_profile_snapshot(profile, plan, gap)


def test_profile_rejects_embedded_mutable_tax_rates() -> None:
    payload = load_json_object(PROFILE_PATH)
    payload["tax_policy"]["vat_rate"] = 0.25

    with pytest.raises(MarketProfileError, match="reference rules rather than embed mutable rates"):
        MarketProfileV1.from_dict(payload)


def test_cli_writes_a_valid_detached_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "norway-market-profile.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_norway_market_profile.py",
            "--root",
            str(ROOT),
            "--output",
            str(output),
        ],
    )

    assert build_profile_main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["profile_id"] == "NO_DOMESTIC_V1"
    assert payload["market_code"] == "NO"
    assert payload["source_registry_snapshot"]["source_count"] > 0
    assert payload["safety"]["automatic_purchase"] is False
