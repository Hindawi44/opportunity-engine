from scripts.collect_market_price_candidates import _candidate, _extract_price, _similarity


def test_extract_price_supports_norwegian_formats() -> None:
    assert _extract_price("Pris 8 500 kr") == 8500.0
    assert _extract_price("NOK 12.500") == 12500.0
    assert _extract_price("ingen pris") is None


def test_similarity_requires_shared_product_terms() -> None:
    assert _similarity("lagerreol 200x60 brukt pris Norge", "Lagerreol brukt", "200x60 reol") >= 0.2
    assert _similarity("lagerreol 200x60", "Brudekjole", "silke størrelse 38") == 0.0


def test_candidate_is_unverified_and_keeps_observed_price() -> None:
    result = {
        "title": "Lagerreol 200x60 selges 8 500 kr",
        "snippet": "Brukt lagerreol i god stand",
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
    assert _candidate({}, result, "lagerreol 200x60 brukt pris Norge") is None
