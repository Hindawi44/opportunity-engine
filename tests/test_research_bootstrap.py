from types import SimpleNamespace

from opportunity_engine.research_bootstrap import ResearchBootstrapPipeline


class Repo:
    def __init__(self):
        self.items = {key: SimpleNamespace(opportunity_id=key) for key in ("a", "b", "c", "d")}
        self.loaded = []
        self.saved = []

    def load(self, opportunity_id):
        self.loaded.append(opportunity_id)
        return self.items[opportunity_id]

    def save(self, item):
        self.saved.append(item.opportunity_id)


class Loop:
    def __init__(self, fail=None):
        self.fail = fail
        self.seen = []

    def run(self, item):
        self.seen.append(item.opportunity_id)
        if item.opportunity_id == self.fail:
            raise RuntimeError("provider unavailable")
        return SimpleNamespace(
            searches_executed=2,
            searches_skipped=0,
            evidence_created=1,
            evidence_updated=0,
            comparables_found=1,
            buyers_found=1,
            scenarios_regenerated=True,
            errors=(),
        )


def row(opportunity_id, resale, logistics, data_quality=10, warning=0, risk=0):
    return {
        "opportunity_id": opportunity_id,
        "title": f"Vareparti {opportunity_id}",
        "source_url": f"https://example.test/{opportunity_id}",
        "location": "Namsos",
        "price": 1000,
        "score": 19,
        "score_breakdown": [
            f"data_quality={data_quality}.0/15",
            f"resale={resale}.0/15",
            f"logistics={logistics}.0/15",
            f"warning_penalty={warning}.0",
            f"risk_penalty={risk}.0",
        ],
    }


def test_forwards_only_top_three_preliminary_candidates():
    repo = Repo()
    loop = Loop()
    payload = [
        row("a", 15, 15),
        row("b", 14, 14),
        row("c", 13, 13),
        row("d", 2, 2, data_quality=2, warning=4, risk=9),
    ]

    report = ResearchBootstrapPipeline(
        investment_repository=repo,
        external_loop_factory=lambda: loop,
        research_threshold=25,
        selection_limit=3,
    ).run(payload)

    assert report.external_research_queue_size == 3
    assert report.forwarded_candidates == 3
    assert report.completed_candidates == 3
    assert loop.seen == ["a", "b", "c"]
    assert repo.saved == ["a", "b", "c"]
    selected = [record for record in report.records if record.bootstrap_forwarded]
    assert all(record.selected_for_external_research for record in selected)
    assert all(record.bootstrap_reason == "top_ranked_candidate" for record in selected)
    assert all(record.external_research_requested for record in selected)
    assert report.searches_executed == 6
    assert report.evidence_created == 3


def test_missing_brave_configuration_preserves_queue_without_forwarding():
    repo = Repo()
    report = ResearchBootstrapPipeline(
        investment_repository=repo,
        external_loop_factory=lambda: Loop(),
        research_threshold=25,
        selection_limit=1,
        enabled=False,
        disabled_reason="missing_brave_api_key",
    ).run([row("a", 15, 15)])

    assert report.external_research_queue_size == 1
    assert report.forwarded_candidates == 0
    assert report.records[0].bootstrap_reason == "missing_brave_api_key"
    assert report.records[0].external_research_requested is False
    assert repo.loaded == []


def test_one_candidate_failure_does_not_abort_remaining_queue():
    repo = Repo()
    loop = Loop(fail="a")
    report = ResearchBootstrapPipeline(
        investment_repository=repo,
        external_loop_factory=lambda: loop,
        research_threshold=25,
        selection_limit=2,
    ).run([row("a", 15, 15), row("b", 14, 14)])

    assert loop.seen == ["a", "b"]
    assert report.forwarded_candidates == 2
    assert report.completed_candidates == 1
    assert report.failed_candidates == 1
    failed = next(record for record in report.records if record.opportunity_id == "a")
    assert failed.errors


def test_final_investment_score_is_not_used_as_bootstrap_gate():
    repo = Repo()
    loop = Loop()
    report = ResearchBootstrapPipeline(
        investment_repository=repo,
        external_loop_factory=lambda: loop,
        research_threshold=25,
        selection_limit=1,
    ).run([row("a", 15, 15)])

    assert report.records[0].research_candidate_score >= 25
    assert report.records[0].bootstrap_forwarded is True
    assert loop.seen == ["a"]
