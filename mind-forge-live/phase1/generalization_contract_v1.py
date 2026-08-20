from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESILIENT_RUNNER = ROOT / "runner_v1_resilient.py"
GEOGRAPHIC_RUNNER = ROOT / "runner_v1_geographic.py"

EXPECTED_GENERAL_LABELS = (
    "observable reality",
    "alternatives and benchmarks",
    "people and context",
    "resources and economics",
    "rules risks and dependencies",
    "implementation and access",
)

EXPECTED_LOCAL_LABELS = (
    "local demand",
    "competition",
    "customer base",
    "pricing and economics",
    "regulation",
    "location and customer flow",
)

PROFILE_CASES = (
    ("محل شاي في نامسوس", "LOCAL_MARKET"),
    ("open a cafe in Oslo", "LOCAL_MARKET"),
    ("إصلاح انهيار البرنامج عند رفع ملف 2GB", "GENERAL"),
    ("شراء 2000 متر أقمشة stocklot من إيطاليا", "GENERAL"),
    ("اختيار ماكينة خياطة صناعية GC1011", "GENERAL"),
    ("تحليل استهلاك الطاقة لخوارزمية ضغط بيانات", "GENERAL"),
    ("تحسين تأخير سلسلة توريد من إيطاليا إلى النرويج", "GENERAL"),
    ("debug API timeout in Norway deployment", "GENERAL"),
)


def _literal_assignments(tree: ast.Module) -> dict[str, object]:
    values: dict[str, object] = {}
    for node in tree.body:
        target = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        if not isinstance(target, ast.Name) or value is None:
            continue
        try:
            values[target.id] = ast.literal_eval(value)
        except (ValueError, TypeError):
            continue
    return values


def _extract_functions(tree: ast.Module, names: set[str]) -> list[ast.FunctionDef]:
    found = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    missing = names.difference(node.name for node in found)
    if missing:
        raise AssertionError(f"missing expected functions: {sorted(missing)}")
    return found


def _load_profile_logic():
    source = RESILIENT_RUNNER.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(RESILIENT_RUNNER))
    assignments = _literal_assignments(tree)

    required_constants = {
        "_LOCAL_MARKET_SEED_MARKERS",
        "_MARKET_RESEARCH_TEMPLATES",
        "_UNIVERSAL_RESEARCH_TEMPLATES",
    }
    missing = required_constants.difference(assignments)
    if missing:
        raise AssertionError(f"missing expected constants: {sorted(missing)}")

    functions = _extract_functions(
        tree,
        {"research_profile_for_seed", "research_templates_for_seed"},
    )
    module = ast.Module(body=functions, type_ignores=[])
    ast.fix_missing_locations(module)

    namespace = {name: assignments[name] for name in required_constants}
    exec(compile(module, str(RESILIENT_RUNNER), "exec"), namespace)
    return namespace


def _labels(templates) -> tuple[str, ...]:
    return tuple(item[0] for item in templates)


def run_contract() -> dict[str, object]:
    namespace = _load_profile_logic()
    profile = namespace["research_profile_for_seed"]
    templates_for_seed = namespace["research_templates_for_seed"]

    case_results = []
    for seed, expected in PROFILE_CASES:
        actual = profile(seed)
        if actual != expected:
            raise AssertionError(
                f"profile mismatch for {seed!r}: expected {expected}, got {actual}"
            )
        templates = templates_for_seed(seed)
        labels = _labels(templates)
        expected_labels = (
            EXPECTED_LOCAL_LABELS if expected == "LOCAL_MARKET" else EXPECTED_GENERAL_LABELS
        )
        if labels != expected_labels:
            raise AssertionError(
                f"lens mismatch for {seed!r}: expected {expected_labels}, got {labels}"
            )
        if len(set(labels)) != 6:
            raise AssertionError(f"research lenses must be six unique labels for {seed!r}")

        for _label, claim_template, _why_material, _source_types in templates:
            rendered = claim_template.format(seed=seed)
            if seed not in rendered:
                raise AssertionError(
                    f"exact seed was not preserved in rendered claim for {seed!r}"
                )

        case_results.append(
            {
                "seed": seed,
                "profile": actual,
                "labels": list(labels),
            }
        )

    general_labels = set(EXPECTED_GENERAL_LABELS)
    local_only = {
        "local demand",
        "competition",
        "customer base",
        "pricing and economics",
        "regulation",
        "location and customer flow",
    }
    if general_labels.intersection(local_only):
        raise AssertionError("GENERAL profile is contaminated by local-market lenses")

    geographic_source = GEOGRAPHIC_RUNNER.read_text(encoding="utf-8")
    local_gate = 'research_profile_for_seed(seed) == "LOCAL_MARKET"'
    if local_gate not in geographic_source:
        raise AssertionError(
            "geographic filtering is not explicitly gated by LOCAL_MARKET"
        )

    return {
        "status": "MIND_FORGE_GENERALIZATION_CONTRACT_PASS",
        "network_calls": 0,
        "paid_api_calls": 0,
        "case_count": len(case_results),
        "general_lens_count": len(EXPECTED_GENERAL_LABELS),
        "local_lens_count": len(EXPECTED_LOCAL_LABELS),
        "cases": case_results,
    }


def main() -> None:
    print(json.dumps(run_contract(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
