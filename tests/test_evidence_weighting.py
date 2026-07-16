import pytest

from opportunity_engine.ods import calculate_ssb_adjustment


def test_ssb_adjustment_is_bounded_and_transparent() -> None:
    result = calculate_ssb_adjustment(
        base_score=73.23,
        category="inventory",
        evidence_score=90.0,
    )

    assert result.adjustment == 2.7
    assert result.final_score == 75.93
    assert result.relevance == 1.0
    assert "no growth" in result.reason.lower()


def test_less_relevant_category_receives_smaller_bonus() -> None:
    inventory = calculate_ssb_adjustment(
        base_score=70.0,
        category="inventory",
        evidence_score=80.0,
    )
    logistics = calculate_ssb_adjustment(
        base_score=70.0,
        category="logistics",
        evidence_score=80.0,
    )

    assert inventory.adjustment > logistics.adjustment


def test_adjustment_never_exceeds_one_hundred() -> None:
    result = calculate_ssb_adjustment(
        base_score=99.5,
        category="inventory",
        evidence_score=100.0,
    )

    assert result.final_score == 100.0


def test_invalid_evidence_score_is_rejected() -> None:
    with pytest.raises(ValueError, match="evidence_score"):
        calculate_ssb_adjustment(
            base_score=70.0,
            category="inventory",
            evidence_score=120.0,
        )
