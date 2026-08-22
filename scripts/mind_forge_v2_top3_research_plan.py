from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_top3_research_plan(reasoning: dict[str, Any]) -> dict[str, Any]:
    selected = list(reasoning.get("selected_idea_ids", []) or [])
    assessments = {str(row["idea_id"]): row for row in reasoning.get("assessments", []) or []}
    if len(selected) != 3:
        raise ValueError(f"expected exactly 3 selected ideas, got {len(selected)}")

    requests: list[dict[str, Any]] = []
    for rank, idea_id in enumerate(selected, start=1):
        idea_id = str(idea_id)
        if idea_id not in assessments:
            raise ValueError(f"selected idea missing from assessments: {idea_id}")
        row = assessments[idea_id]
        critique = row.get("critique", {}) or {}
        assumption = str(critique.get("key_assumption") or "").strip()
        risk = str(critique.get("key_risk") or "").strip()
        title = str(row.get("title") or idea_id)
        if assumption:
            claim = assumption
        elif risk:
            claim = risk
        else:
            claim = f"There is a real, material need in Norway for the mechanism proposed by {title}."
        requests.append({
            "request_id": f"v2-top3-{rank}",
            "idea_id": idea_id,
            "title": title,
            "claim_text": claim,
            "why_material": "This is the single highest-value uncertainty to resolve before final ranking.",
            "route": "WEB",
            "acceptable_source_types": ["official", "public_data", "primary", "academic", "industry", "company"],
            "max_search_operations": 1,
            "max_results": 3,
        })

    return {
        "status": "MIND_FORGE_V2_TOP3_RESEARCH_PLAN_READY",
        "candidate_count": 3,
        "request_count": len(requests),
        "max_total_search_operations": 3,
        "max_operations_per_request": 1,
        "uses_mechanism_family_for_routing": False,
        "requests": requests,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reasoning_json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    reasoning = json.loads(Path(args.reasoning_json).read_text(encoding="utf-8"))
    result = build_top3_research_plan(reasoning)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "request_count": result["request_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
