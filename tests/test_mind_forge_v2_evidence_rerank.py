from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.mind_forge_v2_evidence_rerank import rerank_with_evidence


FIXTURE = Path(__file__).parent / "fixtures" / "mind_forge_v2_live_top3_32566688085.json"


def _reasoning():
    return {
        "selected_idea_ids": ["a", "b", "c"],
        "assessments": [
            {"idea_id": "a", "title": "A", "mechanism_family": "x", "composite_score": 0.72},
            {"idea_id": "b", "title": "B", "mechanism_family": "y", "composite_score": 0.69},
            {"idea_id": "c", "title": "C", "mechanism_family": "z", "composite_score": 0.66},
        ],
    }


def _obs(idea_id, stance, confidence=0.9, source_type="official", ref=None):
    return {
        "idea_id": idea_id,
        "stance": stance,
        "confidence": confidence,
        "source_type": source_type,
        "source_ref": ref or f"https://example.test/{idea_id}/{stance}",
        "observation_text": f"Evidence for {idea_id}: {stance}",
    }


def test_no_evidence_preserves_reasoning_order():
    result = rerank_with_evidence(_reasoning(), [])
    assert result["selected_idea_ids"] == ["a", "b", "c"]
    assert all(row["evidence_status"] == "NO_EVIDENCE" for row in result["ranking"])


def test_strong_primary_evidence_can_change_order():
    result = rerank_with_evidence(
        _reasoning(),
        [
            _obs("a", "CONTRADICTS", 0.95, "official"),
            _obs("b", "SUPPORTS", 0.95, "official"),
            _obs("c", "SUPPORTS", 0.75, "industry"),
        ],
    )
    assert result["selected_idea_ids"][0] == "b"
    assert result["ranking"][-1]["idea_id"] == "a"


def test_conflicting_evidence_is_penalized():
    result = rerank_with_evidence(
        _reasoning(),
        [
            _obs("a", "SUPPORTS", 0.9, "official", "https://example.test/a/1"),
            _obs("a", "CONTRADICTS", 0.9, "official", "https://example.test/a/2"),
            _obs("b", "SUPPORTS", 0.75, "industry"),
        ],
    )
    row_a = next(row for row in result["ranking"] if row["idea_id"] == "a")
    assert row_a["conflicting_evidence"] is True
    assert result["selected_idea_ids"][0] == "b"


def test_rejects_evidence_for_non_candidate():
    with pytest.raises(ValueError, match="outside selected candidates"):
        rerank_with_evidence(_reasoning(), [_obs("not-selected", "SUPPORTS")])


def test_mechanism_family_labels_do_not_change_result():
    original = _reasoning()
    renamed = deepcopy(original)
    for idx, row in enumerate(renamed["assessments"]):
        row["mechanism_family"] = f"completely-new-family-{idx}"
    evidence = [_obs("a", "SUPPORTS"), _obs("b", "CONTRADICTS")]
    first = rerank_with_evidence(original, evidence)
    second = rerank_with_evidence(renamed, evidence)
    assert first["ranking"] == second["ranking"]
    assert first["uses_mechanism_family_for_scoring"] is False


def test_live_top3_fixture_preserves_real_reasoning_order_without_evidence():
    live = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = rerank_with_evidence(live, [])
    assert live["source_run_id"] == 32566688085
    assert live["source_artifact_id"] == 9474264157
    assert result["selected_titles"] == [
        "Verified Local Supplier Desk",
        "Cold-Chain Route Orchestrator",
        "Multilingual Microbusiness Back Office",
    ]


def test_live_top3_fixture_allows_sourced_evidence_to_change_real_order():
    live = json.loads(FIXTURE.read_text(encoding="utf-8"))
    supplier, cold_chain, backoffice = live["selected_idea_ids"]
    result = rerank_with_evidence(
        live,
        [
            _obs(supplier, "SUPPORTS", 0.95, "official", "https://official.example/supplier"),
            _obs(cold_chain, "CONTRADICTS", 0.90, "official", "https://official.example/cold-chain"),
            _obs(backoffice, "SUPPORTS", 0.90, "primary", "https://primary.example/backoffice"),
        ],
    )
    assert result["selected_idea_ids"][0] == supplier
    assert result["selected_idea_ids"][-1] == cold_chain
