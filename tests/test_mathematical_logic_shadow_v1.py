from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from opportunity_engine.discovery.mathematical_logic_shadow import (
    ENGINE_VERSION,
    OUTPUT_FILENAME,
    READINESS_DIMENSIONS,
    build_mathematical_logic_shadow,
    write_mathematical_logic_shadow,
)


NOW = datetime(2026, 8, 17, 6, 40, tzinfo=timezone.utc)


def _case(
    case_id: str,
    *,
    countries: list[str],
    case_type: str = "DIRECT_OPPORTUNITY",
    price: bool = False,
    quantity: bool = False,
    gate_passed: bool = False,
) -> dict:
    return {
        "case_id": case_id,
        "case_title": case_id,
        "case_type": case_type,
        "case_status": "ACTIVE",
        "countries": countries,
        "priority_class": "TEST_BASELINE_PRIORITY",
        "decision_lane": "TEST_BASELINE_LANE",
        "actionability_score": 61.25,
        "commercial_strength": 70.0,
        "source_strength": 80.0,
        "item_count": 2,
        "evidence_count": 4,
        "source_names": ["Source A", "Source B"],
        "source_urls": ["https://example.test/a"],
        "missing_information": ["SOMETHING"] if not gate_passed else [],
        "risk_flags": ["TEST_RISK"] if not gate_passed else [],
        "commercial_snapshot": {
            "quantities": [{"quantity": 10}] if quantity else [],
            "prices": [{"price": 100}] if price else [],
        },
        "verification_gate": {
            "gate_passed": gate_passed,
            "required_evidence": ["A", "B"],
            "missing_required_evidence": [] if gate_passed else ["B"],
        },
    }


def test_math_shadow_is_unweighted_read_only_and_deterministic() -> None:
    source = {
        "schema_version": "unified-market-cases-1.0",
        "river_schema_version": "unified-market-intelligence-river-1.0",
        "case_count": 2,
        "cases": [
            _case("core", countries=["NO"], price=True, quantity=True, gate_passed=True),
            _case("sidecar", countries=["FR"]),
        ],
    }

    first = build_mathematical_logic_shadow(
        source,
        generated_at=NOW,
        baseline_commit="abc123",
    )
    second = build_mathematical_logic_shadow(
        source,
        generated_at=NOW,
        baseline_commit="abc123",
    )

    assert first == second
    assert first["engine_version"] == ENGINE_VERSION
    assert first["methodology"]["stage"] == "MATHEMATICAL_LOGIC_ONLY"
    assert first["methodology"]["language_logic_enabled"] is False
    assert first["methodology"]["probability_law_selected"] is False
    assert first["methodology"]["predictive_model_enabled"] is False
    assert first["methodology"]["feature_weighting_enabled"] is False
    assert first["methodology"]["llm_calls"] == 0
    assert first["methodology"]["external_api_calls"] == 0
    assert first["methodology"]["decision_influence"] == "NONE"
    assert first["baseline"]["coverage_matches_declared_count"] is True
    assert first["baseline"]["commit_sha"] == "abc123"
    assert first["coverage"]["core_markets"] == ["NO", "SE", "DE"]
    assert first["coverage"]["expansion_sidecars"] == ["IT", "NL", "FR"]

    by_id = {row["case_id"]: row for row in first["cases"]}
    core = by_id["core"]
    assert set(core["readiness_vector"]) == set(READINESS_DIMENSIONS)
    assert core["readiness"]["known_dimension_count"] == 6
    assert core["readiness"]["completeness_fraction"] == 1.0
    assert core["readiness"]["decision_distance"] == 0
    assert core["segment"] == "CORE_OPPORTUNITY_MARKETS"
    assert core["baseline"]["actionability_score"] == 61.25

    sidecar = by_id["sidecar"]
    assert sidecar["segment"] == "EXPANSION_SIDECARS"
    assert sidecar["readiness"]["known_dimension_count"] == 3
    assert sidecar["readiness"]["decision_distance"] == 3

    assert first["safety"]["top5_changed"] is False
    assert first["safety"]["primary_human_action_changed"] is False
    assert first["safety"]["canonical_market_scope_changed"] is False
    assert first["safety"]["automatic_purchase"] is False


def test_fabric_is_separate_from_expansion_sidecar() -> None:
    source = {
        "case_count": 1,
        "cases": [
            _case(
                "fabric",
                countries=["IT"],
                case_type="FABRIC_PROCUREMENT",
                gate_passed=True,
            )
        ],
    }
    report = build_mathematical_logic_shadow(source, generated_at=NOW)
    assert report["cases"][0]["segment"] == "FABRIC_PROCUREMENT"
    assert report["coverage"]["segment_counts"] == {"FABRIC_PROCUREMENT": 1}


def test_sidecar_funnels_measure_conversion_without_inventing_denominators(tmp_path: Path) -> None:
    files = {
        "italy-market-discovery-v1.json": {"accepted_signal_count": 8, "status": "SUCCESS"},
        "italy-case-memory-v1.json": {"persistent_case_count": 4},
        "italy-signal-follow-up-v1.json": {"commercial_lead_count": 2},
        "italy-exact-lot-verification-v1.json": {"verified_active_exact_lot_lead_count": 1},
        "italy-commercial-qualification-v1.json": {
            "qualification_count": 1,
            "financial_decision_ready_count": 0,
        },
        "netherlands-market-discovery-v1.json": {"accepted_signal_count": 0, "status": "VALID_ZERO"},
        "netherlands-case-memory-v1.json": {"persistent_case_count": 0},
        "netherlands-signal-follow-up-v1.json": {"commercial_lead_count": 0},
        "france-market-discovery-v1.json": {"accepted_signal_count": 3, "status": "SUCCESS"},
        "france-case-memory-v1.json": {"persistent_case_count": 1},
        "france-signal-follow-up-v1.json": {"commercial_lead_count": 0},
    }
    for filename, payload in files.items():
        (tmp_path / filename).write_text(json.dumps(payload), encoding="utf-8")

    report = build_mathematical_logic_shadow(
        {"case_count": 0, "cases": []},
        output_dir=tmp_path,
        generated_at=NOW,
    )

    italy = report["sidecar_funnels"]["IT"]
    assert italy["first_stage_count"] == 8
    assert italy["last_stage_count"] == 0
    assert italy["end_to_end_conversion"] == 0.0
    assert italy["stages"][1]["conversion_from_previous"] == 0.5
    assert italy["stages"][2]["conversion_from_previous"] == 0.5

    netherlands = report["sidecar_funnels"]["NL"]
    assert netherlands["end_to_end_conversion"] is None
    assert netherlands["stages"][1]["conversion_from_previous"] is None


def test_writer_uses_existing_unified_cases_and_creates_only_shadow_artifact(tmp_path: Path) -> None:
    source = {
        "schema_version": "unified-market-cases-1.0",
        "case_count": 1,
        "cases": [_case("one", countries=["DE"], price=True)],
    }
    source_path = tmp_path / "unified-market-cases.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    before = source_path.read_text(encoding="utf-8")

    report = write_mathematical_logic_shadow(tmp_path, baseline_commit="deadbeef")

    assert (tmp_path / OUTPUT_FILENAME).exists()
    assert source_path.read_text(encoding="utf-8") == before
    assert report["baseline"]["observed_case_count"] == 1
    assert report["cases"][0]["decision_influence"] == "NONE"
