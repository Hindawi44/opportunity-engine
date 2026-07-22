from scripts.collect_market_price_candidates import (
    _candidate,
    _evaluate_candidate,
    _extract_price,
    _extract_prices,
    _quantity,
    _similarity,
)


def test_extract_price_supports_norwegian_formats() -> None:
    assert _extract_price("Pris 8 500 kr") == 8500.0
    assert _extract_price("NOK 12.500") == 12500.0
    assert _extract_price("4,990kr Inkludert Mva") == 4990.0
    assert _extract_price("4.990 kr") == 4990.0
    assert _extract_price("4'990 NOK") == 4990.0
    assert _extract_price("ingen pris") is None


def test_extract_prices_keeps_all_observed_prices_without_truncation() -> None:
    assert _extract_prices("Før 5,990 kr, nå 4,990 kr") == [5990.0, 4990.0]


def test_similarity_requires_shared_product_terms() -> None:
    assert _similarity("lagerreol 200x60 brukt pris Norge", "Lagerreol brukt", "200x60 reol") >= 0.35
    assert _similarity("lagerreol 200x60", "Brudekjole", "silke størrelse 38") == 0.0


def test_quantity_extracts_explicit_norwegian_quantity() -> None:
    assert _quantity("4 stk komplette lagerreoler") == 4
    assert _quantity("pakke med 6 hyller") == 6
    assert _quantity("lagerreol") is None


def test_candidate_is_unverified_and_keeps_observed_price() -> None:
    result = {
        "title": "Lagerreol 200x60 selges 8 500 kr",
        "snippet": "Brukt lagerreol 200x60 i god stand",
        "url": "https://example.no/reol/1",
        "source": "Brave Search",
    }
    item = {"title": "Lagerreol 200x60"}
    candidate = _candidate(item, result, "lagerreol 200x60 brukt pris Norge")

    assert candidate is not None
    assert candidate["price_nok"] == 8500.0
    assert candidate["verified"] is False
    assert candidate["verification_status"] == "REVIEW_REQUIRED"


def test_candidate_rejects_irrelevant_result_even_with_price() -> None:
    result = {
        "title": "Brudekjole 5 000 kr",
        "snippet": "Silke og blonder",
        "url": "https://example.no/kjole/1",
    }
    candidate, rejection = _evaluate_candidate({}, result, "lagerreol 200x60 brukt pris Norge")
    assert candidate is None
    assert rejection is not None
    assert "similarity_below_0.35" in rejection["rejection_reasons"]


def test_candidate_rejects_explicit_quantity_mismatch() -> None:
    result = {
        "title": "1 stk lagerreol 200x60 4,990 kr",
        "snippet": "Brukt lagerreol 200x60",
        "url": "https://example.no/reol/1",
    }
    item = {"title": "4 stk komplette lagerreoler 200x60"}
    candidate, rejection = _evaluate_candidate(item, result, "4 stk lagerreoler 200x60 brukt pris Norge")
    assert candidate is None
    assert rejection is not None
    assert "quantity_mismatch" in rejection["rejection_reasons"]


def test_candidate_accepts_unknown_comparable_quantity_but_marks_it_unknown() -> None:
    result = {
        "title": "Lagerreol 200x60 4,990 kr",
        "snippet": "Stor brukt lagerreol 200x60",
        "url": "https://example.no/reol/2",
    }
    item = {"title": "4 stk komplette lagerreoler 200x60"}
    candidate = _candidate(item, result, "lagerreoler 200x60 brukt pris Norge")
    assert candidate is not None
    assert candidate["price_nok"] == 4990.0
    assert candidate["quantity_status"] == "UNKNOWN"
