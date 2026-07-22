import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "collect_market_price_candidates.py"

spec = importlib.util.spec_from_file_location("collect_market_price_candidates", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_query_variants_include_independent_target_domains() -> None:
    item = {"title": "4 stk lagerreoler 200x60x200 cm svart"}
    queries = module._query_variants(item)

    assert len(queries) == 8
    assert queries[0].endswith("brukt pris Norge")
    assert any(query.startswith("site:finn.no ") for query in queries)
    assert any(query.startswith("site:auksjonen.no ") for query in queries)
    assert any(query.startswith("site:retrade.eu ") for query in queries)
    assert any(query.startswith("site:klaravik.no ") for query in queries)
    assert any(query.startswith("site:mascus.no ") for query in queries)


def test_similarity_ignores_site_operator() -> None:
    score = module._similarity(
        "site:finn.no lagerreoler svart kr",
        "Lagerreoler svart selges",
        "Brukte lagerreoler i god stand 4 990 kr",
    )
    assert score >= 0.5


def test_targeted_result_must_match_requested_domain() -> None:
    item = {"title": "lagerreoler svart"}
    result = {
        "title": "Lagerreoler svart",
        "snippet": "Selges for 4 990 kr",
        "url": "https://example.no/lagerreoler",
    }

    candidate, rejection = module._evaluate_candidate(
        item,
        result,
        "site:finn.no lagerreoler svart kr",
    )

    assert candidate is None
    assert rejection is not None
    assert "target_domain_mismatch" in rejection["rejection_reasons"]


def test_candidate_records_source_class_and_correct_price() -> None:
    item = {"title": "lagerreoler svart"}
    result = {
        "title": "Lagerreoler svart",
        "snippet": "Selges for 4,990 kr",
        "url": "https://www.finn.no/bap/forsale/ad.html?finnkode=123&utm_source=test",
    }

    candidate, rejection = module._evaluate_candidate(
        item,
        result,
        "site:finn.no lagerreoler svart kr",
    )

    assert rejection is None
    assert candidate is not None
    assert candidate["price_nok"] == 4990.0
    assert candidate["domain"] == "finn.no"
    assert candidate["source_class"] == "marketplace"
    assert "utm_source" not in candidate["canonical_url"]
