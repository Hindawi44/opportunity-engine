from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
ARCHIVED = ROOT / "docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt"


def _legacy_validation() -> str:
    text = ARCHIVED.read_text(encoding="utf-8")
    start = text.index("- name: Validate checkpoint safety, coverage and lifecycle integrity")
    end = text.index("- name: Upload checkpoint and source evidence", start)
    return text[start:end]


def test_legacy_runtime_validator_preserved_for_historical_artifacts() -> None:
    validation = _legacy_validation()
    assert 'summary.count("الإجراء البشري الوحيد:") != 1' in validation
    assert 'intelligence_text.count("الإجراء البشري الوحيد:") != 1' not in validation
    assert "Domain bulletin must contain exactly one human action" not in validation


def test_six_market_validation_is_archived_and_absent_from_active_workflow() -> None:
    validation = _legacy_validation()
    active = ACTIVE.read_text(encoding="utf-8")
    assert '"NO", "SE", "DE", "FR", "IT", "NL"' in validation
    assert 'intelligence.get("market_coverage") != ["NO", "SE", "DE"]' not in validation
    assert '"NO", "SE", "DE", "FR", "IT", "NL"' not in active
    assert active.startswith("name: Norway Opportunity Hunter\n")


def test_historical_query_decision_validator_is_not_reused_as_new_proof() -> None:
    validation = _legacy_validation()
    active = ACTIVE.read_text(encoding="utf-8")
    assert '"HUMAN_DECISION_APPLIED"' in validation
    assert '"HUMAN_DECISION_APPLIED"' not in active


def test_historical_challenge_state_validator_is_preserved_but_not_scheduled() -> None:
    validation = _legacy_validation()
    active = ACTIVE.read_text(encoding="utf-8")
    assert 'state.get("status") == "HUMAN_DECISION_APPLIED"' in validation
    assert 'state.get("remaining_independent_checkpoint_days") != 0' in validation
    assert "remaining_independent_checkpoint_days" not in active
