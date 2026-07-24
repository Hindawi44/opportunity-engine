from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT = SCRIPTS / "run_v28_comparable_collection.py"
spec = importlib.util.spec_from_file_location("run_v28_comparable_collection", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def observation(value: float | None, currency: str | None = "NOK") -> SimpleNamespace:
    return SimpleNamespace(numeric_value=value, currency=currency)


def evidence(*, value: float | None, currency: str | None = "NOK", url: str = "https://example.no/item") -> SimpleNamespace:
    return SimpleNamespace(
        evidence_type="market_price",
        source_url=url,
        observations=[observation(value, currency)],
    )


def test_verified_gate_requires_positive_nok_https_observation() -> None:
    assert module._has_verified_nok_observation(evidence(value=1200)) is True
    assert module._has_verified_nok_observation(evidence(value=None)) is False
    assert module._has_verified_nok_observation(evidence(value=0)) is False
    assert module._has_verified_nok_observation(evidence(value=1200, currency="EUR")) is False
    assert module._has_verified_nok_observation(evidence(value=1200, url="http://example.no/item")) is False


def test_invalid_market_price_shells_do_not_stop_search() -> None:
    repository = SimpleNamespace(
        list_for_opportunity=lambda _opportunity_id: [
            evidence(value=None),
            evidence(value=0),
            evidence(value=1200, currency="EUR"),
        ]
    )
    loop = object.__new__(module.ComparableCollectionLoop)
    loop.evidence_repository = repository
    investment_file = SimpleNamespace(opportunity_id="opp-1", title="Brukt industrimaskin")

    needs = loop.detect_needs(investment_file)

    assert len(needs) == 2
    assert all(need.kind == "market" for need in needs)


def test_three_valid_persisted_comparables_stop_search() -> None:
    repository = SimpleNamespace(
        list_for_opportunity=lambda _opportunity_id: [
            evidence(value=1000, url="https://one.no/item"),
            evidence(value=1200, url="https://two.no/item"),
            evidence(value=1400, url="https://three.no/item"),
        ]
    )
    loop = object.__new__(module.ComparableCollectionLoop)
    loop.evidence_repository = repository
    investment_file = SimpleNamespace(opportunity_id="opp-1", title="Brukt industrimaskin")

    assert loop.detect_needs(investment_file) == ()
