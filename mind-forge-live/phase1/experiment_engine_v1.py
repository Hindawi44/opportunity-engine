from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts_v1 import DecisionVerdict, Experiment, MetricDirection, MetricSpec
from .creative_engine_v1 import CreativeEngineResult
from .critique_engine_v1 import CritiqueEngineResult
from .decision_engine_v1 import DecisionEngineResult


class ExperimentEngineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(min_length=1)
    selected_idea_ids: list[str] = Field(default_factory=list)
    experiments: list[Experiment] = Field(default_factory=list)
    executable_now: bool
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_experiment_scope(self) -> "ExperimentEngineResult":
        experiment_idea_ids = [item.idea_id for item in self.experiments]
        if len(experiment_idea_ids) != len(set(experiment_idea_ids)):
            raise ValueError("only one Phase 1 experiment may be emitted per selected idea")
        if self.executable_now:
            if set(experiment_idea_ids) != set(self.selected_idea_ids):
                raise ValueError("TEST_NOW must emit exactly one experiment per selected idea")
        elif self.experiments:
            raise ValueError("non-executable decisions must not emit runnable experiments")
        return self


class _ExperimentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    steps: tuple[str, ...]
    cost_ceiling: float
    time_ceiling_hours: float
    success_metrics: tuple[MetricSpec, ...]
    failure_metrics: tuple[MetricSpec, ...]
    stop_conditions: tuple[str, ...]
    data_to_record: tuple[str, ...]


_SPECS: dict[str, _ExperimentSpec] = {
    "bottleneck_redesign": _ExperimentSpec(
        steps=(
            "Choose one reversible workflow change aimed at the currently suspected bottleneck.",
            "Measure a small baseline sample before the change and a matched sample after the change.",
            "Compare total cycle time, queue movement, and rework rather than only the targeted step.",
        ),
        cost_ceiling=0.0,
        time_ceiling_hours=16.0,
        success_metrics=(
            MetricSpec(name="end_to_end_cycle_time_change", direction=MetricDirection.AT_MOST, threshold=-10.0, unit="percent"),
            MetricSpec(name="rework_rate_change", direction=MetricDirection.AT_MOST, threshold=0.0, unit="percentage_points"),
        ),
        failure_metrics=(
            MetricSpec(name="downstream_queue_growth", direction=MetricDirection.AT_MOST, threshold=0.0, unit="jobs"),
        ),
        stop_conditions=("Stop if the change creates a larger downstream queue or a quality/rework increase.",),
        data_to_record=("baseline cycle time", "post-change cycle time", "queue location", "rework events"),
    ),
    "standardization": _ExperimentSpec(
        steps=(
            "Draft three to five explicit standard packages with scope and exception rules.",
            "Classify a bounded historical or live sample against those packages without changing the real customer offer yet.",
            "Record fit, exceptions, re-quoting needs, and margin/effort variance.",
        ),
        cost_ceiling=0.0,
        time_ceiling_hours=8.0,
        success_metrics=(
            MetricSpec(name="package_fit_rate", direction=MetricDirection.AT_LEAST, threshold=70.0, unit="percent"),
            MetricSpec(name="exception_rate", direction=MetricDirection.AT_MOST, threshold=30.0, unit="percent"),
        ),
        failure_metrics=(
            MetricSpec(name="quality_loss_cases", direction=MetricDirection.AT_MOST, threshold=0.0, unit="cases"),
        ),
        stop_conditions=("Stop if standardization requires quality compromises or hides material profitable exceptions.",),
        data_to_record=("job type", "package match", "exception reason", "effort variance", "quality concern"),
    ),
    "data_feedback": _ExperimentSpec(
        steps=(
            "Define only the minimum fields linked to a pricing, capacity, routing, or offer decision.",
            "Capture those fields for a bounded sample or short operating window.",
            "At the end, require a written decision log showing which decision changed because of the captured signal.",
        ),
        cost_ceiling=0.0,
        time_ceiling_hours=168.0,
        success_metrics=(
            MetricSpec(name="decision_changes_from_data", direction=MetricDirection.AT_LEAST, threshold=1.0, unit="decisions"),
            MetricSpec(name="required_fields_completion", direction=MetricDirection.AT_LEAST, threshold=90.0, unit="percent"),
        ),
        failure_metrics=(
            MetricSpec(name="unused_collected_fields", direction=MetricDirection.AT_MOST, threshold=1.0, unit="fields"),
        ),
        stop_conditions=("Stop or shrink the dataset if fields are collected but do not affect any explicit decision.",),
        data_to_record=("job type", "lead time", "rework", "margin proxy", "demand source", "decision changed"),
    ),
}

_FALLBACK = _ExperimentSpec(
    steps=(
        "Run the Critique Engine low-cost test on the smallest reversible sample available.",
        "Measure one customer-value signal and one business-value signal.",
        "Compare the result against the falsification condition before expanding the test.",
    ),
    cost_ceiling=50.0,
    time_ceiling_hours=24.0,
    success_metrics=(
        MetricSpec(name="customer_value_signal", direction=MetricDirection.AT_LEAST, threshold=1.0, unit="positive_signal"),
        MetricSpec(name="business_value_signal", direction=MetricDirection.AT_LEAST, threshold=1.0, unit="positive_signal"),
    ),
    failure_metrics=(
        MetricSpec(name="critical_failure_events", direction=MetricDirection.AT_MOST, threshold=0.0, unit="events"),
    ),
    stop_conditions=("Stop immediately if the Critique Engine falsification condition is met.",),
    data_to_record=("customer-value signal", "business-value signal", "failure events", "unexpected effects"),
)


def design_experiments(
    creative: CreativeEngineResult,
    critique: CritiqueEngineResult,
    decision_result: DecisionEngineResult,
) -> ExperimentEngineResult:
    """Turn TEST_NOW selections into bounded falsifiable experiments.

    This stage designs tests; it does not execute them and therefore creates no
    outcome claims. TEST_AFTER_EVIDENCE/HOLD/REWORK/REJECT intentionally emit no
    runnable experiment until their gate is cleared.
    """

    decision = decision_result.decision
    selected = list(decision.selected_idea_ids)
    if decision.verdict is not DecisionVerdict.TEST_NOW:
        return ExperimentEngineResult(
            decision_id=decision.decision_id,
            selected_idea_ids=selected,
            experiments=[],
            executable_now=False,
            reason=f"Decision verdict is {decision.verdict.value}; Experiment Engine will not bypass that gate.",
        )

    ideas_by_id = {item.idea_id: item for item in creative.ideas}
    family_by_id = creative.mechanism_family_by_idea_id
    critique_by_id = {item.idea_id: item for item in critique.critiques}
    missing = set(selected) - set(ideas_by_id)
    if missing:
        raise ValueError(f"selected ideas missing from creative universe: {sorted(missing)}")
    if not set(selected).issubset(set(critique.survived_idea_ids)):
        raise ValueError("Experiment Engine may only test ideas that survived Devil's Advocate")

    experiments: list[Experiment] = []
    for idea_id in selected:
        family = family_by_id[idea_id]
        spec = _SPECS.get(family, _FALLBACK)
        critique_item = critique_by_id[idea_id]
        steps = list(spec.steps)
        steps.append(f"Use this Critique low-cost test as the execution anchor: {critique_item.low_cost_test}")

        experiments.append(
            Experiment(
                experiment_id=f"experiment-{idea_id}",
                idea_id=idea_id,
                hypothesis=(
                    f"The {family} mechanism creates measurable customer/business value without triggering the Critique falsification condition: "
                    f"{critique_item.falsification_test}"
                ),
                steps=steps,
                cost_ceiling=spec.cost_ceiling,
                time_ceiling_hours=spec.time_ceiling_hours,
                success_metrics=list(spec.success_metrics),
                failure_metrics=list(spec.failure_metrics),
                stop_conditions=list(spec.stop_conditions),
                data_to_record=list(spec.data_to_record),
                next_decision_if_passed="Retain the idea for the next evidence/decision cycle and increase confidence only from observed results.",
                next_decision_if_failed="Downgrade, rework, or reject the idea according to the recorded failure and return the lesson to Memory Engine.",
            )
        )

    return ExperimentEngineResult(
        decision_id=decision.decision_id,
        selected_idea_ids=selected,
        experiments=experiments,
        executable_now=True,
        reason="Decision is TEST_NOW and every selected idea passed Logic plus Devil's Advocate hard gates.",
    )
