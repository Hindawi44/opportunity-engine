from opportunity_engine.living_investment_file import (
    Evidence,
    LivingInvestmentFile,
    RevenuePath,
    RevenuePathType,
)
from opportunity_engine.scenario_generator import ScenarioGeneratorEngine, ScenarioInputs


def test_generates_six_paths_without_inventing_missing_financial_values():
    item = LivingInvestmentFile.create(
        "Liquidation stock",
        asking_price_nok=None,
        source_url="https://example.com/listing",
    )

    result = ScenarioGeneratorEngine().generate(item)

    assert len(result.generated_path_ids) == 6
    assert len(item.revenue_paths) == 6
    purchase = next(path for path in item.revenue_paths if path.path_id.endswith("purchase"))
    assert purchase.estimated_cost_nok is None
    assert purchase.estimated_revenue_nok is None
    assert purchase.estimated_profit_nok is None
    assert result.best_path_id is None
    assert any("verified purchase price" in question.lower() for question in result.missing_questions_added)


def test_calculates_only_from_explicit_inputs_and_selects_viable_path():
    item = LivingInvestmentFile.create("Office inventory", asking_price_nok=100_000)
    inputs = ScenarioInputs(
        purchase_price_nok=100_000,
        auction_fees_nok=5_000,
        transport_cost_nok=10_000,
        storage_cost_nok=5_000,
        repair_cost_nok=0,
        conservative_resale_value_nok=160_000,
        brokerage_commission_rate=0.10,
        liquidation_commission_rate=0.15,
        partner_funding_share=0.50,
        lot_purchase_fraction=0.25,
        presale_committed_revenue_nok=20_000,
        expected_duration_days=60,
    )

    result = ScenarioGeneratorEngine().generate(item, inputs)

    purchase = next(path for path in item.revenue_paths if path.path_id.endswith("purchase"))
    brokerage = next(path for path in item.revenue_paths if path.path_id.endswith("brokerage"))
    partnership = next(path for path in item.revenue_paths if path.path_id.endswith("partnership"))
    split = next(path for path in item.revenue_paths if path.path_id.endswith("lot-split"))

    assert purchase.estimated_cost_nok == 120_000
    assert purchase.estimated_profit_nok == 40_000
    assert brokerage.estimated_revenue_nok == 16_000
    assert partnership.estimated_cost_nok == 60_000
    assert split.estimated_cost_nok == 25_000
    assert split.estimated_revenue_nok == 40_000
    assert result.best_path_id == purchase.path_id
    assert item.next_action


def test_regeneration_replaces_generated_paths_but_preserves_manual_path():
    item = LivingInvestmentFile.create("Mixed stock", asking_price_nok=50_000)
    engine = ScenarioGeneratorEngine()
    engine.generate(item)

    item.add_revenue_path(
        RevenuePath(
            path_id="manual-custom-path",
            path_type=RevenuePathType.OTHER,
            title="Manual specialist path",
            description="A manually researched option that must survive regeneration.",
        )
    )

    engine.generate(item)

    generated = [path for path in item.revenue_paths if path.path_id.startswith(engine.GENERATED_PREFIX)]
    manual_paths = [path for path in item.revenue_paths if path.path_id == "manual-custom-path"]
    assert len(generated) == 6
    assert len(manual_paths) == 1


def test_does_not_duplicate_missing_questions_on_regeneration():
    item = LivingInvestmentFile.create("Unknown lot")
    engine = ScenarioGeneratorEngine()

    engine.generate(item)
    first_count = len(item.missing_information)
    engine.generate(item)

    assert len(item.missing_information) == first_count


def test_rejects_unknown_evidence_ids():
    item = LivingInvestmentFile.create("Verified lot")

    try:
        ScenarioGeneratorEngine().generate(item, evidence_ids=["ev_missing"])
    except ValueError as exc:
        assert "Unknown evidence ids" in str(exc)
    else:
        raise AssertionError("Expected unknown evidence ids to fail")


def test_attaches_known_evidence_to_every_generated_path():
    item = LivingInvestmentFile.create("Verified lot")
    evidence = Evidence.create("Seller confirmed item-level inventory")
    item.add_evidence(evidence)

    ScenarioGeneratorEngine().generate(item, evidence_ids=[evidence.evidence_id])

    assert all(path.evidence_ids == [evidence.evidence_id] for path in item.revenue_paths)


def test_validates_rates_and_negative_values():
    for kwargs in (
        {"purchase_price_nok": -1},
        {"brokerage_commission_rate": 1.1},
        {"partner_funding_share": -0.1},
        {"expected_duration_days": 0},
    ):
        try:
            ScenarioInputs(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected invalid inputs to fail: {kwargs}")
