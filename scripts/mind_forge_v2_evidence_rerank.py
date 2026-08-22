from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

SOURCE_WEIGHTS = {
    "official": 1.00,
    "public_data": 1.00,
    "primary": 0.95,
    "academic": 0.90,
    "industry": 0.80,
    "company": 0.65,
    "secondary": 0.55,
    "unknown": 0.35,
}

STANCE_SIGN = {
    "SUPPORTS": 1.0,
    "CONTRADICTS": -1.0,
    "MIXED": -0.25,
    "NEUTRAL": 0.0,
}


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _source_weight(source_type: str) -> float:
    key = str(source_type or "unknown").strip().casefold().replace("-", "_").replace(" ", "_")
    return SOURCE_WEIGHTS.get(key, SOURCE_WEIGHTS["unknown"])


def rerank_with_evidence(
    reasoning: dict[str, Any],
    observations: list[dict[str, Any]],
    *,
    top_n: int = 3,
) -> dict[str, Any]:
    assessments = list(reasoning.get("assessments", []) or [])
    selected_ids = list(reasoning.get("selected_idea_ids", []) or [])
    if not assessments or not selected_ids:
        raise ValueError("reasoning result must contain assessments and selected_idea_ids")

    by_id = {str(row["idea_id"]): row for row in assessments}
    candidate_ids = [str(idea_id) for idea_id in selected_ids]
    unknown_candidates = [idea_id for idea_id in candidate_ids if idea_id not in by_id]
    if unknown_candidates:
        raise ValueError(f"selected idea IDs missing from assessments: {unknown_candidates}")

    obs_by_idea: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for obs in observations:
        idea_id = str(obs.get("idea_id", ""))
        if idea_id not in candidate_ids:
            raise ValueError(f"evidence references idea outside selected candidates: {idea_id}")
        stance = str(obs.get("stance", "NEUTRAL")).upper()
        if stance not in STANCE_SIGN:
            raise ValueError(f"unsupported evidence stance: {stance}")
        confidence = float(obs.get("confidence", 0.0))
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("evidence confidence must be between 0 and 1")
        if not str(obs.get("source_ref", "")).strip():
            raise ValueError("evidence requires source_ref")
        if not str(obs.get("observation_text", "")).strip():
            raise ValueError("evidence requires observation_text")
        obs_by_idea[idea_id].append(obs)

    rows: list[dict[str, Any]] = []
    for idea_id in candidate_ids:
        base = float(by_id[idea_id].get("composite_score", 0.0))
        idea_obs = obs_by_idea.get(idea_id, [])
        weighted_sum = 0.0
        weight_total = 0.0
        stances: set[str] = set()
        source_refs: list[str] = []
        for obs in idea_obs:
            stance = str(obs.get("stance", "NEUTRAL")).upper()
            confidence = float(obs.get("confidence", 0.0))
            quality = _source_weight(str(obs.get("source_type", "unknown")))
            weight = quality * confidence
            weighted_sum += STANCE_SIGN[stance] * weight
            weight_total += weight
            stances.add(stance)
            source_refs.append(str(obs["source_ref"]))

        if weight_total > 0:
            signal = max(-1.0, min(1.0, weighted_sum / weight_total))
            evidence_score = _bounded((signal + 1.0) / 2.0)
            status = "EVIDENCE_AVAILABLE"
        else:
            signal = 0.0
            evidence_score = 0.5
            status = "NO_EVIDENCE"

        conflict = "SUPPORTS" in stances and "CONTRADICTS" in stances
        conflict_penalty = 0.08 if conflict else 0.0
        final_score = _bounded(0.70 * base + 0.30 * evidence_score - conflict_penalty)
        rows.append({
            "idea_id": idea_id,
            "title": by_id[idea_id].get("title"),
            "reasoning_score": round(base, 4),
            "evidence_score": evidence_score,
            "evidence_signal": round(signal, 4),
            "evidence_count": len(idea_obs),
            "evidence_status": status,
            "conflicting_evidence": conflict,
            "final_score": final_score,
            "source_refs": source_refs,
        })

    ranked = sorted(rows, key=lambda row: (row["final_score"], row["reasoning_score"], row["idea_id"]), reverse=True)
    top = ranked[: min(top_n, len(ranked))]
    return {
        "status": "MIND_FORGE_V2_EVIDENCE_RERANK_COMPLETE",
        "uses_mechanism_family_for_scoring": False,
        "candidate_count": len(candidate_ids),
        "observation_count": len(observations),
        "ranking": ranked,
        "selected_idea_ids": [row["idea_id"] for row in top],
        "selected_titles": [row["title"] for row in top],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reasoning_json")
    parser.add_argument("evidence_json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--top-n", type=int, default=3)
    args = parser.parse_args()

    reasoning = json.loads(Path(args.reasoning_json).read_text(encoding="utf-8"))
    evidence_payload = json.loads(Path(args.evidence_json).read_text(encoding="utf-8"))
    observations = list(evidence_payload.get("observations", evidence_payload if isinstance(evidence_payload, list) else []))
    result = rerank_with_evidence(reasoning, observations, top_n=args.top_n)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "selected_idea_ids": result["selected_idea_ids"],
        "selected_titles": result["selected_titles"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
