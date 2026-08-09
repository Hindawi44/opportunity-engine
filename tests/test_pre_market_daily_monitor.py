import json
from pathlib import Path

import pytest

from opportunity_engine.discovery.estate_manager_enrichment_pilot import (
    EstateManagerEnrichment,
)
from opportunity_engine.discovery.konkurs_app_clothing_adapter import (
    KonkursAppClothingCollection,
    KonkursAppClothingLead,
)
from opportunity_engine.discovery.pre_market_daily_monitor import (
    SOURCE_COMPLETE,
    SOURCE_TEMPORARILY_UNAVAILABLE,
    run_pre_market_daily_monitor,
    write_pre_market_daily_monitor_artifacts,
)
from opportunity_engine.discovery.pre_market_sale_channel_search import (
    SaleChannelSearchResult,
)


class StaticCollector:
    def __init__(self, collection):
        self.collection = collection

    def collect(self):
        return self.collection


class StaticEnrichmentCollector:
    def __init__(self, enrichment):
        self.enrichment = enrichment

    def collect(self):
        return self.enrichment


def lead(orgnr: str, debtor_name: str, *, assets: float) -> KonkursAppClothingLead:
    return KonkursAppClothingLead(
        estate_orgnr=orgnr,
        estate_name=f"{debtor_name} KONKURSBO",
        debtor_name=debtor_name,
        url=f"https://konkurs.app/konkursbo/{orgnr}",
        opened_date="2026-07-20",
        registered_date="2026-07-20",
        industry_code="46.420",
        industry_description="Engroshandel med klær og skotøy",
        municipality="OSLO",
        postal_place="OSLO",
        mva_registered=True,
        accounting_year="2025",
        accounting_currency="NOK",
        revenue=12_000_000,
        total_assets=assets,
        total_debt=1_000_000,
        priority_score=90,
    )


def collection(*leads: KonkursAppClothingLead) -> KonkursAppClothingCollection:
    return KonkursAppClothingCollection(
        captured_at="2026-07-30T12:00:00+00:00",
        from_date="2025-07-30",
        endpoints=("https://konkurs.app/api/konkursbo?one",),
        items_received=len(leads),
        leads=tuple(leads),
        scan_complete=True,
        errors=(),
    )


def enrichment(orgnr: str, debtor_name: str) -> EstateManagerEnrichment:
    debtor_orgnr = "986425284" if orgnr == "938018014" else "987654321"
    return EstateManagerEnrichment(
        captured_at="2026-07-30T12:01:00+00:00",
        estate_orgnr=orgnr,
        estate_name=f"{debtor_name} KONKURSBO",
        debtor_orgnr=debtor_orgnr,
        debtor_name=debtor_name,
        opened_date="2026-07-20",
        industry_code="46.420",
        industry_description="Engroshandel med klær og skotøy",
        municipality="OSLO",
        estate_manager_name="Adv. Example Manager",
        source_endpoint=f"https://konkurs.app/api/konkursbo/{orgnr}",
    )


def completed_search(value: EstateManagerEnrichment) -> SaleChannelSearchResult:
    return SaleChannelSearchResult(
        captured_at="2026-07-30T12:02:00+00:00",
        estate=value,
        queries=("q1", "q2", "q3", "q4", "q5"),
        requests_made=5,
        raw_hits=0,
        candidates=(),
        errors=(),
    )


def test_daily_monitor_is_bounded_and_updates_only_completed_cases():
    leads = collection(
        lead("938018014", "MENSWEAR NORGE AS", assets=11_000_000),
        lead("938022038", "KEEPFIT AS", assets=3_000_000),
    )

    result = run_pre_market_daily_monitor(
        api_key="test-key",
        previous_cases={},
        case_limit=1,
        collector_factory=lambda: StaticCollector(leads),
        enrichment_factory=lambda orgnr: StaticEnrichmentCollector(
            enrichment(orgnr, "MENSWEAR NORGE AS")
        ),
        provider_factory=lambda _key: object(),
        search_runner=lambda value, _provider, **_kwargs: completed_search(value),
        captured_at="2026-07-30T12:03:00+00:00",
    )

    assert result.source_status == SOURCE_COMPLETE
    assert result.allocated_query_budget == 5
    assert result.requests_made == 5
    assert len(result.attempts) == 1
    assert len(result.tracker.cases) == 1
    assert result.tracker.cases[0].state == "NO_PUBLIC_SALE_CHANNEL_FOUND"
    assert result.to_dict()["commercial_top5_count"] == 0
    assert result.to_dict()["automatic_contact"] is False


def test_source_failure_preserves_previous_case_without_false_state_change():
    leads = collection(lead("938018014", "MENSWEAR NORGE AS", assets=11_000_000))
    common = dict(
        api_key="test-key",
        case_limit=1,
        collector_factory=lambda: StaticCollector(leads),
        enrichment_factory=lambda orgnr: StaticEnrichmentCollector(
            enrichment(orgnr, "MENSWEAR NORGE AS")
        ),
        provider_factory=lambda _key: object(),
    )
    first = run_pre_market_daily_monitor(
        previous_cases={},
        search_runner=lambda value, _provider, **_kwargs: completed_search(value),
        captured_at="2026-07-30T12:03:00+00:00",
        **common,
    )
    previous = {case.case_id: case for case in first.tracker.cases}

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("Brave temporarily unavailable")

    second = run_pre_market_daily_monitor(
        previous_cases=previous,
        search_runner=unavailable,
        captured_at="2026-07-31T12:03:00+00:00",
        **common,
    )

    assert second.source_status == SOURCE_TEMPORARILY_UNAVAILABLE
    assert len(second.unavailable_attempts) == 1
    assert second.tracker.cases[0] == first.tracker.cases[0]
    assert second.tracker.changes == ()
    assert second.tracker.alerts == ()
    assert second.to_dict()["incomplete_sources_are_treated_as_no_sale"] is False


def test_incomplete_search_result_is_not_applied_to_registry():
    leads = collection(lead("938018014", "MENSWEAR NORGE AS", assets=11_000_000))
    value = enrichment("938018014", "MENSWEAR NORGE AS")
    incomplete = SaleChannelSearchResult(
        captured_at="2026-07-30T12:02:00+00:00",
        estate=value,
        queries=("q1", "q2", "q3", "q4", "q5"),
        requests_made=4,
        raw_hits=0,
        candidates=(),
        errors=({"query": "q5", "error": "timeout"},),
    )

    result = run_pre_market_daily_monitor(
        api_key="test-key",
        previous_cases={},
        case_limit=1,
        collector_factory=lambda: StaticCollector(leads),
        enrichment_factory=lambda _orgnr: StaticEnrichmentCollector(value),
        provider_factory=lambda _key: object(),
        search_runner=lambda *_args, **_kwargs: incomplete,
    )

    assert result.source_status == SOURCE_TEMPORARILY_UNAVAILABLE
    assert result.tracker.cases == ()
    assert result.attempts[0].requests_made == 4
    assert result.attempts[0].errors == ("timeout",)
    assert result.source_status_dict()[
        "failed_or_incomplete_observations_applied_to_registry"
    ] is False


def test_writer_outputs_durable_registry_and_source_status(tmp_path: Path):
    leads = collection(lead("938018014", "MENSWEAR NORGE AS", assets=11_000_000))
    value = enrichment("938018014", "MENSWEAR NORGE AS")
    result = run_pre_market_daily_monitor(
        api_key="test-key",
        previous_cases={},
        case_limit=1,
        collector_factory=lambda: StaticCollector(leads),
        enrichment_factory=lambda _orgnr: StaticEnrichmentCollector(value),
        provider_factory=lambda _key: object(),
        search_runner=lambda *_args, **_kwargs: completed_search(value),
    )

    paths = write_pre_market_daily_monitor_artifacts(result, tmp_path)
    registry = json.loads(paths["registry"].read_text(encoding="utf-8"))
    source_status = json.loads(paths["source_status"].read_text(encoding="utf-8"))
    commercial = json.loads(paths["commercial_top5"].read_text(encoding="utf-8"))

    assert registry["case_count"] == 1
    assert source_status["sale_channel_searches"][0]["source_status"] == "COMPLETE"
    assert source_status["sale_channel_searches"][0]["automatic_contact"] is False
    assert commercial == []
    assert paths["daily_summary"].exists()


def test_daily_monitor_rejects_unbounded_configuration():
    with pytest.raises(ValueError):
        run_pre_market_daily_monitor(
            api_key="test-key",
            previous_cases={},
            case_limit=21,
        )
    with pytest.raises(ValueError):
        run_pre_market_daily_monitor(
            api_key="test-key",
            previous_cases={},
            results_per_query=21,
        )


def test_existing_workflow_keeps_pre_market_monitor_manual_only():
    workflow = Path(".github/workflows/daily-opportunity-pipeline.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in workflow
    assert "\n  schedule:" not in workflow
    assert "pre-market-monitor:" in workflow
    assert "needs: generate" in workflow
    assert "BRAVE_SEARCH_API_KEY" in workflow
    assert "run_pre_market_daily_monitor.py" in workflow
    assert "--case-limit 10" in workflow
    assert "data/pre_market_cases.json" in workflow
    assert "concurrency:" in workflow
    # Historical .yml shells have moved out of GitHub Actions; tests.yml is the
    # only current .yml workflow. Operational workflows use .yaml.
    assert len(list(Path(".github/workflows").glob("*.yml"))) == 1
