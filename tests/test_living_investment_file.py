from opportunity_engine.living_investment_file import (
    Confidence,
    Evidence,
    LivingInvestmentFile,
    LivingInvestmentFileRepository,
    OpportunityStatus,
    RevenuePath,
    RevenuePathType,
    SmallTest,
)


def build_complete_file() -> LivingInvestmentFile:
    item = LivingInvestmentFile.create(
        "Retail liquidation lot",
        source_url="https://example.test/listing/1",
        source_name="Example",
        asking_price_nok=10_000,
        summary="Mixed shop inventory that may be sold through several channels.",
    )
    evidence = Evidence.create(
        "The listing states that the lot contains retail fixtures and inventory.",
        source_url=item.source_url,
        confidence=Confidence.HIGH,
    )
    item.add_evidence(evidence)
    item.add_fact(
        "The lot contains both fixtures and saleable inventory.",
        evidence_ids=[evidence.evidence_id],
        confidence=Confidence.HIGH,
    )
    item.add_revenue_path(
        RevenuePath(
            path_id="brokerage",
            path_type=RevenuePathType.BROKERAGE,
            title="Broker the lot",
            description="Find specialist buyers and earn a commission without buying.",
            estimated_cost_nok=1_000,
            estimated_revenue_nok=8_000,
            first_step="Contact three specialist resellers.",
        )
    )
    item.add_revenue_path(
        RevenuePath(
            path_id="split",
            path_type=RevenuePathType.LOT_SPLIT,
            title="Split the lot",
            description="Acquire selected categories and resell separately.",
            estimated_cost_nok=12_000,
            estimated_revenue_nok=25_000,
            first_step="Request a detailed inventory list.",
        )
    )
    item.small_test = SmallTest(
        hypothesis="Specialist buyers will reserve items before purchase.",
        action="Show ten photographed items to five buyers.",
        max_cost_nok=500,
        success_metric="At least three written expressions of interest.",
        stop_condition="Stop if no buyer responds within seven days.",
    )
    item.select_best_path("brokerage", "Contact three specialist resellers")
    return item


def test_fact_requires_known_evidence() -> None:
    item = LivingInvestmentFile.create("Test opportunity")

    try:
        item.add_fact("Unsupported fact", evidence_ids=["ev_missing"])
    except ValueError as exc:
        assert "Unknown evidence ids" in str(exc)
    else:
        raise AssertionError("Unsupported fact was accepted")


def test_missing_price_remains_none_on_update() -> None:
    item = LivingInvestmentFile.create("Test opportunity", asking_price_nok=None)

    changed = item.merge_discovery_update({"summary": "New summary"})

    assert changed == ["summary"]
    assert item.asking_price_nok is None


def test_revenue_path_profit_is_not_invented_when_data_is_missing() -> None:
    path = RevenuePath(
        path_id="brokerage",
        path_type=RevenuePathType.BROKERAGE,
        title="Brokerage",
        description="Commission model",
        estimated_cost_nok=None,
        estimated_revenue_nok=5_000,
    )

    assert path.estimated_profit_nok is None


def test_complete_file_passes_v250_readiness() -> None:
    item = build_complete_file()

    assert item.readiness_gaps() == []
    assert item.is_v250_complete is True


def test_repository_round_trip_preserves_history(tmp_path) -> None:
    repository = LivingInvestmentFileRepository(tmp_path)
    original = build_complete_file()
    original.set_status(OpportunityStatus.RESEARCHING, "Research started")

    saved_path = repository.save(original)
    loaded = repository.load(original.opportunity_id)

    assert saved_path.exists()
    assert loaded.to_dict() == original.to_dict()
    assert loaded.status is OpportunityStatus.RESEARCHING
    assert loaded.update_history[-1].event_type == "status_changed"


def test_discovery_update_records_only_real_changes() -> None:
    item = LivingInvestmentFile.create("Original", location="Namsos")
    history_count = len(item.update_history)

    unchanged = item.merge_discovery_update({"location": "Namsos"})
    changed = item.merge_discovery_update({"location": "Trondheim"})

    assert unchanged == []
    assert changed == ["location"]
    assert len(item.update_history) == history_count + 1
