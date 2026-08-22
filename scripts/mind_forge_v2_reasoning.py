from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any


@dataclass(frozen=True)
class Lens:
    lens_id: str
    label: str
    keywords: tuple[str, ...]


LENSES: tuple[Lens, ...] = (
    Lens("systems_scale", "Systems & Scale", ("scale", "repeat", "standard", "capacity", "network")),
    Lens("information_edge", "Information Advantage", ("signal", "data", "forecast", "trace", "verify")),
    Lens("capital", "Capital Allocation", ("margin", "cost", "inventory", "cash", "capital", "preorder")),
    Lens("retail", "Retail Efficiency", ("stock", "merchant", "order", "delivery", "customer")),
    Lens("operations", "Operational Productivity", ("process", "workflow", "routing", "inspection", "handling")),
    Lens("standardization", "Standardization", ("standard", "procedure", "repeatable", "package", "specification")),
    Lens("distribution", "Distribution", ("route", "delivery", "supplier", "fulfillment", "access")),
    Lens("customer_trust", "Customer Trust", ("trust", "warranty", "clarity", "evidence", "origin", "compliance")),
    Lens("replication", "Replication", ("shared", "recurring", "operator", "business", "replenishment")),
    Lens("differentiation", "Differentiation", ("novel", "alternative", "repair", "service", "substitute", "outcome")),
)


def _text(idea: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("title", "core_mechanism", "customer_value", "business_value", "novelty_reason"):
        parts.append(str(idea.get(key, "")))
    for key in ("required_capabilities", "assumptions", "risks"):
        parts.extend(str(x) for x in idea.get(key, []) or [])
    return " ".join(parts).casefold()


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _structural_quality(idea: dict[str, Any]) -> float:
    required = len(idea.get("required_capabilities", []) or [])
    assumptions = len(idea.get("assumptions", []) or [])
    risks = len(idea.get("risks", []) or [])
    completeness = mean(
        1.0 if str(idea.get(key, "")).strip() else 0.0
        for key in ("core_mechanism", "customer_value", "business_value", "novelty_reason")
    )
    simplicity = 1.0 - min(required, 6) / 8.0
    assumption_burden = min(assumptions, 5) / 5.0
    risk_burden = min(risks, 5) / 5.0
    return _bounded(0.50 * completeness + 0.30 * simplicity + 0.10 * (1 - assumption_burden) + 0.10 * (1 - risk_burden))


def _lens_score(idea: dict[str, Any], lens: Lens) -> float:
    text = _text(idea)
    hits = sum(1 for keyword in lens.keywords if keyword in text)
    semantic = min(1.0, hits / max(2, math.ceil(len(lens.keywords) / 2)))
    return _bounded(0.55 * _structural_quality(idea) + 0.45 * semantic)


def _logic_score(idea: dict[str, Any]) -> float:
    required = len(idea.get("required_capabilities", []) or [])
    assumptions = len(idea.get("assumptions", []) or [])
    risks = len(idea.get("risks", []) or [])
    feasibility = 1.0 - min(required, 6) / 9.0
    reversibility = 0.78 if any(word in _text(idea) for word in ("test", "preorder", "small", "pilot", "limited")) else 0.62
    dependency_risk = min(1.0, 0.18 * required + 0.12 * risks)
    evidence_debt = min(1.0, 0.16 * assumptions + 0.08 * risks)
    simplicity = 1.0 - min(required, 6) / 6.0
    return _bounded(
        0.30 * feasibility
        + 0.20 * reversibility
        + 0.20 * (1.0 - dependency_risk)
        + 0.20 * (1.0 - evidence_debt)
        + 0.10 * simplicity
    )


def _critique(idea: dict[str, Any], logic_score: float) -> dict[str, Any]:
    assumptions = list(idea.get("assumptions", []) or [])
    risks = list(idea.get("risks", []) or [])
    severity = _bounded(0.30 + 0.08 * len(assumptions) + 0.07 * len(risks) + 0.25 * (1.0 - logic_score))
    if severity >= 0.72:
        disposition = "REWORK"
    elif severity >= 0.56:
        disposition = "NEEDS_EVIDENCE"
    else:
        disposition = "SURVIVES"
    key_assumption = assumptions[0] if assumptions else "The mechanism creates measurable customer and business value."
    key_risk = risks[0] if risks else "Execution complexity may exceed the expected value."
    return {
        "severity": severity,
        "disposition": disposition,
        "key_assumption": key_assumption,
        "key_risk": key_risk,
        "falsification_test": f"Run the smallest reversible test that directly challenges: {key_assumption}",
    }


def evaluate_payload(payload: dict[str, Any], top_n: int = 3) -> dict[str, Any]:
    ideas = list(payload.get("ideas", []) or [])
    if not ideas:
        raise ValueError("Creative V2 payload contains no ideas")
    if len(LENSES) != 10:
        raise RuntimeError("reasoning pipeline requires exactly ten lenses")

    expert_outputs: list[dict[str, Any]] = []
    lens_scores_by_idea: dict[str, list[float]] = {str(i["idea_id"]): [] for i in ideas}
    for lens in LENSES:
        scores = {str(idea["idea_id"]): _lens_score(idea, lens) for idea in ideas}
        strongest = max(scores, key=lambda idea_id: (scores[idea_id], idea_id))
        expert_outputs.append({
            "lens_id": lens.lens_id,
            "lens": lens.label,
            "strongest_idea_id": strongest,
            "support_scores": scores,
        })
        for idea_id, score in scores.items():
            lens_scores_by_idea[idea_id].append(score)

    assessments: list[dict[str, Any]] = []
    for idea in ideas:
        idea_id = str(idea["idea_id"])
        logic = _logic_score(idea)
        expert_mean = _bounded(mean(lens_scores_by_idea[idea_id]))
        critique = _critique(idea, logic)
        composite = _bounded(0.62 * logic + 0.38 * expert_mean - 0.12 * critique["severity"])
        assessments.append({
            "idea_id": idea_id,
            "title": idea.get("title"),
            "mechanism_family": idea.get("mechanism_family") or payload.get("mechanism_families", {}).get(idea_id),
            "logic_score": logic,
            "expert_support_mean": expert_mean,
            "critique": critique,
            "composite_score": composite,
        })

    ranked = sorted(assessments, key=lambda x: (x["composite_score"], x["logic_score"], x["idea_id"]), reverse=True)
    selected = [item["idea_id"] for item in ranked if item["critique"]["disposition"] != "REWORK"][:top_n]
    if len(selected) < min(top_n, len(ranked)):
        selected = [item["idea_id"] for item in ranked[:top_n]]

    return {
        "status": "MIND_FORGE_V2_REASONING_COMPLETE",
        "seed": payload.get("seed"),
        "idea_count": len(ideas),
        "expert_mind_count": len(expert_outputs),
        "uses_mechanism_family_for_scoring": False,
        "expert_outputs": expert_outputs,
        "assessments": ranked,
        "selected_idea_ids": selected,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("input_json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--top-n", type=int, default=3)
    args = parser.parse_args()

    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    result = evaluate_payload(payload, top_n=args.top_n)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "idea_count": result["idea_count"],
        "expert_mind_count": result["expert_mind_count"],
        "selected_idea_ids": result["selected_idea_ids"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
