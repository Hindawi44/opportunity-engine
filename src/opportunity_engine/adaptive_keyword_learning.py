"""Conservative keyword learning from proven missed opportunities.

The module turns QUERY_GAP cases into candidate search patterns, then evaluates
those patterns against hidden ground-truth replay cases.  V1 never edits live
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

SCHEMA_VERSION = "adaptive-keyword-learning-1.0"

# Cross-market commercial fragments are intentionally broad enough to detect
# compounds such as avviklingssalg, lagersalg, restlager, Insolvenzverkauf,
# utförsäljning, liquidation, etc.  Frequency support is still required for
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
    return "\n".join(_fold(query) for query in active_queries)


def _candidate_terms(text: str) -> set[str]:
    tokens = [token for token in _tokens(text) if len(token) >= 4 and token not in _STOPWORDS]
    terms: set[str] = set()
    for token in tokens:
        if _commercial(token):
            terms.add(token)
    for left, right in zip(tokens, tokens[1:]):
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

    Company names and arbitrary one-off prose are not candidates merely because
    they appear in a missed listing.  V1 proposes either commercially shaped
    terms/phrases or, in future versions, terms with repeated cross-case support.
    When evidence supports both an atomic commercial term and a phrase containing
    it, the atomic term gets a small generalizability advantage so the bounded
    daily budget tests the reusable market pattern before one-off wording.
    """

    if max_candidates < 1:
        raise ValueError("max_candidates must be >= 1")

    active = _active_query_text(active_queries)
    support: dict[tuple[str, str], set[str]] = defaultdict(set)
    occurrences: Counter[tuple[str, str]] = Counter()

    for raw_case in cases:
        case = raw_case if raw_case.root_cause else raw_case.with_diagnosis()
        if case.root_cause != "QUERY_GAP":
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
        # commercial signal.  This keeps proper names and generic prose out.
        if len(case_ids) < 2 and not _commercial(term):
            continue
        specificity_bonus = 3.0 if _commercial(term) else 0.0
        generalizability_bonus = 1.0 if " " not in term else 0.0
        score = round(
            len(case_ids) * 10.0
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
) -> KeywordEvaluationResult:
    """Shadow-test one keyword against real hidden missed-opportunity cases."""

    if min_recovered_cases < 1:
        raise ValueError("min_recovered_cases must be >= 1")
    if not 0.0 <= min_precision <= 1.0:
        raise ValueError("min_precision must be between 0 and 1")

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
