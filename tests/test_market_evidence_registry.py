from scripts.build_market_evidence_registry import _build_record, _remove_outliers


def _candidate(price: float, domain: str, quantity_status: str = "MATCHED") -> dict:
    return {
        "price_nok": price,
        "domain": domain,
        "quantity_status": quantity_status,
        "url": f"https://{domain}/{price}",
    }


def test_market_value_requires_three_comparables_and_two_domains() -> None:
    record = _build_record({
        "opportunity_id": "opp-1",
        "candidates": [
            _candidate(4000, "a.no"),
            _candidate(5000, "a.no"),
            _candidate(6000, "b.no"),
        ],
    })
    assert record["candidate_market_value_nok"] == 5000
    assert record["evidence_status"] == "REVIEW_REQUIRED"
    assert record["market_value_verified"] is False
    assert record["verified_market_value_nok"] is None


def test_single_domain_is_insufficient_even_with_three_prices() -> None:
    record = _build_record({
        "opportunity_id": "opp-2",
        "candidates": [
            _candidate(4000, "same.no"),
            _candidate(5000, "same.no"),
            _candidate(6000, "same.no"),
        ],
    })
    assert record["candidate_market_value_nok"] is None
    assert record["evidence_status"] == "INSUFFICIENT_EVIDENCE"
    assert "fewer_than_2_independent_domains" in record["review_reasons"]


def test_price_outlier_is_removed_before_market_value() -> None:
    accepted, rejected = _remove_outliers([
        _candidate(4800, "a.no"),
        _candidate(5000, "b.no"),
        _candidate(5200, "c.no"),
        _candidate(50000, "d.no"),
    ])
    assert [item["price_nok"] for item in accepted] == [4800, 5000, 5200]
    assert len(rejected) == 1
    assert rejected[0]["evidence_rejection_reason"] == "price_outlier"


def test_unknown_quantity_is_flagged_for_review() -> None:
    record = _build_record({
        "opportunity_id": "opp-3",
        "candidates": [
            _candidate(4000, "a.no", "UNKNOWN"),
            _candidate(5000, "b.no"),
            _candidate(6000, "c.no"),
        ],
    })
    assert record["candidate_market_value_nok"] == 5000
    assert "quantity_not_confirmed_for_all_comparables" in record["review_reasons"]
