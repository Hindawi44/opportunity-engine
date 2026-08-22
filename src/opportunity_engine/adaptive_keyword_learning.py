"""Conservative keyword learning from proven missed opportunities.

The module turns QUERY_GAP cases into candidate search patterns, then evaluates
those patterns against hidden ground-truth replay cases. V1 never edits live
query packs automatically: a candidate may become PROVEN, but activation still
requires an explicit later integration/review step.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
import re
from typing import Any, Callable, Mapping, Sequence

from opportunity_engine.missed_opportunity_learning import (
    MissedOpportunityCase,
    run_replay,
)

SCHEMA_VERSION = "adaptive-keyword-learning-1.1"
EVALUATION_SCOPES = {"SOURCE_CASE_REPLAY", "HOLDOUT_TRANSFER"}

# Cross-market commercial fragments are intentionally broad enough to detect
# compounds such as avviklingssalg, lagersalg, restlager, Insolvenzverkauf,
# utförsäljning, liquidation, etc. Frequency support is still required for
# ordinary vocabulary that does not contain one of these fragments.
_COMMERCIAL_FRAGMENTS = (
    "avvikling",
    "salg",
    "lager",
    "konkurs",
    "tømme",
    "opphør",
    "stock",
    "liquid",
    "clearance",
    "closing",
    "insolv",
    "auction",
    "auktion",
    "versteiger",
    "restpost",
    "auflösung",
    "aufloesung",
    "utförsälj",
    "utforsalj",
    "avveckling",
    "sv konkurs",
)

_STOPWORDS = {
    "dette",
    "denne",
    "med",
    "som",
    "fra",
    "for",
    "til",
    "og",
    "eller",
    "the",
    "and",
    "from",
    "with",
    "this",
    "that",
    "eine",
    "einer",
    "eines",
    "und",
    "oder",
    "mit",
    "von",
    "der",
    "die",
    "das",
    "ett",
    "och",
    "eller",
    "från",
    "med",
    "butikken",
    "butikk",
    "company",
    "selskap",
    "varer",
    "selges",
    "as",
}

_TOKEN_RE = re.compile(r"[^\W_]+(?:-[^\W_]+)*", flags=re.UNICODE)


@dataclass(frozen=True, slots=True)
class KeywordLearningCandidate:
    term: str
    market_code: str
    support_case_ids: tuple[str, ...]
    root_cause: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class KeywordEvaluationResult:
    term: str
    market_code: str
    status: str
    recovered_case_ids: tuple[str, ...]
    raw_hit_count: int
    verified_relevant_count: int
    precision: float
    min_recovered_cases: int
    min_precision: float
    automatic_activation: bool = False
    support_case_ids: tuple[str, ...] = ()
    evaluation_scope: str = "SOURCE_CASE_REPLAY"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


KeywordSearchCallback = Callable[[str, str], Sequence[Mapping[str, Any]]]


def _fold(value: object) -> str:
    return " ".join(str(value or "").casefold().split()).strip()


def _tokens(value: str) -> list[str]:
    return [token.casefold() for token in _TOKEN_RE.findall(value)]


def _commercial(term: str) -> bool:
    folded = term.casefold()
    return any(fragment in folded for fragment in _COMMERCIAL_FRAGMENTS)


def _active_query_text(active_queries: Sequence[str]) -> str:
    return "\n".join(
        _fold(query)
        for query in active_queries
        if str(getattr(query, "query_scope", "") or "").strip().upper()
        != "SIGNAL_ONLY"
    )


def _candidate_terms(text: str) -> set[str]:
    raw_tokens = _tokens(text)
    eligible_tokens = [
        token
        for token in raw_tokens
        if len(token) >= 4 and token not in _STOPWORDS
    ]
    terms: set[str] = set()
    for token in eligible_tokens:
        if _commercial(token):
            terms.add(token)

    # Build phrases only from tokens that were truly adjacent in the evidence.
    # Filtering first can invent adjacency (for example "avslutningssalg på alle"
    # becoming the false phrase "avslutningssalg alle").
    for left, right in zip(raw_tokens, raw_tokens[1:]):
        if len(left) < 4 or len(right) < 4:
            continue
        if left in _STOPWORDS or right in _STOPWORDS:
            continue
        phrase = f"{left} {right}"
        if len(phrase) <= 64 and _commercial(phrase):
            terms.add(phrase)
    return terms


def propose_query_gap_keywords(
    cases: Sequence[MissedOpportunityCase],
    *,
    active_queries: Sequence[str],
    max_candidates: int = 20,
) -> list[KeywordLearningCandidate]:
    """Propose bounded patterns only from diagnosed QUERY_GAP evidence.

    Exact terms already diagnosed by the Scout are proposed before noisier
    evidence-derived phrases, but they still go through the normal replay/shadow
    proof path. Signal-only Market Radar queries do not suppress a Core gap.
    """

    if max_candidates < 1:
        raise ValueError("max_candidates must be >= 1")

    active = _active_query_text(active_queries)
    support: dict[tuple[str, str], set[str]] = defaultdict(set)
    occurrences: Counter[tuple[str, str]] = Counter()
    diagnosed_keys: set[tuple[str, str]] = set()

    for raw_case in cases:
        case = raw_case if raw_case.root_cause else raw_case.with_diagnosis()
        if case.root_cause != "QUERY_GAP":
            continue

        for term in case.diagnosed_query_gap_terms:
            folded = _fold(term)
            if not folded or folded in active:
                continue
            key = (case.market_code.upper(), folded)
            support[key].add(case.case_id)
            occurrences[key] += 1
            diagnosed_keys.add(key)

        # Once a source miss has already been recovered or transfer-proven,
        # keep only its exact diagnosed terms available for any required
        # replication. Do not spend later budgets mining new evidence phrases
        # from a case whose learning objective has already been satisfied.
        if case.learning_status in {"RECOVERED", "TRANSFER_PROVEN"}:
            continue

        text = case.learning_evidence_text.strip()
        if not text:
            continue
        for term in _candidate_terms(text):
            folded = _fold(term)
            if not folded or folded in active:
                continue
            key = (case.market_code.upper(), folded)
            support[key].add(case.case_id)
            occurrences[key] += max(1, _fold(text).count(folded))

    candidates: list[KeywordLearningCandidate] = []
    for (market_code, term), case_ids in support.items():
        # A one-case candidate is allowed only when it carries a recognizable
        # commercial signal. This keeps proper names and generic prose out.
        if len(case_ids) < 2 and not _commercial(term):
            continue
        specificity_bonus = 3.0 if _commercial(term) else 0.0
        generalizability_bonus = 1.0 if " " not in term else 0.0
        diagnosed_bonus = 100.0 if (market_code, term) in diagnosed_keys else 0.0
        score = round(
            len(case_ids) * 10.0
            + diagnosed_bonus
            + min(occurrences[(market_code, term)], 5)
            + specificity_bonus
            + generalizability_bonus,
            3,
        )
        candidates.append(
            KeywordLearningCandidate(
                term=term,
                market_code=market_code,
                support_case_ids=tuple(sorted(case_ids)),
                root_cause="QUERY_GAP",
                score=score,
            )
        )

    candidates.sort(key=lambda item: (-item.score, item.term))
    return candidates[:max_candidates]


def _hit_matches_any_case(
    hit: Mapping[str, Any], cases: Sequence[MissedOpportunityCase]
) -> bool:
    for case in cases:
        replay = run_replay(case, lambda _context, one=hit: [one])
        if replay.recovered:
            return True
    return False


def evaluate_keyword_candidate(
    candidate: KeywordLearningCandidate,
    cases: Sequence[MissedOpportunityCase],
    search: KeywordSearchCallback,
    *,
    min_recovered_cases: int = 1,
    min_precision: float = 0.20,
    evaluation_scope: str = "SOURCE_CASE_REPLAY",
) -> KeywordEvaluationResult:
    """Shadow-test one keyword against hidden replay or holdout cases.

    SOURCE_CASE_REPLAY asks whether the pattern rediscovers the original miss.
    HOLDOUT_TRANSFER asks the harder generalization question: can a term learned
    from one miss discover an independent hidden opportunity that was not used
    to generate the term?
    """

    if min_recovered_cases < 1:
        raise ValueError("min_recovered_cases must be >= 1")
    if not 0.0 <= min_precision <= 1.0:
        raise ValueError("min_precision must be between 0 and 1")
    scope = str(evaluation_scope or "").strip().upper()
    if scope not in EVALUATION_SCOPES:
        raise ValueError(f"unsupported evaluation_scope: {evaluation_scope}")

    if scope == "HOLDOUT_TRANSFER":
        market_cases = [
            case
            for case in cases
            if case.market_code.upper() == candidate.market_code.upper()
            and case.stock_proven
        ]
    else:
        market_cases = [
            case
            for case in cases
            if case.market_code.upper() == candidate.market_code.upper()
            and (case.root_cause or case.with_diagnosis().root_cause) == "QUERY_GAP"
        ]

    raw = search(candidate.term, candidate.market_code.upper())
    hits = [item for item in raw if isinstance(item, Mapping)]

    recovered: list[str] = []
    for case in market_cases:
        replay_case = replace(
            case,
            learned_patterns=tuple(
                dict.fromkeys((*case.learned_patterns, candidate.term))
            ),
        )
        result = run_replay(replay_case, lambda _context, rows=hits: rows)
        if result.recovered:
            recovered.append(case.case_id)

    relevant_count = sum(
        1
        for item in hits
        if item.get("verified_relevant") is True
        or _hit_matches_any_case(item, market_cases)
    )
    raw_count = len(hits)
    precision = 0.0 if raw_count == 0 else round(relevant_count / raw_count, 6)

    if raw_count == 0:
        status = "INSUFFICIENT_EVIDENCE"
    elif len(recovered) < min_recovered_cases:
        status = "NOT_RECOVERED"
    elif precision < min_precision:
        status = "REJECTED_NOISY"
    else:
        status = "PROVEN"

    return KeywordEvaluationResult(
        term=candidate.term,
        market_code=candidate.market_code.upper(),
        status=status,
        recovered_case_ids=tuple(sorted(recovered)),
        raw_hit_count=raw_count,
        verified_relevant_count=relevant_count,
        precision=precision,
        min_recovered_cases=min_recovered_cases,
        min_precision=min_precision,
        automatic_activation=False,
        support_case_ids=candidate.support_case_ids,
        evaluation_scope=scope,
    )


def build_keyword_learning_report(
    candidates: Sequence[KeywordLearningCandidate],
    evaluations: Sequence[KeywordEvaluationResult],
) -> dict[str, Any]:
    """Return review-safe learning output; V1 never activates queries itself."""

    proven = [item for item in evaluations if item.status == "PROVEN"]
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_count": len(candidates),
        "evaluated_count": len(evaluations),
        "proven_count": len(proven),
        "candidate_terms": [item.to_dict() for item in candidates],
        "evaluations": [item.to_dict() for item in evaluations],
        "proven_terms_for_review": [item.term for item in proven],
        "automatic_activation": False,
        "production_query_mutation": False,
    }
