from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field

from .contracts_v1 import Idea, Question, QuestionKind, QuestionStatus, TopicInput
from .question_generator_v1 import generate_questions


class CreativeEngineResult(BaseModel):
    """Canonical output of the deterministic Phase 1 creative expansion step."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    ideas: list[Idea] = Field(min_length=1)
    mechanism_family_by_idea_id: dict[str, str]
    mechanism_diversity_ratio: float = Field(ge=0.0, le=1.0)
    source_question_ids: list[str] = Field(default_factory=list)
    user_answer_required: bool = False


class _Pattern(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    family: str
    title: str
    mechanism: str
    customer_value: str
    business_value: str
    capabilities: tuple[str, ...]
    assumptions: tuple[str, ...]
    risks: tuple[str, ...]
    novelty: str
    question_keys: tuple[str, ...]


_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern(
        family="bottleneck_redesign",
        title="Bottleneck-first redesign for {topic}",
        mechanism=(
            "Map the highest-friction step in {topic}, remove or pre-resolve it, and reorganize the workflow around throughput rather than tradition."
        ),
        customer_value="Shorter waits, fewer handoffs, and a more predictable result.",
        business_value="Raises throughput and capacity before adding headcount or locations.",
        capabilities=("workflow measurement", "process redesign"),
        assumptions=("A small number of bottlenecks drive a disproportionate share of delay or cost.",),
        risks=("Optimizing the wrong bottleneck can shift delay elsewhere instead of improving the whole system.",),
        novelty="Changes the operating constraint itself rather than merely marketing the existing service differently.",
        question_keys=("bottlenecks", "value_leak"),
    ),
    _Pattern(
        family="standardization",
        title="Productized standard offer for {topic}",
        mechanism=(
            "Convert the most repeatable work in {topic} into a small menu of standardized packages with explicit scope, turnaround, and acceptance criteria."
        ),
        customer_value="Easier choice, clearer expectations, and less uncertainty about what will happen next.",
        business_value="Reduces quoting variance and enables repeatable execution, training, and margin control.",
        capabilities=("service design", "standard operating procedures"),
        assumptions=("Enough demand clusters into repeatable jobs to justify standard packages.",),
        risks=("Over-standardization can reject profitable edge cases or reduce perceived craftsmanship.",),
        novelty="Turns bespoke work into a repeatable product architecture instead of competing only on individual execution.",
        question_keys=("standardization", "replication"),
    ),
    _Pattern(
        family="premium_speed",
        title="Priority-speed tier for {topic}",
        mechanism=(
            "Create a deliberately capacity-limited priority lane for {topic} with a higher price, explicit deadline, and rules that protect normal-flow capacity."
        ),
        customer_value="A credible fast option when urgency matters more than lowest price.",
        business_value="Monetizes urgency while revealing the market value of time and queue position.",
        capabilities=("capacity reservation", "deadline control", "tiered pricing"),
        assumptions=("A subset of customers values speed enough to pay a meaningful premium.",),
        risks=("Poor capacity controls could cause premium jobs to damage standard delivery reliability.",),
        novelty="Monetizes time as a separate product dimension rather than discounting or adding generic features.",
        question_keys=("pricing", "bottlenecks"),
    ),
    _Pattern(
        family="recurring_membership",
        title="Recurring membership around {topic}",
        mechanism=(
            "Bundle recurring access, periodic service credits, priority handling, or maintenance benefits around {topic} into a membership with clear usage rules."
        ),
        customer_value="Convenience and predictable access without restarting the buying process each time.",
        business_value="Creates repeat demand, smoother revenue, and better visibility into future workload.",
        capabilities=("membership rules", "customer tracking", "recurring billing"),
        assumptions=("The underlying need recurs often enough for customers to value continuity.",),
        risks=("Unused benefits or excessive usage can make the offer feel unfair to either side.",),
        novelty="Changes the revenue relationship from one-off transactions to an ongoing service contract.",
        question_keys=("pricing", "adjacent_value"),
    ),
    _Pattern(
        family="outcome_guarantee",
        title="Outcome-guaranteed offer for {topic}",
        mechanism=(
            "Define one measurable customer outcome in {topic}, narrow eligibility, and attach a bounded guarantee or redo policy to that outcome."
        ),
        customer_value="Lower perceived risk because success criteria and remediation are explicit before purchase.",
        business_value="Supports premium positioning and forces operational quality to become measurable.",
        capabilities=("quality criteria", "eligibility screening", "remediation policy"),
        assumptions=("The chosen outcome can be objectively defined and controlled enough to guarantee within bounds.",),
        risks=("A vague guarantee can create open-ended liability or attract unsuitable cases.",),
        novelty="Competes on transferred risk and verified outcome instead of only price, speed, or features.",
        question_keys=("value_leak", "pricing"),
    ),
    _Pattern(
        family="distribution_partnership",
        title="Partner-distributed {topic}",
        mechanism=(
            "Place intake, referral, or fulfillment access for {topic} inside businesses that already serve the target customer, using a simple revenue-share or referral rule."
        ),
        customer_value="Accesses the service through a place or provider they already use and trust.",
        business_value="Acquires demand through existing traffic instead of relying only on direct marketing.",
        capabilities=("partner onboarding", "referral tracking", "service-level agreement"),
        assumptions=("Adjacent businesses serve overlapping customers and gain value from the partnership.",),
        risks=("Weak partner incentives or handoff quality can create low-volume, low-trust referrals.",),
        novelty="Changes the route to market by borrowing distribution rather than buying all customer acquisition directly.",
        question_keys=("distribution", "adjacent_value"),
    ),
    _Pattern(
        family="b2b_embedding",
        title="Embedded B2B workflow for {topic}",
        mechanism=(
            "Integrate {topic} as a recurring back-office capability for organizations whose own customer or employee workflow regularly creates the need."
        ),
        customer_value="The end user gets the result as part of a larger service instead of arranging it separately.",
        business_value="Creates higher-volume contractual demand with lower acquisition cost per transaction.",
        capabilities=("account management", "batch workflow", "B2B invoicing"),
        assumptions=("At least one business segment experiences the need frequently enough to outsource it.",),
        risks=("Large accounts can create concentration risk and negotiate margins aggressively.",),
        novelty="Moves from retail transactions to infrastructure-like service embedded inside another business process.",
        question_keys=("distribution", "underserved_segments"),
    ),
    _Pattern(
        family="automation_intake",
        title="Pre-qualified digital intake for {topic}",
        mechanism=(
            "Move repetitive diagnosis, information capture, photo/document collection, quoting inputs, and scheduling for {topic} before the human work begins."
        ),
        customer_value="Less waiting and fewer repeated explanations during the service interaction.",
        business_value="Cuts non-value-added labor and increases the share of staff time spent on skilled work.",
        capabilities=("intake form", "routing rules", "scheduling integration"),
        assumptions=("A meaningful portion of intake decisions can be standardized without unsafe automation.",),
        risks=("Poor intake questions can misclassify complex cases and create rework.",),
        novelty="Automates the information bottleneck while keeping skilled execution human where judgment matters.",
        question_keys=("bottlenecks", "standardization"),
    ),
    _Pattern(
        family="mobile_access",
        title="Mobile or on-site access for {topic}",
        mechanism=(
            "Bring intake, measurement, pickup, assessment, or selected execution steps for {topic} to concentrated customer locations on scheduled routes or pop-up windows."
        ),
        customer_value="Removes travel and coordination friction for customers with limited time or mobility.",
        business_value="Unlocks underserved demand pockets without committing to another permanent location.",
        capabilities=("route planning", "portable workflow", "appointment clustering"),
        assumptions=("Geographic or convenience friction suppresses enough demand to support clustered visits.",),
        risks=("Travel time and low route density can destroy unit economics.",),
        novelty="Changes the access geometry of the service instead of expanding through fixed-site overhead.",
        question_keys=("underserved_segments", "distribution"),
    ),
    _Pattern(
        family="demand_aggregation",
        title="Demand-aggregation layer for {topic}",
        mechanism=(
            "Aggregate similar {topic} jobs into scheduled batches, neighborhood drops, workplace collections, or campaign windows before fulfillment."
        ),
        customer_value="Convenient access and potentially better economics through coordinated demand.",
        business_value="Improves route, setup, purchasing, and labor efficiency by increasing batch density.",
        capabilities=("batch scheduling", "collection coordination", "demand forecasting"),
        assumptions=("Jobs can wait long enough to be grouped without harming customer value.",),
        risks=("Low participation can leave batches inefficient and disappoint customers expecting savings.",),
        novelty="Optimizes the economics by changing when demand is assembled, not just how each individual job is performed.",
        question_keys=("distribution", "bottlenecks"),
    ),
    _Pattern(
        family="circular_recovery",
        title="Recovery and reuse loop around {topic}",
        mechanism=(
            "Capture residual materials, rejected items, replaceable components, or post-service assets around {topic} and route them into repair, reuse, resale, donation, or material recovery."
        ),
        customer_value="A lower-waste option and possible residual-value recovery from items that would otherwise be discarded.",
        business_value="Creates secondary value streams from material or assets already passing through the operation.",
        capabilities=("sorting criteria", "secondary-channel partners", "traceability"),
        assumptions=("Residual outputs have enough recoverable value to exceed handling cost.",),
        risks=("Storage and sorting can consume more value than recovery creates.",),
        novelty="Creates a second economic loop from waste or residual assets rather than extracting all value from the primary transaction.",
        question_keys=("adjacent_value", "value_leak"),
    ),
    _Pattern(
        family="replication_licensing",
        title="Train-and-license method for {topic}",
        mechanism=(
            "Codify the repeatable method, quality checks, pricing logic, and operating playbook for {topic}, then train independent operators or partner locations to execute it under a bounded standard."
        ),
        customer_value="More consistent access to a trusted method across more locations or operators.",
        business_value="Scales know-how and brand reach with less direct fixed-cost expansion.",
        capabilities=("training curriculum", "quality audits", "licensing terms"),
        assumptions=("The core method can be taught and audited without depending entirely on one expert.",),
        risks=("Inconsistent partner execution can damage trust faster than direct expansion.",),
        novelty="Scales the operating system and know-how instead of scaling only owned labor and locations.",
        question_keys=("replication", "standardization"),
    ),
    _Pattern(
        family="data_feedback",
        title="Data-guided optimization for {topic}",
        mechanism=(
            "Capture a minimal dataset on job type, lead time, rework, margin proxy, demand source, and outcome in {topic}, then use it to change capacity, pricing, and offer design."
        ),
        customer_value="More reliable turnaround and service design as recurring failure patterns are removed.",
        business_value="Replaces intuition-only decisions with feedback on which work, channels, and operating choices actually perform.",
        capabilities=("simple data capture", "metric review", "decision cadence"),
        assumptions=("A small operational dataset is sufficient to reveal actionable patterns.",),
        risks=("Collecting too much data can create overhead without changing decisions.",),
        novelty="Builds a learning loop that continuously changes the business rather than treating each transaction as isolated.",
        question_keys=("bottlenecks", "value_leak"),
    ),
    _Pattern(
        family="adjacent_bundle",
        title="Adjacent-value bundle around {topic}",
        mechanism=(
            "Combine {topic} with one tightly adjacent service, product, preparation step, or aftercare need that the same customer already has before or after the core job."
        ),
        customer_value="Solves a broader job-to-be-done with fewer vendors, trips, and coordination steps.",
        business_value="Raises value per customer while using the same acquisition event and trust relationship.",
        capabilities=("adjacent-offer design", "cross-sell workflow", "partner or supply coordination"),
        assumptions=("The adjacent need is common enough and close enough to the core service to feel coherent.",),
        risks=("A weak adjacency can distract operations and dilute the core proposition.",),
        novelty="Expands the unit of value from one task to the surrounding customer workflow instead of adding unrelated extras.",
        question_keys=("adjacent_value", "underserved_segments"),
    ),
)


def _stable_id(topic: str, family: str) -> str:
    digest = sha256(f"{topic.strip().casefold()}\x1f{family}".encode("utf-8")).hexdigest()[:16]
    return f"idea-{digest}"


def _internal_question_index(questions: Iterable[Question]) -> dict[str, Question]:
    result: dict[str, Question] = {}
    for question in questions:
        if question.kind is not QuestionKind.INTERNAL:
            continue
        if question.status not in {QuestionStatus.OPEN, QuestionStatus.ANSWERED}:
            continue
        prefix = "q-internal-"
        key = question.question_id[len(prefix):] if question.question_id.startswith(prefix) else question.question_id
        result[key] = question
    return result


def _source_ids(pattern: _Pattern, question_index: dict[str, Question]) -> list[str]:
    matched = [question_index[key].question_id for key in pattern.question_keys if key in question_index]
    if matched:
        return matched
    # Fail open for provenance only when the caller supplied non-standard internal
    # question IDs. We still require at least one internal question and never use
    # a user-facing candidate as creative evidence/provenance.
    if question_index:
        return [next(iter(question_index.values())).question_id]
    raise ValueError("Creative Engine requires at least one internal Question")


def generate_ideas(
    topic: TopicInput,
    questions: Iterable[Question] | None = None,
) -> CreativeEngineResult:
    """Expand a raw topic into a structurally diverse canonical Idea set.

    This Phase 1 implementation is deliberately deterministic and zero-cost. It
    proves the orchestration contract: TopicInput -> internally generated Questions
    -> diverse canonical Ideas, without requiring a user-supplied idea or a paid
    model call. Later model-driven creativity can replace candidate generation while
    retaining these diversity/provenance guardrails.
    """

    question_list = list(questions) if questions is not None else generate_questions(topic)
    question_index = _internal_question_index(question_list)
    if not question_index:
        raise ValueError("Creative Engine cannot run without internally generated questions")

    ideas: list[Idea] = []
    families: dict[str, str] = {}
    used_question_ids: set[str] = set()

    for pattern in _PATTERNS:
        idea_id = _stable_id(topic.topic, pattern.family)
        source_ids = _source_ids(pattern, question_index)
        used_question_ids.update(source_ids)

        idea = Idea(
            idea_id=idea_id,
            title=pattern.title.format(topic=topic.topic),
            core_mechanism=pattern.mechanism.format(topic=topic.topic),
            customer_value=pattern.customer_value,
            business_value=pattern.business_value,
            required_capabilities=list(pattern.capabilities),
            assumptions=list(pattern.assumptions),
            risks=list(pattern.risks),
            novelty_reason=pattern.novelty,
            source_question_ids=source_ids,
        )
        ideas.append(idea)
        families[idea_id] = pattern.family

    unique_families = len(set(families.values()))
    diversity_ratio = unique_families / len(ideas)

    return CreativeEngineResult(
        topic=topic.topic,
        ideas=ideas,
        mechanism_family_by_idea_id=families,
        mechanism_diversity_ratio=diversity_ratio,
        source_question_ids=sorted(used_question_ids),
        user_answer_required=False,
    )
