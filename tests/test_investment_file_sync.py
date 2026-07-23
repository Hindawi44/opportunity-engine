from opportunity_engine.investment_file_sync import InvestmentFileSynchronizer
from opportunity_engine.living_investment_file import LivingInvestmentFileRepository


def _row(**overrides):
    row = {
        "opportunity_id": "unified-demo-1",
        "title": "Demo liquidation lot",
        "url": "https://example.com/listing/1",
        "city": "Namsos",
        "asking_price_nok": None,
        "score": 72.5,
        "decision": "monitor",
        "decision_label": "Monitor",
        "market_is_verified": False,
        "market_value_nok": None,
    }
    row.update(overrides)
    return row


def test_sync_creates_one_living_file_without_inventing_price(tmp_path):
    result = InvestmentFileSynchronizer(tmp_path).sync_payload({"rows": [_row()]})

    assert result.created_count == 1
    item = LivingInvestmentFileRepository(tmp_path).load("unified-demo-1")
    assert item.asking_price_nok is None
    assert item.internal_score == 72.5
    assert item.internal_signal == "monitor"
    assert item.location == "Namsos"


def test_sync_updates_discovery_fields_and_preserves_research(tmp_path):
    synchronizer = InvestmentFileSynchronizer(tmp_path)
    synchronizer.sync_rows([_row()])

    repository = LivingInvestmentFileRepository(tmp_path)
    item = repository.load("unified-demo-1")
    item.add_assumption("The lot can be split", "Ask the seller")
    repository.save(item)

    result = synchronizer.sync_rows([
        _row(asking_price_nok=15000, city="Steinkjer", score=80, decision="watch")
    ])

    assert result.updated_count == 1
    updated = repository.load("unified-demo-1")
    assert updated.asking_price_nok == 15000
    assert updated.location == "Steinkjer"
    assert len(updated.assumptions) == 1
    assert updated.internal_score == 80
    assert updated.internal_signal == "watch"


def test_verified_market_value_is_added_as_evidence_once(tmp_path):
    synchronizer = InvestmentFileSynchronizer(tmp_path)
    row = _row(market_is_verified=True, market_value_nok=42000)

    synchronizer.sync_rows([row])
    synchronizer.sync_rows([row])

    item = LivingInvestmentFileRepository(tmp_path).load("unified-demo-1")
    matching = [e for e in item.evidence if "42000.00 NOK" in e.statement]
    assert len(matching) == 1
