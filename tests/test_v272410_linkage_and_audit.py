from types import SimpleNamespace
from unittest.mock import patch

from opportunity_engine.external_execution_audit import TracingSearchProvider
from opportunity_engine.linked_scenario_generator import LinkedScenarioGeneratorEngine
from opportunity_engine.scenario_generator import ScenarioGeneratorEngine


class FakeProvider:
    request_count = 0
    cache_hits = 0

    def search(self, query, **kwargs):
        self.request_count += 1
        return [{"title": "Result", "url": "https://example.com/item"}]


def test_tracing_refresh_counts_landing_page_price_mutation():
    tracing = TracingSearchProvider(FakeProvider())
    response = tracing.search("query")
    assert tracing.traces[0].explicit_price_result_count == 0

    response[0]["price_nok"] = 4990.0
    tracing.refresh_price_counts()

    assert tracing.traces[0].explicit_price_result_count == 1


def test_linked_generator_resolves_repository_id_to_living_mirror_id():
    item = SimpleNamespace(
        evidence=[SimpleNamespace(evidence_id="ev_living", notes="research:rev_repository")]
    )
    engine = LinkedScenarioGeneratorEngine()

    with patch.object(ScenarioGeneratorEngine, "generate", return_value="ok") as parent_generate:
        result = engine.generate(item, evidence_ids=("rev_repository",))

    assert result == "ok"
    parent_generate.assert_called_once_with(item, None, evidence_ids=("ev_living",))


def test_linked_generator_keeps_already_living_evidence_id():
    item = SimpleNamespace(
        evidence=[SimpleNamespace(evidence_id="ev_living", notes=None)]
    )
    engine = LinkedScenarioGeneratorEngine()

    with patch.object(ScenarioGeneratorEngine, "generate", return_value="ok") as parent_generate:
        engine.generate(item, evidence_ids=("ev_living",))

    parent_generate.assert_called_once_with(item, None, evidence_ids=("ev_living",))
