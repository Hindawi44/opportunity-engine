from opportunity_engine.evidence_store import (
    EvidenceConfidence,
    EvidenceDirection,
    EvidenceRepository,
    EvidenceType,
    ResearchEvidence,
)


def test_creates_and_persists_evidence(tmp_path):
    repository = EvidenceRepository(tmp_path)
    item = ResearchEvidence.create(
        opportunity_id="opp_1",
        evidence_type=EvidenceType.MARKET_PRICE,
        statement="Comparable listing priced at 12 000 NOK",
        source_name="FINN.no",
        source_url="https://example.com/listing/1",
        confidence=EvidenceConfidence.MEDIUM,
        direction=EvidenceDirection.SUPPORTS,
        scenario_ids=["scenario_purchase"],
        numeric_value=12_000,
        currency="nok",
    )

    result = repository.upsert(item)
    loaded = repository.load("opp_1", item.evidence_id)

    assert result.created is True
    assert loaded.statement == item.statement
    assert loaded.observations[0].numeric_value == 12_000
    assert loaded.observations[0].currency == "NOK"
    assert loaded.scenario_ids == ["scenario_purchase"]


def test_deduplicates_same_evidence_and_preserves_history(tmp_path):
    repository = EvidenceRepository(tmp_path)
    first = ResearchEvidence.create(
        opportunity_id="opp_1",
        evidence_type=EvidenceType.COST,
        statement="Transport quote for Namsos delivery",
        source_name="Transport company",
        source_url="https://example.com/quote",
        numeric_value=4_000,
        currency="NOK",
    )
    repository.upsert(first)

    second = ResearchEvidence.create(
        opportunity_id="opp_1",
        evidence_type=EvidenceType.COST,
        statement="Transport quote for Namsos delivery",
        source_name="Transport company",
        source_url="https://example.com/quote",
        confidence=EvidenceConfidence.HIGH,
        numeric_value=4_500,
        currency="NOK",
        scenario_ids=["scenario_purchase", "scenario_lot_split"],
    )
    result = repository.upsert(second)

    stored = repository.list_for_opportunity("opp_1")
    assert result.created is False
    assert result.observation_added is True
    assert len(stored) == 1
    assert len(stored[0].observations) == 2
    assert stored[0].confidence is EvidenceConfidence.HIGH
    assert stored[0].scenario_ids == ["scenario_purchase", "scenario_lot_split"]


def test_exact_duplicate_observation_is_not_repeated(tmp_path):
    repository = EvidenceRepository(tmp_path)
    item = ResearchEvidence.create(
        opportunity_id="opp_1",
        evidence_type=EvidenceType.DEMAND,
        statement="Three similar active listings",
        source_name="Marketplace",
        source_url="https://example.com/search",
        numeric_value=3,
    )
    repository.upsert(item)
    result = repository.upsert(
        ResearchEvidence.create(
            opportunity_id="opp_1",
            evidence_type=EvidenceType.DEMAND,
            statement="Three similar active listings",
            source_name="Marketplace",
            source_url="https://example.com/search",
            numeric_value=3,
        )
    )

    assert result.observation_added is False
    assert len(repository.list_for_opportunity("opp_1")[0].observations) == 1


def test_missing_numeric_value_remains_none(tmp_path):
    repository = EvidenceRepository(tmp_path)
    item = ResearchEvidence.create(
        opportunity_id="opp_2",
        evidence_type=EvidenceType.BUYER,
        statement="Potential buyer identified",
        source_name="Company register",
        source_url="https://example.com/company",
    )

    repository.upsert(item)
    loaded = repository.list_for_opportunity("opp_2")[0]
    assert loaded.observations[0].numeric_value is None
    assert loaded.observations[0].currency is None


def test_rejects_negative_values_and_non_https_urls():
    try:
        ResearchEvidence.create(
            opportunity_id="opp_1",
            evidence_type=EvidenceType.COST,
            statement="Invalid cost",
            source_name="Source",
            numeric_value=-1,
        )
    except ValueError as exc:
        assert "negative" in str(exc)
    else:
        raise AssertionError("Expected negative value to fail")

    try:
        ResearchEvidence.create(
            opportunity_id="opp_1",
            evidence_type=EvidenceType.LEGAL,
            statement="Rule",
            source_name="Authority",
            source_url="http://example.com/rule",
        )
    except ValueError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("Expected non-HTTPS URL to fail")


def test_repository_rejects_unsafe_opportunity_ids(tmp_path):
    repository = EvidenceRepository(tmp_path)
    try:
        repository.list_for_opportunity("../outside")
    except ValueError as exc:
        assert "Invalid opportunity_id" in str(exc)
    else:
        raise AssertionError("Expected unsafe opportunity id to fail")
