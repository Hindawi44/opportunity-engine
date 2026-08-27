import json
from pathlib import Path

from opportunity_engine.search_maturity_route_evidence_gate_v1 import evaluate_search_maturity


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _core_clothing(input_root: Path) -> None:
    counts = {"NO": 5, "SE": 3, "DE": 34}
    for market, count in counts.items():
        _write(
            input_root / f"{market.lower()}-exa-exact-lot" / "search-run-report.json",
            {
                "status": "SUCCESS",
                "execution_status": "PASS",
                "domain": "CLOTHING_INVENTORY",
                "market_code": market,
                "source_mode": "EXA_EXACT_LOT_MULTIHOP",
                "strict_exact_lot_count": count,
                "automatic_contact": False,
                "automatic_bid": False,
                "automatic_purchase": False,
                "automatic_payment": False,
            },
        )


def _expansion_clothing(output_dir: Path) -> None:
    _write(
        output_dir / "unified-six-market-exa-runtime.json",
        {
            "status": "SUCCESS",
            "project_domain": "CLOTHING_INVENTORY",
            "production_mutation": False,
            "automatic_query_activation": False,
            "automatic_provider_activation": False,
            "automatic_source_promotion": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_reservation": False,
            "automatic_purchase": False,
            "automatic_payment": False,
            "search_requests_added_by_route_continuity": 0,
            "markets": {
                "FR": {"status": "SUCCESS", "strict_exact_lot_count": 11},
                "IT": {"status": "SUCCESS", "strict_exact_lot_count": 20},
                "NL": {"status": "SUCCESS", "strict_exact_lot_count": 5},
            },
        },
    )


def _fabric_report(markets: list[str], *, molton_primary: bool = False) -> dict:
    rows = []
    candidates = []
    for market in markets:
        rows.append(
            {
                "market_code": market,
                "status": "SUCCESS",
                "accepted_candidate_count": 1,
            }
        )
    is_core_cohort = set(markets) == {"NO", "SE", "DE"}
    pair_market = markets[0]
    candidates.append(
        {
            "source_country": pair_market,
            "source_name": "example-fabric.test",
            "source_url": f"https://example-fabric.test/{pair_market.lower()}",
            "price": None if is_core_cohort else 6.5,
            "price_text": None if is_core_cohort else "€ 6.50",
            "quantity": None if is_core_cohort else 6.0,
            "quantity_unit": None if is_core_cohort else "meter",
            "commercial_evidence_complete": not is_core_cohort,
            "commercial_evidence_normalized": not is_core_cohort,
            "commercial_evidence_pairing_mode": None if is_core_cohort else "CONTEXTUAL_PRICE_QUANTITY_PAIR",
        }
    )
    if "DE" in markets:
        candidates.append(
            {
                "source_country": "DE",
                "source_name": "molton-markt.de",
                "source_url": "https://www.molton-markt.de/molton/dekomolton-30lfm.html",
                "title": "Dekomolton GREENLINE Stoffballen schwarz 300 cm, 30 lfm",
                "price": 319.0 if molton_primary else 0.34,
                "price_text": "319,00 €" if molton_primary else "0,34 €",
                "quantity": 30.0 if molton_primary else 25.0,
                "quantity_unit": "lfm",
                "commercial_evidence_complete": True,
                "commercial_evidence_normalized": True,
                "commercial_evidence_pairing_mode": "INDEPENDENT_SINGLE_EVIDENCE",
            }
        )
    return {
        "status": "SUCCESS",
        "project_domain": "FABRIC_PROCUREMENT",
        "scheduled_market_coverage": markets,
        "market_coverage": markets,
        "query_budget_total": 3,
        "requests_made": 3,
        "site_pinning_used": False,
        "legacy_search_requests_made": 0,
        "search_requests_added_by_coverage_rotation": 0,
        "new_runtime_added": False,
        "new_provider_added": False,
        "new_source_added": False,
        "country_specific_search_paths_added": False,
        "production_mutation": False,
        "automatic_query_activation": False,
        "automatic_provider_activation": False,
        "automatic_source_promotion": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
        "candidates": candidates,
        "exa_market_search": {
            "provider": "exa",
            "project_domain": "FABRIC_PROCUREMENT",
            "market_coverage": markets,
            "query_budget_total": 3,
            "requests_made": 3,
            "search_requests_added_by_coverage_rotation": 0,
            "new_runtime_added": False,
            "new_provider_added": False,
            "new_source_added": False,
            "country_specific_search_paths_added": False,
            "production_mutation": False,
            "automatic_query_activation": False,
            "automatic_provider_activation": False,
            "automatic_source_promotion": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_reservation": False,
            "automatic_purchase": False,
            "automatic_payment": False,
            "markets": rows,
        },
    }


def test_gate_declares_mature_only_from_existing_six_market_evidence(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    output_dir = tmp_path / "output"
    prior = tmp_path / "prior-fabric.json"
    _core_clothing(input_root)
    _expansion_clothing(output_dir)
    _write(prior, _fabric_report(["FR", "IT", "NL"]))
    _write(output_dir / "fabric-procurement-watch.json", _fabric_report(["NO", "SE", "DE"], molton_primary=True))

    result = evaluate_search_maturity(
        input_root=input_root,
        output_dir=output_dir,
        prior_fabric_reports=[prior],
    )

    assert result["decision"] == "MATURE"
    assert result["search_engine_v1_mature"] is True
    assert result["blocking_reasons"] == []
    assert result["fabric"]["covered_markets"] == ["DE", "FR", "IT", "NL", "NO", "SE"]
    core_report = next(report for report in result["fabric"]["reports"] if set(report["coverage"]) == {"NO", "SE", "DE"})
    assert core_report["contextual_pair_markets"] == []
    assert core_report["complete_price_quantity_markets"] == ["DE"]
    molton = result["fabric"]["molton_primary_product_proof"]
    assert molton["status"] == "PROVEN"
    assert molton["observed"][0]["pairing_mode"] == "INDEPENDENT_SINGLE_EVIDENCE"
    assert molton["observed"][0]["primary_roll_evidence"] is True
    assert result["gate_search_requests_made"] == 0
    assert result["gate_page_fetches_made"] == 0
    assert result["new_runtime_added"] is False
    assert result["site_pinning_added"] is False
    assert result["exact_lot_relaxed"] is False


def test_gate_blocks_molton_cross_sell_accessory_pair(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    output_dir = tmp_path / "output"
    prior = tmp_path / "prior-fabric.json"
    _core_clothing(input_root)
    _expansion_clothing(output_dir)
    _write(prior, _fabric_report(["FR", "IT", "NL"]))
    _write(output_dir / "fabric-procurement-watch.json", _fabric_report(["NO", "SE", "DE"], molton_primary=False))

    result = evaluate_search_maturity(
        input_root=input_root,
        output_dir=output_dir,
        prior_fabric_reports=[prior],
    )

    assert result["decision"] == "BLOCKED"
    assert "MOLTON_PRIMARY_PRODUCT_EVIDENCE_NOT_PROVEN" in result["blocking_reasons"]
    assert result["fabric"]["molton_primary_product_proof"]["observed"][0]["primary_roll_evidence"] is False


def test_gate_requires_both_fixed_fabric_cohorts(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    output_dir = tmp_path / "output"
    _core_clothing(input_root)
    _expansion_clothing(output_dir)
    _write(output_dir / "fabric-procurement-watch.json", _fabric_report(["NO", "SE", "DE"], molton_primary=True))

    result = evaluate_search_maturity(input_root=input_root, output_dir=output_dir)

    assert result["decision"] == "BLOCKED"
    assert "FABRIC_SIX_MARKET_COVERAGE_NOT_PROVEN" in result["blocking_reasons"]
    assert "FABRIC_BOTH_FIXED_COHORTS_NOT_PROVEN" in result["blocking_reasons"]


def test_gate_has_no_search_or_fetch_dependency() -> None:
    source = Path("src/opportunity_engine/search_maturity_route_evidence_gate_v1.py").read_text(encoding="utf-8")
    forbidden = (
        "ExaSearchProvider",
        "fetch_public_page",
        "requests.get",
        "urllib.request",
        "httpx",
    )
    for token in forbidden:
        assert token not in source
