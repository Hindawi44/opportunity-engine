from opportunity_engine.verified_financial_integration import integrate_verified_financial_evidence


def complete_payload():
    return {
        "market_comparables": [
            {"verified": True, "source": "A", "url": "https://a.no/1", "price_nok": 30000},
            {"verified": True, "source": "B", "url": "https://b.no/2", "price_nok": 32000},
            {"verified": True, "source": "C", "url": "https://c.no/3", "price_nok": 35000},
        ],
        "auction_price_nok": 10000,
        "auction_fee_nok": 1500,
        "vat_nok": 2875,
        "transport_cost_nok": 2200,
        "dismantling_cost_nok": 1200,
        "storage_cost_nok": 0,
    }


def test_complete_verified_evidence_opens_financial_review_gate():
    result = integrate_verified_financial_evidence("opp", complete_payload())
    assert result.verified_comparable_count == 3
    assert result.verified_cost_component_count == 6
    assert result.market_evidence_status == "COMPLETE"
    assert result.cost_evidence_status == "COMPLETE"
    assert result.true_acquisition_cost_nok == 17775.0
    assert result.conservative_resale_value_nok == 30000.0
    assert result.expected_profit_nok == 12225.0
    assert result.roi_percent == 68.78
    assert result.decision_gate == "READY_FOR_FINANCIAL_REVIEW"
    assert result.automatic_purchase_decision is False
    assert result.missing_required_evidence == ()


def test_missing_evidence_stays_null_and_blocks_gate():
    payload = complete_payload()
    payload.pop("transport_cost_nok")
    result = integrate_verified_financial_evidence("opp", payload)
    assert result.decision_gate == "EVIDENCE_REQUIRED"
    assert result.true_acquisition_cost_nok is None
    assert result.expected_profit_nok is None
    assert result.roi_percent is None
    assert "transport_cost_nok" in result.missing_required_evidence
    assert result.automatic_purchase_decision is False


def test_less_than_three_comparables_blocks_gate():
    payload = complete_payload()
    payload["market_comparables"] = payload["market_comparables"][:2]
    result = integrate_verified_financial_evidence("opp", payload)
    assert result.market_evidence_status == "INCOMPLETE"
    assert result.decision_gate == "EVIDENCE_REQUIRED"
    assert "three_verified_market_comparables" in result.missing_required_evidence
