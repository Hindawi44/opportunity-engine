from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "creative_engine_v2_open.py"
LIVE = ROOT / "live_creative_v2_open.py"
V1 = ROOT / "creative_engine_v1.py"


def _functions(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _string_literals(tree: ast.AST) -> str:
    parts: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            parts.append(node.value)
    return "\n".join(parts)


def run_contract() -> dict[str, object]:
    engine_source = ENGINE.read_text(encoding="utf-8")
    live_source = LIVE.read_text(encoding="utf-8")
    v1_source = V1.read_text(encoding="utf-8")

    engine_tree = ast.parse(engine_source, filename=str(ENGINE))
    live_tree = ast.parse(live_source, filename=str(LIVE))
    engine_literals = _string_literals(engine_tree)
    live_literals = _string_literals(live_tree)

    required_engine = {
        "open_creative_prompt",
        "apply_open_payload",
        "v1_benchmark",
    }
    missing_engine = required_engine.difference(_functions(engine_tree))
    if missing_engine:
        raise AssertionError(f"missing V2 engine functions: {sorted(missing_engine)}")

    if "generate_live_open_ideas" not in _functions(live_tree):
        raise AssertionError("missing paid V2 open generator")

    forbidden_open_tokens = (
        "_PATTERNS",
        "BOUNDED IDEA FRAMES",
        "preserve every idea_id",
        "stay inside its stated mechanism family",
    )
    for token in forbidden_open_tokens:
        if token in engine_source or token in live_source or token in engine_literals or token in live_literals:
            raise AssertionError(f"V2 is contaminated by V1 frame constraint: {token}")

    required_prompt_meaning = (
        "NOT rewriting a supplied idea list",
        "NOT constrained to predefined mechanism families",
        "Discover the opportunity space from the meaning of the seed itself",
        "at least eight distinct mechanism families",
    )
    for text in required_prompt_meaning:
        if text not in engine_literals:
            raise AssertionError(f"V2 open prompt lost required instruction: {text}")

    if "generate_v1_ideas(topic, questions)" not in engine_source:
        raise AssertionError("V1 benchmark/fallback hook is missing")

    if "def generate_ideas(" not in v1_source:
        raise AssertionError("V1 deterministic generator was unexpectedly removed")

    if "OpenCreativePayload" not in live_source or "apply_open_payload" not in live_source:
        raise AssertionError("live V2 does not use the open output contract")

    return {
        "status": "CREATIVE_V2_OPEN_CONTRACT_PASS",
        "network_calls": 0,
        "paid_api_calls": 0,
        "v1_preserved": True,
        "v2_uses_predefined_pattern_frames": False,
        "v2_min_required_family_diversity": 8,
        "v2_target_idea_count": 14,
    }


def main() -> None:
    print(json.dumps(run_contract(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
