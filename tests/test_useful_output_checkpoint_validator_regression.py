from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"


def test_runtime_validator_accepts_useful_only_domain_delivery() -> None:
    """The cleaned domain delivery no longer carries the legacy human-action block."""
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.index("- name: Validate checkpoint safety, coverage and lifecycle integrity")
    end = text.index("- name: Upload checkpoint and source evidence", start)
    validation = text[start:end]

    # The operator phone summary still owns the single bounded human action.
    assert 'summary.count("الإجراء البشري الوحيد:") != 1' in validation

    # The useful-only domain delivery intentionally contains opportunity rows only.
    # Runtime validation must not reject it for omitting the legacy action block.
    assert 'intelligence_text.count("الإجراء البشري الوحيد:") != 1' not in validation
    assert "Domain bulletin must contain exactly one human action" not in validation
