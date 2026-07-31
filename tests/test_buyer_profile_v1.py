from copy import deepcopy
import json
from pathlib import Path

import pytest

from opportunity_engine.buyers import (
    BuyerProfileError,
    BuyerProfileV1,
    build_buyer_profile_snapshot,
)
from opportunity_engine.markets.profile import MarketProfileV1
from scripts.build_buyer_profile import main as build_buyer_profile_main


ROOT = Path(__file__).resolve().parents[1]
BUYER_PATH = ROOT / "config" / "buyers" / "mahmoud_namsos_v1.json"
MARKET_PATH = ROOT / "config" / "markets" / "no_v1.json"


def _buyer_payload() -> dict:
    return json.loads(BUYER_PATH.read_text(encoding="utf-8"))


def test_mahmoud_namsos_profile_matches_norway_market() -> None:
    buyer = BuyerProfileV1.from_path(BUYER_PATH)
    market = MarketProfileV1.from_path(MARKET_PATH)

    snapshot = build_buyer_profile_snapshot(buyer, market)

    assert snapshot["profile_id"] == "MAHMOUD_NAMSOS_V1"
    assert snapshot["buyer_type"] == "BUSINESS"
    assert snapshot["display_name"] == "Namsos Skredderhus"
    assert snapshot["location"]["country_code"] == "NO"
    assert snapshot["location"]["city"] == "Namsos"
    assert snapshot["settlement_currency"] == "NOK"
    assert snapshot["interests"]["categories"] == [
        "clothing_inventory",
        "textiles",
    ]
    assert snapshot["interests"]["markets"] == ["NO"]


def test_unknown_constraints_block_matching_without_inventing_values() -> None:
    buyer = BuyerProfileV1.from_path(BUYER_PATH)
    market = MarketProfileV1.from_path(MARKET_PATH)

    snapshot = build_buyer_profile_snapshot(buyer, market)

    assert snapshot["matching_readiness"] == {
        "ready": False,
        "status": "BLOCKED_MISSING_CONSTRAINTS",
        "missing_required_constraints": [
            "commercial_constraints.budget_nok",
            "commercial_constraints.maximum_shipping_nok",
            "commercial_constraints.minimum_expected_margin_ratio",
            "risk_policy.risk_tolerance",
        ],
    }
    assert snapshot["commercial_constraints"]["budget_nok"] is None
    assert snapshot["commercial_constraints"]["maximum_shipping_nok"] is None
    assert snapshot["commercial_constraints"]["minimum_expected_margin_ratio"] is None
    assert snapshot["risk_policy"]["risk_tolerance"] is None
    assert snapshot["location"]["postal_code"] is None
    assert snapshot["location"]["coordinates"] is None


def test_buyer_profile_keeps_automatic_actions_disabled() -> None:
    buyer = BuyerProfileV1.from_path(BUYER_PATH)
    market = MarketProfileV1.from_path(MARKET_PATH)

    snapshot = build_buyer_profile_snapshot(buyer, market)

    assert snapshot["safety"] == {
        "automatic_purchase_allowed": False,
        "automatic_bid_allowed": False,
        "automatic_contact_allowed": False,
    }
    assert snapshot["scope"] == {
        "landed_cost_calculation_enabled": False,
        "opportunity_ranking_enabled": False,
        "decision_changes_enabled": False,
    }


def test_buyer_profile_rejects_negative_or_invalid_constraints() -> None:
    payload = _buyer_payload()
    payload["commercial_constraints"]["budget_nok"] = -1
    with pytest.raises(BuyerProfileError, match="budget_nok must not be negative"):
        BuyerProfileV1.from_dict(payload)

    payload = _buyer_payload()
    payload["commercial_constraints"]["minimum_expected_margin_ratio"] = 1.2
    with pytest.raises(BuyerProfileError, match="must be between 0 and 1"):
        BuyerProfileV1.from_dict(payload)


def test_buyer_profile_rejects_automatic_purchase() -> None:
    payload = _buyer_payload()
    payload["safety"]["automatic_purchase_allowed"] = True

    with pytest.raises(
        BuyerProfileError,
        match="safety.automatic_purchase_allowed must be false",
    ):
        BuyerProfileV1.from_dict(payload)


def test_buyer_profile_rejects_market_identity_mismatch() -> None:
    buyer = BuyerProfileV1.from_path(BUYER_PATH)
    market = MarketProfileV1.from_path(MARKET_PATH)
    mismatched = deepcopy(market.to_dict())
    mismatched["currency_code"] = "EUR"
    other_market = MarketProfileV1.from_dict(mismatched)

    with pytest.raises(
        BuyerProfileError,
        match="settlement currency does not match home market",
    ):
        build_buyer_profile_snapshot(buyer, other_market)


def test_buyer_profile_cli_writes_auditable_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "buyer-profile.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_buyer_profile.py",
            "--buyer",
            str(BUYER_PATH),
            "--market",
            str(MARKET_PATH),
            "--output",
            str(output),
        ],
    )

    assert build_buyer_profile_main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    printed = json.loads(capsys.readouterr().out)

    assert payload["profile_id"] == "MAHMOUD_NAMSOS_V1"
    assert payload["matching_readiness"]["ready"] is False
    assert printed["matching_status"] == "BLOCKED_MISSING_CONSTRAINTS"
    assert printed["output"] == str(output)
