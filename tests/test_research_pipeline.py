from opportunity_engine.evidence_store import EvidenceRepository
from opportunity_engine.living_investment_file import (
    LivingInvestmentFile,
    LivingInvestmentFileRepository,
)
from opportunity_engine.research_pipeline import ResearchPipelineOrchestrator


def _row():
    return {
        "source_name": "FINN.no",
        "url": "https://www.finn.no/example",
        "asking_price_nok": 100_000,
        "market_value_nok": 150_000,
        "market_is_verified": True,
        "market_comparable_count": 4,
        "city": "Namsos",
        "seller_is_verified": True,
        "seller_name": "Verified seller",
        "seller_score": 85,
    }


def test_runs_full_cycle_and_persists_outputs(tmp_path):
    evidence_repo = EvidenceRepository(tmp_path / "evidence")
    investment_repo = LivingInvestmentFileRepository(tmp_path / "investment_files")
    orchestrator = ResearchPipelineOrchestrator(
        evidence_repository=evidence_repo,
        investment_repository=investment_repo,
        run_log_root=tmp_path / "runs",
    )
    item = LivingInvestmentFile.create(
        "Liquidation lot",
        opportunity_id="opp-pipeline-1",
        asking_price_nok=100_000,
        source_url="https://www.finn.no/example",
        source_name="FINN.no",
    )

    result = orchestrator.run(item, _row())

    assert result.evidence_created > 0
    assert result.evidence_scored == len(evidence_repo.list_for_opportunity(item.opportunity_id))
    assert result.scenarios_regenerated is True
    assert len(item.revenue_paths) == 6
    assert investment_repo.load(item.opportunity_id).revenue_paths
    assert list((tmp_path / "runs" / item.opportunity_id).glob("*.json"))


def test_second_identical_run_does_not_regenerate_scenarios(tmp_path):
    evidence_repo = EvidenceRepository(tmp_path / "evidence")
    investment_repo = LivingInvestmentFileRepository(tmp_path / "investment_files")
    orchestrator = ResearchPipelineOrchestrator(
        evidence_repository=evidence_repo,
        investment_repository=investment_repo,
        run_log_root=tmp_path / "runs",
    )
    item = LivingInvestmentFile.create(
        "Liquidation lot",
        opportunity_id="opp-pipeline-2",
        asking_price_nok=100_000,
    )

    first = orchestrator.run(item, _row())
    second = orchestrator.run(item, _row())

    assert first.scenarios_regenerated is True
    assert second.evidence_created == 0
    assert second.evidence_updated == 0
    assert second.evidence_linked == 0
    assert second.scenarios_regenerated is False


def test_collector_failure_is_logged_without_crashing_cycle(tmp_path):
    class BrokenCollector:
        def collect(self, *args, **kwargs):
            raise RuntimeError("collector unavailable")

    item = LivingInvestmentFile.create(
        "Failure case",
        opportunity_id="opp-pipeline-3",
    )
    orchestrator = ResearchPipelineOrchestrator(
        evidence_repository=EvidenceRepository(tmp_path / "evidence"),
        investment_repository=LivingInvestmentFileRepository(tmp_path / "investment_files"),
        collector=BrokenCollector(),
        run_log_root=tmp_path / "runs",
    )

    result = orchestrator.run(item, {})

    assert any(error.startswith("collector:") for error in result.errors)
    assert result.scenarios_regenerated is False
    assert list((tmp_path / "runs" / item.opportunity_id).glob("*.json"))
