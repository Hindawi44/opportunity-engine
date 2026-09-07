# MIND FORGE — Architecture V1

## 1. Purpose

MIND FORGE is not primarily a deal checker. It is an idea-generation and idea-refinement system.

The user may provide only a raw topic, domain, or problem. The system must expand that seed into questions, hypotheses, opportunities, business models, and experiments, then subject them to structured criticism, evidence, logic, ranking, and learning.

Core doctrine:

> The user gives the seed, not the whole tree.

And:

> MIND FORGE does not search for the prettiest idea. It searches for the strongest idea that can survive criticism and testing.

Canonical flow:

Problem / Topic → Creative Generation → Logic → Expert Council → Adversarial Critique → Evidence → Decision → Experiment → Learning

---

## 2. Two-Plan Architecture

### PLAN A — Thinking Core

PLAN A starts immediately even with sparse input.

Responsibilities:
- understand the raw topic;
- generate useful internal questions;
- create a broad and diverse idea space;
- produce competing hypotheses and business models;
- let multiple expert minds inspect the same problem from different mental models;
- eliminate weak or redundant ideas;
- preserve genuinely different strategic paths.

PLAN A must not wait for perfect data before it starts thinking.

### PLAN B — Reality, Research, and Evidence

PLAN B activates when an idea or decision depends on facts that are not yet known.

Responsibilities:
- identify which missing facts materially affect the idea;
- ask the user only high-value questions;
- use external tools and open sources when appropriate;
- distinguish facts, estimates, assumptions, and unknowns;
- quantify uncertainty;
- return verified evidence to the reasoning system;
- prevent unsupported claims from becoming accepted facts.

PLAN B must not collect data merely because it is available. Every data request must have a reason.

Rule:

> Do not request data before knowing why the data matters.

---

## 3. High-Level System Map

```text
┌──────────────────────────────┐
│ User Seed                    │
│ topic / problem / question   │
└──────────────┬───────────────┘
               │
               v
┌──────────────────────────────┐
│ 1. Intake & Framing Engine   │
└──────────────┬───────────────┘
               │
               v
┌──────────────────────────────┐
│ 2. Question Generator        │
│ Internal + user-facing       │
└──────────────┬───────────────┘
               │
      ┌────────┴─────────┐
      │                  │
      v                  v
┌───────────────┐   ┌──────────────────┐
│ PLAN A        │   │ PLAN B           │
│ Thinking Core │   │ Reality / Tools  │
└──────┬────────┘   └────────┬─────────┘
       │                     │
       v                     v
┌───────────────┐   ┌──────────────────┐
│ Creative      │   │ Research Router  │
│ Engine        │   │ + Tool Layer     │
└──────┬────────┘   └────────┬─────────┘
       │                     │
       v                     v
┌───────────────┐   ┌──────────────────┐
│ 10 Expert     │   │ Evidence Engine  │
│ Minds         │   └────────┬─────────┘
└──────┬────────┘            │
       │                     │
       └──────────┬──────────┘
                  v
         ┌──────────────────┐
         │ Logic Engine     │
         └────────┬─────────┘
                  v
         ┌──────────────────┐
         │ Devil's Advocate │
         └────────┬─────────┘
                  v
         ┌──────────────────┐
         │ Synthesis Engine │
         └────────┬─────────┘
                  v
         ┌──────────────────┐
         │ Decision Engine  │
         └────────┬─────────┘
                  v
         ┌──────────────────┐
         │ Experiment Engine│
         └────────┬─────────┘
                  v
         ┌──────────────────┐
         │ Memory Engine    │
         └──────────────────┘
```

---

## 4. Engine Responsibilities

## 4.1 Intake & Framing Engine

Input can be extremely small, for example:

> "Clothing alterations"

The Intake Engine should infer only the obvious domain and avoid inventing constraints.

Output fields:
- raw_seed
- normalized_topic
- known_constraints
- unknown_constraints
- initial_scope
- ambiguity_flags

It must not force the user into a long questionnaire.

---

## 4.2 Question Generator

This engine creates two classes of questions.

### Internal Questions
Questions the system can explore itself without interrupting the user.

Examples:
- Where does value leak in this business?
- Which customer segments are underserved?
- Which steps can be standardized?
- Which bottlenecks limit growth?
- Which adjacent services have asymmetric upside?
- What would make this model repeatable in another city?

### User-Facing Questions
Questions that should be asked only when the answer materially changes the idea space or the decision.

Examples:
- What capital range is available?
- What risk level is acceptable?
- Is the goal local profitability or multi-city expansion?
- How much owner time may the model consume?

The Question Generator must score each possible question by expected information gain.

Suggested rule:

`Ask user only if Expected Information Gain > Interruption Cost.`

---

## 4.3 Creative Engine

Purpose: generate a wide opportunity space before converging.

Requirements:
- create materially different ideas, not paraphrases;
- include incremental, operational, platform, network, product, service, pricing, distribution, partnership, automation, and business-model ideas where relevant;
- separate ideas from facts;
- mark assumptions explicitly;
- avoid premature rejection.

Suggested V1 target:
- generate 12–20 raw ideas;
- cluster duplicates;
- preserve at least 8 materially distinct candidates before expert review.

Each idea should contain:
- idea_id
- title
- core_mechanism
- customer_value
- business_value
- required_capabilities
- key_assumptions
- key_risks
- novelty_reason

---

## 4.4 The 10 Expert Minds

The minds are not literal simulations or quotations of historical people. They are distinct analytical lenses.

Recommended V1 mental models:

1. **Systems & Control Mind**
   - standardization, process control, repeatability, operating discipline.

2. **Information & Network Mind**
   - information advantage, referrals, partnerships, distribution networks, relationship leverage.

3. **Capital Efficiency Mind**
   - return on capital, return on time, margin quality, downside protection.

4. **Scale & Throughput Mind**
   - volume, unit economics, capacity, queue design, cost-to-serve.

5. **Productivity Mind**
   - labor specialization, bottlenecks, delegation, expert-time protection.

6. **Standardization Mind**
   - repeatable workflows, service recipes, quality control, predictable cycle time.

7. **Distribution & Flow Mind**
   - where customers originate, where demand flows, channel capture, location advantage.

8. **Customer Experience Mind**
   - trust, service quality, communication, retention, perceived value.

9. **Replication Mind**
   - training, franchisability, branch replication, owner-independence.

10. **Differentiation Mind**
   - category design, brand, premium value, unique positioning, defensibility.

Each mind must:
- evaluate independently first;
- create or modify candidate ideas;
- state its assumptions;
- identify the strongest idea through its own lens;
- identify what evidence would change its opinion.

This prevents groupthink.

---

## 4.5 Logic Engine

The Logic Engine checks internal consistency before external evidence is considered decisive.

Checks include:
- arithmetic consistency;
- causal coherence;
- contradictory assumptions;
- impossible dependencies;
- unrealistic capacity assumptions;
- unit economics;
- sequencing dependencies;
- risk asymmetry;
- owner/time constraints;
- scalability claims.

It should not reject a creative idea merely because data is missing. Instead it may label it:
- LOGIC_PASS
- LOGIC_PASS_WITH_ASSUMPTIONS
- LOGIC_FAIL
- NEEDS_QUANTIFICATION

---

## 4.6 Devil's Advocate

Purpose: actively try to kill weak ideas.

Attack dimensions:
- demand failure;
- operational fragility;
- hidden cost;
- customer resistance;
- legal/regulatory dependency;
- competitive imitation;
- owner bottleneck;
- capital intensity;
- poor timing;
- unrealistic adoption;
- single-point-of-failure risk.

For every top candidate, the Devil's Advocate must answer:
1. What is the most likely reason this fails?
2. What hidden assumption is doing the most work?
3. What evidence would falsify the idea?
4. What low-cost test could expose the weakness quickly?

---

## 4.7 Research Router & Tool Layer

The system should not browse blindly. It should create a research request tied to a decision variable.

Possible tools:
- Web Search
- Maps / Places
- Public statistics
- Open data portals
- APIs
- Calculators
- User files and spreadsheets
- Internal business records
- Market databases where available

Research request schema:
- research_question
- why_it_matters
- decision_variable
- preferred_source_type
- freshness_required
- geographic_scope
- acceptable_confidence

Examples:

Bad request:
> "Search everything about tailoring in Norway."

Good request:
> "Estimate whether a pickup-and-return alteration service in Namsos could acquire enough local demand to cover two driver hours per day. Find local population density, travel distances, competing alteration businesses, and likely customer concentration."

---

## 4.8 Evidence Engine

Every material claim should be classified as one of:
- VERIFIED_FACT
- STRONG_EVIDENCE
- WEAK_EVIDENCE
- ESTIMATE
- ASSUMPTION
- UNKNOWN
- CONFLICTING_EVIDENCE

Evidence records should preserve provenance:
- claim_id
- claim_text
- source
- source_type
- publication_date
- retrieval_date
- geography
- confidence
- contradiction_notes

Rule:

> Creative freedom is allowed. Unsupported certainty is not.

---

## 4.9 Synthesis Engine

The Synthesis Engine combines the diverse outputs without flattening disagreement.

Responsibilities:
- merge duplicate ideas;
- preserve minority ideas with strong asymmetric upside;
- summarize expert disagreement;
- identify key assumptions that drive ranking;
- produce a compact candidate set.

Suggested V1 funnel:
- 12–20 raw ideas
- 8+ distinct ideas after clustering
- 5 semifinalists
- 3 finalists
- 1 primary candidate + 1 optional challenger

---

## 4.10 Decision Engine

The Decision Engine ranks ideas using evidence-aware scoring.

Suggested dimensions:
- Customer Value
- Economic Potential
- Feasibility
- Capital Efficiency
- Time to Test
- Scalability
- Defensibility
- Evidence Strength
- Downside Risk
- Strategic Fit

Scores should never hide uncertainty.

Each finalist should include:
- score
- confidence
- evidence coverage
- key assumptions
- unresolved unknowns
- reason for rank

Possible verdicts:
- TEST_NOW
- TEST_AFTER_EVIDENCE
- HOLD
- REWORK
- REJECT

The system should not convert a low-evidence high-score idea into a confident recommendation.

---

## 4.11 Experiment Engine

The output of MIND FORGE should be a testable action, not only prose.

Each experiment should define:
- hypothesis
- smallest useful test
- cost ceiling
- time ceiling
- success metric
- failure metric
- stop condition
- data to record
- next decision if passed
- next decision if failed

Priority:

> Prefer cheap tests that destroy bad ideas quickly.

---

## 4.12 Memory Engine

Memory stores learning from actual outcomes.

Memory types:
- user constraints and preferences;
- historical idea evaluations;
- experiments run;
- actual outcome vs predicted outcome;
- expert-mind calibration;
- recurring failure patterns;
- reliable source types;
- domain-specific heuristics.

The Memory Engine should not merely save chat history. It should save structured learning.

Example:
- Idea predicted success: 78%
- Experiment result: failed
- Failure reason: customer acquisition cost
- Lesson: Distribution Mind underweighted travel distance
- Future effect: increase weight on local density for similar service models

---

## 5. Adaptive Questioning Protocol

MIND FORGE may ask the user questions, but it should minimize interruption.

Question priority should be based on:
- how much the answer changes ranking;
- whether the system can obtain the answer from evidence instead;
- whether the answer is personal/private/user-specific;
- cost of proceeding under uncertainty;
- reversibility of the next action.

### Ask the user when:
- capital limit is decision-critical;
- risk tolerance is personal;
- time availability is personal;
- strategic goal is ambiguous;
- required constraints cannot be inferred or researched safely.

### Research instead when:
- competitor presence is public;
- population or geographic information is public;
- regulations are public;
- market facts can be sourced externally;
- prices are publicly observable.

### Continue under uncertainty when:
- the missing fact does not materially alter early ideation;
- cheap reversible experiments exist;
- multiple scenarios can be produced.

---

## 6. Internal State Machine

Suggested V1 states:

```text
SEED_RECEIVED
   ↓
FRAMED
   ↓
QUESTIONS_GENERATED
   ↓
IDEAS_GENERATED
   ↓
EXPERT_REVIEWED
   ↓
LOGIC_CHECKED
   ↓
CRITICIZED
   ↓
RESEARCH_NEEDED? ──yes──> RESEARCHING
   │                         ↓
   │                    EVIDENCE_READY
   └────────────no───────────┘
              ↓
SYNTHESIZED
   ↓
RANKED
   ↓
EXPERIMENT_DESIGNED
   ↓
WAITING_FOR_RESULT
   ↓
OUTCOME_RECORDED
   ↓
MEMORY_UPDATED
```

The state machine should make the run auditable and resumable.

---

## 7. Data Objects for V1

Minimum structured objects:

### Seed
- seed_id
- raw_text
- domain
- timestamp

### Constraint
- name
- value
- source: USER / INFERRED / RESEARCHED
- confidence

### Idea
- idea_id
- title
- mechanism
- assumptions[]
- risks[]
- scores{}
- status

### Expert Review
- mind_id
- idea_id
- support_level
- critique
- suggested_modification
- evidence_needed[]

### Evidence Claim
- claim_id
- idea_id
- claim
- classification
- source
- confidence

### Decision
- finalists[]
- selected_idea
- verdict
- confidence
- unresolved_unknowns[]

### Experiment
- experiment_id
- idea_id
- hypothesis
- steps[]
- budget_limit
- success_metric
- stop_rule
- outcome

### Memory Record
- run_id
- prediction
- actual_outcome
- lesson
- calibration_update

---

## 8. Orchestration Rules

The Orchestrator controls sequence, budgets, and stopping conditions.

Rules for V1:
1. Creative generation happens before aggressive filtering.
2. Expert minds review independently before seeing group consensus.
3. Logic checks cannot invent evidence.
4. Evidence checks cannot kill an idea only because proof is not yet available; they may downgrade confidence.
5. Devil's Advocate attacks finalists, not every trivial idea equally.
6. User questions are minimized through information-gain scoring.
7. Tool calls must be linked to explicit research questions.
8. Decision must expose uncertainty.
9. Every TEST_NOW verdict must include a concrete experiment.
10. Every completed experiment must feed Memory.

---

## 9. Cost and Tool Budgeting

MIND FORGE should have a run budget.

Possible limits:
- max model requests;
- max tokens;
- max web/tool requests;
- max elapsed time;
- max paid external API cost.

Budget priority order:
1. preserve Creative generation;
2. preserve Logic;
3. preserve Devil's Advocate for finalists;
4. preserve Evidence on decision-critical claims;
5. preserve Decision and Experiment;
6. degrade low-value supplementary research first.

No automatic paid recurring execution in V1.

---

## 10. Guardrails Against Project Drift

MIND FORGE V1 must not become:
- a generic chatbot;
- only a BUY/HOLD/REJECT deal checker;
- a long questionnaire;
- an uncontrolled web crawler;
- a single-agent answer generator pretending to be a council;
- a system that treats fictional expert personas as authoritative historical quotes;
- a system that hides uncertainty behind scores;
- a system that produces only analysis without an experiment.

---

## 11. Example Run — Seed Only

User input:

> "Clothing alterations"

Expected behavior:

1. Intake frames the domain.
2. Question Generator creates internal questions without interrupting immediately.
3. Creative Engine produces 12–20 different opportunities.
4. 10 Expert Minds inspect, mutate, or add ideas.
5. Logic Engine removes incoherent paths.
6. Devil's Advocate attacks the strongest candidates.
7. Research Router identifies only decision-critical unknowns.
8. The system asks the user only if a personal constraint such as capital or risk materially changes ranking.
9. Evidence Engine verifies public claims.
10. Synthesis reduces the field to 3 finalists.
11. Decision selects the strongest test candidate.
12. Experiment Engine produces a cheap practical test.
13. After the user runs the test, Memory stores predicted vs actual outcome.

The user should never need to invent the full business idea before MIND FORGE can work.

---

## 12. V1 Success Criteria

MIND FORGE V1 succeeds only if it can demonstrate all of the following:

### Idea Generation
- Accept a seed as short as one topic.
- Produce at least 8 materially distinct viable ideas after clustering.
- Avoid simple paraphrase inflation.

### Multi-Mind Reasoning
- 10 minds produce meaningfully different analyses.
- Disagreement is visible and preserved.
- Consensus is not forced prematurely.

### Adaptive Questioning
- The system can proceed with incomplete data.
- It asks only high-value user questions.
- It prefers public research for public facts.

### Evidence Discipline
- Claims are labeled as fact, estimate, assumption, or unknown.
- Sources are attached to material verified claims.
- Unsupported assumptions lower confidence.

### Decision Quality
- Weak ideas are eliminated by explicit reasons.
- Top ideas have visible tradeoffs.
- Ranking includes uncertainty.

### Experimentation
- The selected idea has a low-cost, measurable test.
- Success and failure criteria are predeclared.

### Learning
- Actual outcomes can update structured memory and future calibration.

---

## 13. Build Order After Architecture Approval

No implementation should begin until this architecture is accepted.

Recommended build sequence:

**Phase 1 — Contracts and schemas**
- Seed
- Idea
- ExpertReview
- EvidenceClaim
- Decision
- Experiment
- MemoryRecord

**Phase 2 — Orchestrator skeleton**
- state machine
- run budgets
- logging
- deterministic test harness

**Phase 3 — PLAN A**
- Question Generator
- Creative Engine
- 10 Expert Minds
- Logic Engine
- Devil's Advocate
- Synthesis Engine

**Phase 4 — PLAN B**
- Research Router
- Tool Layer
- Evidence Engine
- Adaptive Questioning

**Phase 5 — Decision and Experiment**
- Decision Engine
- Experiment Engine

**Phase 6 — Memory and calibration**
- outcome storage
- predicted-vs-actual comparison
- expert calibration

**Phase 7 — Evaluation**
- open-ended seed tests
- adversarial tests
- sparse-input tests
- no-evidence tests
- disagreement tests
- budget-degradation tests

---

## 14. First Canonical Evaluation

The first canonical V1 evaluation should use only this seed:

> "Clothing alterations"

No supplied deal.
No prewritten candidate ideas.
No forced answer format that leaks expected solutions.

The evaluation should measure:
- idea diversity;
- expert disagreement;
- quality of critique;
- quality of evidence requests;
- number and usefulness of user-facing questions;
- strength of finalists;
- quality and cost of the final experiment.

This test is the clearest proof that MIND FORGE is functioning as an idea forge rather than merely a decision checker.
