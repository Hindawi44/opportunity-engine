import pytest

from opportunity_engine.ods import (
    BusinessBlueprint,
    ODSAnalysisResult,
    Stage,
    Status,
    USABLE_ALPHA_WORKFLOW,
    ValidationReport,
    build_alpha_engine,
    run_ods,
)


def test_run_ods_completes_current_alpha_flow() -> None:
    result = run_ods("أزياء", country="Norway", shortlist_size=5)

    assert isinstance(result, ODSAnalysisResult)
    assert result.session.status is Status.COMPLETED
    assert tuple(result.session.results) == USABLE_ALPHA_WORKFLOW
    assert result.discovered_count == 10
    assert len(result.ranked_opportunities) == 5
    assert result.ranked_opportunities[0].rank == 1
    assert isinstance(result.blueprint, BusinessBlueprint)
    assert isinstance(result.validation, ValidationReport)
    assert result.validation.opportunity_id == result.blueprint.opportunity.opportunity_id
    assert result.validation.recommended_decision == "TEST"
    assert result.validation.experiments
    assert result.session.audit_log[-1] == "session_completed"


def test_build_alpha_engine_stops_after_validation() -> None:
    engine = build_alpha_engine(shortlist_size=3)

    assert engine.workflow == (
        Stage.DISCOVERY,
        Stage.RANKING,
        Stage.BDNA,
        Stage.VALIDATION,
    )


def test_run_ods_respects_shortlist_size() -> None:
    result = run_ods("Fashion", country="Norway", shortlist_size=2)

    assert len(result.ranked_opportunities) == 2


def test_run_ods_rejects_unsupported_sector_with_clear_error() -> None:
    with pytest.raises(
        RuntimeError,
        match=r"fashion_discovery does not support subject: Agriculture",
    ):
        run_ods("Agriculture", country="Norway")


def test_run_ods_validates_empty_subject() -> None:
    with pytest.raises(ValueError, match="subject must not be empty"):
        run_ods("   ")
