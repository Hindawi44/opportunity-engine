from __future__ import annotations

from hashlib import sha256

from pydantic import BaseModel, ConfigDict

from .contracts_v1 import ExpertMindOutput
from .creative_engine_v1 import CreativeEngineResult


class MindSpec(BaseModel):
    """A bounded analytical lens, not historical-person role-play."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mind_id: str
    lens: str
    primary_family: str
    secondary_families: tuple[str, ...]
    guiding_question: str
    assumption: str
    objection: str
    evidence_change: str


_MIND_SPECS: tuple[MindSpec, ...] = (
    MindSpec(
        mind_id="rockefeller",
        lens="Systems & Scale",
        primary_family="replication_licensing",
        secondary_families=("standardization", "b2b_embedding", "automation_intake"),
        guiding_question="Can the operating system scale without proportional dependence on one owner, craftsperson, or location?",
        assumption="Repeatable methods and quality controls can be codified enough to travel across operators or locations.",
        objection="Scale that outruns quality control can amplify defects and destroy trust faster than a local operating model.",
        evidence_change="Unit-level quality, training time, and variance data from at least two independent operators would materially change this view.",
    ),
    MindSpec(
        mind_id="rothschild",
        lens="Networks & Information",
        primary_family="data_feedback",
        secondary_families=("distribution_partnership", "b2b_embedding", "demand_aggregation"),
        guiding_question="Which information or network position compounds advantage before competitors can see it?",
        assumption="Small operational and demand datasets can reveal non-obvious channel, pricing, or workload patterns.",
        objection="Data collection is useless if it does not change a concrete decision or if the sample is too biased to generalize.",
        evidence_change="A measured link between captured signals and better pricing, routing, conversion, or capacity decisions would materially change this view.",
    ),
    MindSpec(
        mind_id="buffett",
        lens="Capital Allocation",
        primary_family="premium_speed",
        secondary_families=("standardization", "outcome_guarantee", "b2b_embedding"),
        guiding_question="Which idea can improve return on existing capacity before demanding large irreversible capital?",
        assumption="A time-sensitive customer segment exists and can pay a premium without requiring heavy new fixed assets.",
        objection="Revenue growth is unattractive if urgency work consumes scarce capacity and reduces total contribution margin.",
        evidence_change="Contribution margin, capacity displacement, and repeat-purchase data by service tier would materially change this view.",
    ),
    MindSpec(
        mind_id="walton",
        lens="Retail Efficiency",
        primary_family="demand_aggregation",
        secondary_families=("standardization", "mobile_access", "automation_intake"),
        guiding_question="How can volume be made cheaper and simpler to serve without lowering the customer-value floor?",
        assumption="Enough similar demand can be grouped in time or place to reduce handling and setup cost.",
        objection="Aggregation can create waiting, coordination overhead, or failed batches if demand density is weak.",
        evidence_change="Batch density, handling minutes per job, and customer wait-tolerance data would materially change this view.",
    ),
    MindSpec(
        mind_id="carnegie",
        lens="Operational Productivity",
        primary_family="bottleneck_redesign",
        secondary_families=("automation_intake", "standardization", "data_feedback"),
        guiding_question="Which constraint limits throughput, and can it be removed before adding labor or equipment?",
        assumption="A small number of workflow constraints create most avoidable delay, rework, or idle time.",
        objection="Local optimization can move the queue elsewhere and make the total system worse.",
        evidence_change="Cycle-time observations by workflow step plus rework and queue data would materially change this view.",
    ),
    MindSpec(
        mind_id="ford",
        lens="Standardization",
        primary_family="standardization",
        secondary_families=("automation_intake", "replication_licensing", "demand_aggregation"),
        guiding_question="What can become a repeatable specification while preserving the judgment that truly needs craft?",
        assumption="A meaningful share of work repeats often enough to support explicit packages and operating standards.",
        objection="Standardization can destroy value when customers are paying specifically for adaptation and judgment.",
        evidence_change="Job-mix frequency, exception rates, rework rates, and margin variance by job type would materially change this view.",
    ),
    MindSpec(
        mind_id="vanderbilt",
        lens="Distribution",
        primary_family="distribution_partnership",
        secondary_families=("mobile_access", "b2b_embedding", "demand_aggregation"),
        guiding_question="Can access to demand be controlled more cheaply by changing the route to the customer?",
        assumption="Adjacent businesses or concentrated locations already possess customer traffic that overlaps with the target need.",
        objection="Borrowed distribution becomes fragile when partners own the customer relationship and incentives are weak.",
        evidence_change="Partner lead volume, conversion, handoff quality, and acquisition cost versus direct channels would materially change this view.",
    ),
    MindSpec(
        mind_id="lauder",
        lens="Customer Experience",
        primary_family="outcome_guarantee",
        secondary_families=("premium_speed", "mobile_access", "adjacent_bundle"),
        guiding_question="Which uncertainty or friction most damages trust before, during, or after the service?",
        assumption="Reducing perceived risk and clarifying the promised outcome can increase willingness to buy or pay more.",
        objection="A guarantee that is broad, subjective, or operationally uncontrolled can increase disputes instead of trust.",
        evidence_change="Conversion, complaint, redo, willingness-to-pay, and retention data under a bounded guarantee would materially change this view.",
    ),
    MindSpec(
        mind_id="kroc",
        lens="Replication",
        primary_family="b2b_embedding",
        secondary_families=("replication_licensing", "standardization", "distribution_partnership"),
        guiding_question="Which model can repeat through a stable demand source with a teachable service unit?",
        assumption="A recurring B2B workflow can create repeatable volume and make the service unit easier to replicate.",
        objection="A repeatable process is not a repeatable business if one large account dominates economics or bargaining power.",
        evidence_change="Account concentration, repeat order cadence, onboarding effort, and unit economics across multiple B2B customers would materially change this view.",
    ),
    MindSpec(
        mind_id="jobs",
        lens="Product & Differentiation",
        primary_family="adjacent_bundle",
        secondary_families=("outcome_guarantee", "recurring_membership", "premium_speed"),
        guiding_question="Which concept creates a meaningfully different customer job-to-be-done rather than a marginal feature?",
        assumption="Customers value a coherent end-to-end solution more than a collection of unrelated add-ons.",
        objection="Bundling is not differentiation if the adjacent element is weak, confusing, or easy to copy without operational advantage.",
        evidence_change="Customer choice, willingness-to-pay, attach rate, and qualitative job-to-be-done interviews would materially change this view.",
    ),
)


def _jitter(mind_id: str, idea_id: str) -> float:
    digest = sha256(f"{mind_id}\x1f{idea_id}".encode("utf-8")).digest()
    return (int.from_bytes(digest[:2], "big") / 65535.0) * 0.08


def _score(spec: MindSpec, family: str, idea_id: str) -> float:
    if family == spec.primary_family:
        return 0.94
    if family in spec.secondary_families:
        rank = spec.secondary_families.index(family)
        return round(0.80 - (rank * 0.04), 4)
    return round(0.38 + _jitter(spec.mind_id, idea_id), 4)


def evaluate_with_expert_minds(creative: CreativeEngineResult) -> list[ExpertMindOutput]:
    """Assess one shared candidate universe through ten independent bounded lenses.

    This is an offline deterministic structural evaluator. It proves that the same
    canonical idea universe can be reviewed independently without cross-mind leakage.
    A later model-backed evaluator may replace score generation, but it must preserve
    the shared-universe, independence, and provenance contracts established here.
    """

    if len(_MIND_SPECS) != 10:
        raise RuntimeError("MIND FORGE requires exactly ten expert mind specifications")

    ideas_by_id = {idea.idea_id: idea for idea in creative.ideas}
    universe = list(ideas_by_id)
    family_map = creative.mechanism_family_by_idea_id
    if set(family_map) != set(universe):
        raise ValueError("Creative mechanism-family map must exactly cover the expert candidate universe")

    outputs: list[ExpertMindOutput] = []
    for spec in _MIND_SPECS:
        scores = {
            idea_id: _score(spec, family_map[idea_id], idea_id)
            for idea_id in universe
        }
        strongest_id = max(scores, key=lambda idea_id: (scores[idea_id], idea_id))
        strongest = ideas_by_id[strongest_id]
        strongest_family = family_map[strongest_id]

        outputs.append(
            ExpertMindOutput(
                mind_id=spec.mind_id,
                lens=spec.lens,
                assessed_idea_ids=universe,
                strongest_idea_id=strongest_id,
                independent_reasoning=[
                    (
                        f"Through the {spec.lens} lens, '{strongest.title}' is strongest because "
                        f"its {strongest_family} mechanism best matches this lens's primary decision rule."
                    ),
                    f"Guiding question: {spec.guiding_question}",
                ],
                assumptions=[spec.assumption],
                objections=[spec.objection],
                evidence_that_changes_view=[spec.evidence_change],
                support_scores=scores,
            )
        )

    return outputs
