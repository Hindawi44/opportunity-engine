"""Missed-opportunity learning primitives.

V1 is deliberately offline and conservative.  It does not mutate production
queries, source manifests, or ranking policy.  It records a known miss, traces
where the opportunity fell out of the pipeline, diagnoses the first failed
stage, and replays a learned strategy without exposing the hidden ground truth
to the discovery callback.

The intended loop is:

    MISS -> EXPLAIN -> LEARN -> REPLAY -> PROVE

A learning is only considered recovered when replay rediscovers the hidden
company or URL.  This makes real missed opportunities regression fixtures
instead of one-off patches.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

SCHEMA_VERSION = "missed-opportunity-learning-loop-1.0"

ROOT_CAUSES = (
    "QUERY_GAP",
    "SOURCE_GAP",
    "RETRIEVAL_GAP",
    "TIMING_GAP",
    "PARSER_GAP",
    "ENTITY_LINK_GAP",
    "CLASSIFICATION_GAP",
    "VERIFICATION_GAP",
    "RANKING_GAP",
    "REPORTING_GAP",
)


@dataclass(frozen=True, slots=True)
class DiscoveryTrace:
    """Tri-state trace of one opportunity through the discovery pipeline.

    ``True`` means the stage passed, ``False`` means the stage is the observed
    failure, and ``None`` means the stage was not reached or is unknown.
    """

    query_generated: bool | None = None
    search_hit: bool | None = None
    retrieved: bool | None = None
    parsed: bool | None = None
    entity_linked: bool | None = None
    classified_relevant: bool | None = None
    verified: bool | None = None
    ranked: bool | None = None
    reported: bool | None = None
    timely_discovery: bool | None = None

    def to_dict(self) -> dict[str, bool | None]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DiscoveryTrace":
        allowed = cls.__dataclass_fields__
        values = {
            key: value
            for key, value in payload.items()
            if key in allowed and (isinstance(value, bool) or value is None)
        }
        return cls(**values)


def diagnose_root_cause(trace: DiscoveryTrace) -> str | None:
    """Return the first proven failure in pipeline order.

    This is intentionally deterministic rather than LLM-generated.  V1 should
    first establish trustworthy failure labels before any adaptive policy is
    allowed to change live search behaviour.
    """

    ordered_checks = (
        (trace.query_generated, "QUERY_GAP"),
        (trace.search_hit, "SOURCE_GAP"),
        (trace.retrieved, "RETRIEVAL_GAP"),
        (trace.timely_discovery, "TIMING_GAP"),
        (trace.parsed, "PARSER_GAP"),
        (trace.entity_linked, "ENTITY_LINK_GAP"),
        (trace.classified_relevant, "CLASSIFICATION_GAP"),
        (trace.verified, "VERIFICATION_GAP"),
        (trace.ranked, "RANKING_GAP"),
        (trace.reported, "REPORTING_GAP"),
    )
    for value, reason in ordered_checks:
        if value is False:
            return reason
    return None


@dataclass(frozen=True, slots=True)
class MissedOpportunityCase:
    """Ground-truth record for an opportunity the engine missed."""

    case_id: str
    market_code: str
    discovered_by: str
    observed_at: datetime
    opportunity_type: str
    stock_proven: bool
    ground_truth_company: str
    ground_truth_url: str
    trace: DiscoveryTrace
    learning_evidence_text: str = ""
    diagnosed_query_gap_terms: tuple[str, ...] = ()
    learned_patterns: tuple[str, ...] = ()
    root_cause: str | None = None
    learning_status: str = "PENDING"
    repeat_miss: bool = False

    def with_diagnosis(self) -> "MissedOpportunityCase":
        cause = diagnose_root_cause(self.trace)
        return replace(
            self,
            root_cause=cause,
            learning_status="DIAGNOSED" if cause else self.learning_status,
        )

    def replay_context(self) -> dict[str, Any]:
        """Return discovery-safe context with all answers withheld.

        The callback receives the market, time, opportunity family and learned
        patterns.  It never receives the known company, URL, or the evidence
        text used to propose a learning candidate.
        """

        return {
            "case_id": self.case_id,
            "market_code": self.market_code,
            "observed_at": self.observed_at.isoformat(),
            "opportunity_type": self.opportunity_type,
            "stock_proven": self.stock_proven,
            "root_cause": self.root_cause,
            "learned_patterns": list(self.learned_patterns),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "market_code": self.market_code,
            "discovered_by": self.discovered_by,
            "observed_at": self.observed_at.isoformat(),
            "opportunity_type": self.opportunity_type,
            "stock_proven": self.stock_proven,
            "ground_truth": {
                "company": self.ground_truth_company,
                "url": self.ground_truth_url,
            },
            "trace": self.trace.to_dict(),
            "learning_evidence_text": self.learning_evidence_text,
            "diagnosed_query_gap_terms": list(self.diagnosed_query_gap_terms),
            "learned_patterns": list(self.learned_patterns),
            "root_cause": self.root_cause,
            "learning_status": self.learning_status,
            "repeat_miss": self.repeat_miss,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MissedOpportunityCase":
        truth = payload.get("ground_truth")
        truth = dict(truth) if isinstance(truth, Mapping) else {}
        trace = payload.get("trace")
        trace = dict(trace) if isinstance(trace, Mapping) else {}
        diagnosed = payload.get("diagnosed_query_gap_terms")
        if not isinstance(diagnosed, list):
            diagnosed = []
        learned = payload.get("learned_patterns")
        if not isinstance(learned, list):
            learned = []
        return cls(
            case_id=str(payload.get("case_id") or "").strip(),
            market_code=str(payload.get("market_code") or "").strip().upper(),
            discovered_by=str(payload.get("discovered_by") or "").strip(),
            observed_at=datetime.fromisoformat(str(payload.get("observed_at"))),
            opportunity_type=str(payload.get("opportunity_type") or "").strip(),
            stock_proven=bool(payload.get("stock_proven")),
            ground_truth_company=str(truth.get("company") or "").strip(),
            ground_truth_url=str(truth.get("url") or "").strip(),
            trace=DiscoveryTrace.from_dict(trace),
            learning_evidence_text=str(
                payload.get("learning_evidence_text") or ""
            ).strip(),
            diagnosed_query_gap_terms=tuple(
                str(item).strip() for item in diagnosed if str(item).strip()
            ),
            learned_patterns=tuple(
                str(item).strip() for item in learned if str(item).strip()
            ),
            root_cause=(
                str(payload.get("root_cause")).strip()
                if payload.get("root_cause")
                else None
            ),
            learning_status=str(payload.get("learning_status") or "PENDING").strip(),
            repeat_miss=bool(payload.get("repeat_miss")),
        )


@dataclass(frozen=True, slots=True)
class ReplayResult:
    case_id: str
    recovered: bool
    matched_by: str | None
    candidate_count: int
    ground_truth_exposed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_company(value: object) -> str:
    text = " ".join(str(value or "").casefold().split())
    return re.sub(r"[^\w]+", "", text, flags=re.UNICODE)


def _normalize_url(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    scheme = parts.scheme.casefold()
    netloc = parts.netloc.casefold()
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def _candidate_match(
    case: MissedOpportunityCase, candidate: Mapping[str, Any]
) -> str | None:
    expected_company = _normalize_company(case.ground_truth_company)
    expected_url = _normalize_url(case.ground_truth_url)
    candidate_company = _normalize_company(candidate.get("company"))
    candidate_url = _normalize_url(candidate.get("url"))

    company_match = bool(expected_company and candidate_company == expected_company)
    url_match = bool(expected_url and candidate_url == expected_url)
    if company_match and url_match:
        return "company+url"
    if url_match:
        return "url"
    if company_match:
        return "company"
    return None


DiscoveryCallback = Callable[[dict[str, Any]], Sequence[Mapping[str, Any]]]


def run_replay(
    case: MissedOpportunityCase, discover: DiscoveryCallback
) -> ReplayResult:
    """Replay one miss without leaking its hidden answer to discovery."""

    context = case.replay_context()
    forbidden = {
        "ground_truth",
        "ground_truth_company",
        "ground_truth_url",
        "learning_evidence_text",
        "company",
        "url",
    }
    exposed = any(key in context for key in forbidden)
    if exposed:
        raise ValueError("Replay context exposed hidden ground truth")

    raw_candidates = discover(dict(context))
    candidates = [item for item in raw_candidates if isinstance(item, Mapping)]
    for candidate in candidates:
        matched_by = _candidate_match(case, candidate)
        if matched_by:
            return ReplayResult(
                case_id=case.case_id,
                recovered=True,
                matched_by=matched_by,
                candidate_count=len(candidates),
                ground_truth_exposed=False,
            )
    return ReplayResult(
        case_id=case.case_id,
        recovered=False,
        matched_by=None,
        candidate_count=len(candidates),
        ground_truth_exposed=False,
    )


def save_missed_opportunity_memory(
    path: str | Path, cases: Sequence[MissedOpportunityCase]
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "case_count": len(cases),
        "cases": [case.to_dict() for case in cases],
    }
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def load_missed_opportunity_memory(
    path: str | Path,
) -> list[MissedOpportunityCase]:
    target = Path(path)
    if not target.exists():
        return []
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Missed opportunity memory must be a JSON object")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list):
        return []
    return [
        MissedOpportunityCase.from_dict(item)
        for item in raw_cases
        if isinstance(item, Mapping)
    ]


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def build_learning_metrics(
    cases: Sequence[MissedOpportunityCase],
    replay_results: Sequence[ReplayResult],
) -> dict[str, Any]:
    """Summarize whether the engine is converting misses into retained skill."""

    replay_by_case = {result.case_id: result for result in replay_results}
    recovered_count = sum(
        1
        for case in cases
        if replay_by_case.get(case.case_id)
        and replay_by_case[case.case_id].recovered
    )
    diagnosed_count = sum(1 for case in cases if case.root_cause in ROOT_CAUSES)
    repeat_miss_count = sum(1 for case in cases if case.repeat_miss)
    causes = Counter(
        case.root_cause for case in cases if case.root_cause in ROOT_CAUSES
    )
    total = len(cases)
    return {
        "schema_version": SCHEMA_VERSION,
        "known_missed_opportunities": total,
        "diagnosed_count": diagnosed_count,
        "recovered_count": recovered_count,
        "unresolved_count": total - recovered_count,
        "recovery_rate": _rate(recovered_count, total),
        "repeat_miss_count": repeat_miss_count,
        "repeat_miss_rate": _rate(repeat_miss_count, total),
        "root_cause_counts": dict(causes),
    }
