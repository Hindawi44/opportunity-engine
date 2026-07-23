from opportunity_engine.evidence_collector import ExistingSourceEvidenceCollector
from opportunity_engine.evidence_store import EvidenceRepository, EvidenceType
from opportunity_engine.living_investment_file import LivingInvestmentFile


def test_collects_only_explicit_pipeline_evidence(tmp_path):
    repository = EvidenceRepository(tmp_path / "evidence")
    collector = ExistingSourceEvidenceCollector(repository)
    item = LivingInvestmentFile.create(
        "Office inventory",
        opportunity_id="unified-test-1",
        source_url="https://example.com/listing",
    )
    row = {
        "url": "https://example.com/listing",
        "source_name": "Auksjonen.no",
        "asking_price_nok": 100_000,
        "market_is_verified": True,
        "market_value_nok": 160_000,
        "market_comparable_count": 4,
        "seller_is_verified": True,
        "seller_name": "Verified Seller AS",
        "seller_score": 82,
        "city": "Trondheim",
    }

    result = collector.collect(item, row)

    assert result.extracted_count == 4
    assert result.created_count == 4
    assert result.linked_count == 4
    stored = repository.list_for_opportunity(item.opportunity_id)
    assert {e.evidence_type for e in stored} == {
        EvidenceType.MARKET_PRICE,
        EvidenceType.SELLER,
        EvidenceType.LOGISTICS,
    }
    assert len(item.evidence) == 4


def test_missing_and_unverified_values_do_not_become_evidence(tmp_path):
    repository = EvidenceRepository(tmp_path / "evidence")
    collector = ExistingSourceEvidenceCollector(repository)
    item = LivingInvestmentFile.create("Unknown lot", opportunity_id="unified-test-2")

    result = collector.collect(
        item,
        {
            "url": "https://example.com/listing",
            "asking_price_nok": None,
            "market_value_nok": 0,
            "market_is_verified": False,
            "seller_is_verified": False,
            "seller_score": None,
            "city": None,
        },
    )

    assert result.extracted_count == 0
    assert repository.list_for_opportunity(item.opportunity_id) == []
    assert item.evidence == []


def test_repeat_collection_is_deduplicated_and_not_relinked(tmp_path):
    repository = EvidenceRepository(tmp_path / "evidence")
    collector = ExistingSourceEvidenceCollector(repository)
    item = LivingInvestmentFile.create("Retail fittings", opportunity_id="unified-test-3")
    row = {
        "url": "https://example.com/listing",
        "source_name": "FINN.no",
        "asking_price_nok": 25_000,
        "city": "Namsos",
    }

    first = collector.collect(item, row)
    second = collector.collect(item, row)

    assert first.created_count == 2
    assert first.linked_count == 2
    assert second.created_count == 0
    assert second.updated_count == 0
    assert second.linked_count == 0
    assert len(repository.list_for_opportunity(item.opportunity_id)) == 2
    assert len(item.evidence) == 2


def test_collects_intelligence_warnings_as_weakening_evidence(tmp_path):
    repository = EvidenceRepository(tmp_path / "evidence")
    collector = ExistingSourceEvidenceCollector(repository)
    item = LivingInvestmentFile.create("Mixed stock", opportunity_id="unified-test-4")

    result = collector.collect(
        item,
        {"url": "https://example.com/listing"},
        intelligence={"warnings": ["Transport cost is not verified"]},
    )

    assert result.extracted_count == 1
    evidence = repository.list_for_opportunity(item.opportunity_id)[0]
    assert evidence.statement == "Transport cost is not verified"
    assert evidence.direction.value == "weakens"
