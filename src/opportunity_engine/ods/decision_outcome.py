from __future__ import annotations

from .decision import ExecutiveDecision, OpportunityDecisionResult
from .models import LifecycleState, OpportunityCandidate

_DECISION_TARGETS = {
    ExecutiveDecision.GO: LifecycleState.EXECUTION,
    ExecutiveDecision.WAIT: LifecycleState.MONITORING,
    ExecutiveDecision.REJECT: LifecycleState.ARCHIVED,
}


def apply_decision_outcome(
    opportunity: OpportunityCandidate,
    decision_result: OpportunityDecisionResult,
) -> OpportunityCandidate:
    if opportunity.lifecycle_state is not LifecycleState.DECISION_CANDIDATE:
        raise ValueError(
            "decision outcome requires lifecycle state decision_candidate; "
            f"received {opportunity.lifecycle_state.value}"
        )
    if decision_result.opportunity_id != opportunity.opportunity_id:
        raise ValueError("decision outcome must reference the same opportunity")
    if decision_result.lifecycle_state is not LifecycleState.DECISION_CANDIDATE:
        raise ValueError("decision result must originate from a decision_candidate")

    return opportunity.transition_to(_DECISION_TARGETS[decision_result.report.decision])
