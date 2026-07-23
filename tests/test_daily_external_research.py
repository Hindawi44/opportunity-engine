from types import SimpleNamespace

from opportunity_engine.daily_external_research import DailyExternalResearchActivator


class Repo:
    def __init__(self):
        self.items = {"a": SimpleNamespace(opportunity_id="a"), "b": SimpleNamespace(opportunity_id="b")}
        self.saved = []

    def load(self, opportunity_id):
        return self.items[opportunity_id]

    def save(self, item):
        self.saved.append(item.opportunity_id)


class Loop:
    def __init__(self, fail=None):
        self.fail = fail
        self.search_provider = SimpleNamespace(usage=SimpleNamespace(cache_hits=2))
        self.seen = []

    def run(self, item):
        self.seen.append(item.opportunity_id)
        if item.opportunity_id == self.fail:
            raise RuntimeError("boom")
        return SimpleNamespace(searches_executed=1, searches_skipped=1, errors=())


def test_selects_only_highest_scored_bounded_opportunities():
    repo = Repo()
    loop = Loop()
    result = DailyExternalResearchActivator(
        investment_repository=repo,
        loop_factory=lambda: loop,
        max_opportunities=1,
    ).run([
        {"opportunity_id": "a", "score": 20},
        {"opportunity_id": "b", "score": 90},
    ])
    assert loop.seen == ["b"]
    assert repo.saved == ["b"]
    assert result.selected == 1
    assert result.searches_executed == 1
    assert result.cache_hits == 2


def test_missing_api_configuration_disables_without_failure():
    result = DailyExternalResearchActivator(
        investment_repository=Repo(),
        loop_factory=lambda: Loop(),
        enabled=False,
        disabled_reason="missing_brave_api_key",
    ).run([{"opportunity_id": "a", "score": 10}])
    assert result.enabled is False
    assert result.reason == "missing_brave_api_key"
    assert result.selected == 0


def test_one_opportunity_failure_does_not_abort_remaining_work():
    repo = Repo()
    loop = Loop(fail="a")
    result = DailyExternalResearchActivator(
        investment_repository=repo,
        loop_factory=lambda: loop,
        max_opportunities=2,
    ).run([
        {"opportunity_id": "a", "score": 90},
        {"opportunity_id": "b", "score": 80},
    ])
    assert loop.seen == ["a", "b"]
    assert repo.saved == ["b"]
    assert result.completed == 1
    assert result.failed == 1
    assert result.errors
