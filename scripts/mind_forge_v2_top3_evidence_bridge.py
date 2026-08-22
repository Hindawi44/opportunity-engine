from __future__ import annotations

from typing import Any, Callable

from scripts.mind_forge_v2_evidence_rerank import rerank_with_evidence


ResearchExecutor = Callable[[dict[str, Any]], tuple[list[dict[str, Any]], int]]


def run_top3_evidence_bridge(
    reasoning: dict[str, Any],
    plan: dict[str, Any],
    executor: ResearchExecutor,
) -> dict[str, Any]:
    requests = list(plan.get("requests", []) or [])
    if len(requests) != 3:
        raise ValueError(f"expected exactly 3 research requests, got {len(requests)}")
    if int(plan.get("max_total_search_operations", 0)) != 3:
        raise ValueError("Top 3 evidence bridge requires max_total_search_operations=3")
    if int(plan.get("max_operations_per_request", 0)) != 1:
        raise ValueError("Top 3 evidence bridge requires max_operations_per_request=1")

    observations: list[dict[str, Any]] = []
    total_operations = 0
    for request in requests:
        if int(request.get("max_search_operations", 0)) != 1:
            raise ValueError("each Top 3 request must be capped at one search operation")
        rows, operations = executor(request)
        if operations != 1:
            raise RuntimeError("Top 3 research executor must perform exactly one search operation per request")
        total_operations += operations
        if total_operations > 3:
            raise RuntimeError("Top 3 evidence research exceeded three search operations")
        idea_id = str(request["idea_id"])
        for row in rows:
            obs = dict(row)
            obs["idea_id"] = idea_id
            if not str(obs.get("source_ref", "")).strip():
                raise ValueError("research observation requires source_ref")
            if not str(obs.get("observation_text", "")).strip():
                raise ValueError("research observation requires observation_text")
            observations.append(obs)

    reranked = rerank_with_evidence(reasoning, observations, top_n=3)
    return {
        "status": "MIND_FORGE_V2_TOP3_EVIDENCE_COMPLETE",
        "search_operations": total_operations,
        "observation_count": len(observations),
        "final_rank": reranked,
    }
