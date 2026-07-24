from dataclasses import dataclass, field
from datetime import datetime, timezone

from opportunity_engine.external_evidence_loop import ExternalEvidenceLoop


@dataclass
class Missing:
    question: str
    resolved: bool = False


@dataclass
class Item:
    opportunity_id: str = "opp-1"
    title: str = "Butikkinnredning klær"
    summary: str = "Inventar for klesbutikk"
    location: str = "Namsos"
    missing_information: list = field(default_factory=lambda: [Missing("What is the market value?")])
    revenue_paths: list = field(default_factory=list)
    potential_buyers: list = field(default_factory=list)
    evidence: list = field(default_factory=list)

    def add_evidence(self, evidence):
        self.evidence.append(evidence)


class Search:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def search(self, query):
        self.calls.append(query)
        if self.fail:
            raise RuntimeError("rate limit")
        return {"query": query}


@dataclass
class StoredEvidence:
    evidence_id: str
    metadata: dict = field(default_factory=dict)


@dataclass
class UpsertResult:
    evidence: StoredEvidence
    created: bool = False
    observation_added: bool = False


class Repo:
    def __init__(self):
        self.items = {}

    def upsert(self, evidence):
        key = getattr(evidence, "evidence_id", str(id(evidence)))
        if key not in self.items:
            self.items[key] = evidence
            return UpsertResult(evidence, created=True)
        self.items[key] = evidence
        return UpsertResult(evidence)

    def list_for_opportunity(self, opportunity_id):
        return tuple(self.items.values())


class Score:
    score = 82.0
    grade = type("Grade", (), {"value": "strong"})()


class Scorer:
    def score(self, evidence, peers=()):
        return Score()


class Scenario:
    def __init__(self):
        self.calls = 0

    def generate(self, item, evidence_ids=()):
        self.calls += 1


class Comparable:
    title = "Used shop fixture"
    url = "https://marketplace.no/item/123"
    price_nok = 12000.0
    source_name = "Marketplace"
    observed_at = datetime.now(timezone.utc).isoformat()
    similarity_score = 0.82


class ComparablesResult:
    accepted = (Comparable(),)


class Comparables:
    def evaluate(self, candidates):
        return ComparablesResult()


class Candidate:
    name = "Norsk Butikkutstyr"
    website_url = "https://buyer.no"


class Ranked:
    candidate = Candidate()
    fit_score = 80.0


class BuyerResult:
    accepted = (Ranked(),)


class Buyers:
    def discover(self, candidates, **kwargs):
        return BuyerResult()


_counter = 0


def evidence_factory(**kwargs):
    global _counter
    _counter += 1
    item = StoredEvidence(f"ev-{_counter}")
    item.opportunity_id = kwargs["opportunity_id"]
    return item


def build_loop(search=None):
    scenario = Scenario()
    loop = ExternalEvidenceLoop(
        search_provider=search or Search(),
        evidence_repository=Repo(),
        evidence_factory=evidence_factory,
        evidence_scorer=Scorer(),
        scenario_generator=scenario,
        market_comparables_engine=Comparables(),
        buyer_discovery_engine=Buyers(),
        comparable_adapter=lambda response: (Comparable(),),
        buyer_adapter=lambda response: (Candidate(),),
    )
    return loop, scenario


def test_loop_searches_only_for_detected_gaps_and_regenerates_on_new_evidence():
    loop, scenario = build_loop()
    result = loop.run(Item())
    assert result.needs_detected == 2
    assert result.searches_executed == 2
    assert result.comparables_found == 1
    assert result.buyers_found == 1
    assert result.evidence_created == 2
    assert result.scenarios_regenerated is True
    assert scenario.calls == 1


def test_repeated_run_skips_same_searches_and_does_not_regenerate():
    loop, scenario = build_loop()
    loop.run(Item())
    result = loop.run(Item())
    assert result.searches_executed == 0
    assert result.searches_skipped == 2
    assert result.scenarios_regenerated is False
    assert scenario.calls == 1


def test_search_failure_is_recorded_without_stopping_the_loop():
    loop, scenario = build_loop(Search(fail=True))
    result = loop.run(Item())
    assert result.searches_executed == 0
    assert len(result.errors) == 2
    assert result.scenarios_regenerated is False
    assert scenario.calls == 0


def test_no_research_when_file_has_market_value_and_buyers():
    item = Item(missing_information=[], potential_buyers=["buyer"])
    item.revenue_paths = [type("Path", (), {"estimated_revenue_nok": 10000.0})()]
    loop, scenario = build_loop()
    result = loop.run(item)
    assert result.needs_detected == 0
    assert result.searches_executed == 0
    assert scenario.calls == 0
