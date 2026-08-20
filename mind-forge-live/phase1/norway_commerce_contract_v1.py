from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE_PATH = ROOT / "norway_commerce_v1.py"
RUNNER_PATH = ROOT / "runner_v1_norway_commerce.py"

COMMERCE_CASES = (
    "تجارة سيارات مستعملة في النرويج",
    "شراء مخزون تصفية ملابس بالجملة وإعادة بيعه في النرويج",
    "تجارة أقمشة stocklot في النرويج",
    "شراء أثاث مستعمل وإعادة بيعه في النرويج",
    "استيراد وبيع ماكينات خياطة صناعية في النرويج",
    "تجارة قطع غيار سيارات في النرويج",
    "شراء بضائع liquidation من المزادات في النرويج",
    "تجارة معدات ورش مستعملة في النرويج",
)

DISCOVERY_CASE = "ابحث عن تجارة مربحة في النرويج"

NON_COMMERCE_CASES = (
    "debug API timeout in Norway deployment",
    "تحليل استهلاك الطاقة في النرويج",
    "الطقس في النرويج",
)

EXPECTED_LABELS = (
    "norway demand and turnover",
    "sourcing and acquisition",
    "norway resale pricing and margin",
    "competition and sales channels",
    "norway rules taxes and logistics",
    "risk and execution test",
)


def _load_module():
    spec = importlib.util.spec_from_file_location("norway_commerce_v1", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load norway_commerce_v1")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runner_structure_ok() -> bool:
    source = RUNNER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(RUNNER_PATH))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    required = {
        "norway_commerce_profile_for_seed",
        "norway_commerce_templates_for_seed",
        "norway_commerce_geographically_relevant",
        "norway_commerce_semantically_relevant",
        "install_norway_commerce_runner",
        "norway_commerce_main",
    }
    if not required.issubset(functions):
        return False

    install_text = ast.unparse(functions["install_norway_commerce_runner"])
    return all(
        token in install_text
        for token in (
            "resilient.research_profile_for_seed",
            "resilient.research_templates_for_seed",
            "geographic._is_geographically_relevant",
            "geographic._is_semantically_relevant",
            "geographic.install_geographic_runner()",
        )
    )


def run_contract() -> dict[str, object]:
    module = _load_module()

    for seed in COMMERCE_CASES:
        if not module.is_norway_commerce_seed(seed):
            raise AssertionError(f"commerce seed was not recognized: {seed}")

    if not module.is_norway_commerce_discovery_seed(DISCOVERY_CASE):
        raise AssertionError("generic Norway commerce discovery seed was not recognized")

    for seed in NON_COMMERCE_CASES:
        if module.is_norway_commerce_seed(seed):
            raise AssertionError(f"non-commerce seed was misclassified: {seed}")

    templates = module.norway_commerce_templates()
    labels = tuple(item[0] for item in templates)
    if labels != EXPECTED_LABELS:
        raise AssertionError(f"unexpected commerce lens order: {labels}")
    if len(set(labels)) != 6:
        raise AssertionError("NORWAY_COMMERCE must have six unique lenses")

    for seed in COMMERCE_CASES:
        for _label, claim_template, _why, _sources in templates:
            rendered = claim_template.format(seed=seed)
            if seed not in rendered:
                raise AssertionError(f"seed not preserved in claim: {seed}")

    ideas = module.norway_commerce_idea_box(limit=20)
    if len(ideas) != 20:
        raise AssertionError(f"idea box expected 20 ideas, got {len(ideas)}")
    if len(set(ideas)) != 20:
        raise AssertionError("idea box contains duplicate ideas")
    for idea in ideas:
        if not module.is_norway_commerce_seed(idea):
            raise AssertionError(f"idea escaped Norway commerce scope: {idea}")

    expanded = module.candidate_seeds_for_seed(DISCOVERY_CASE, limit=20)
    if expanded != ideas:
        raise AssertionError("generic discovery seed did not expand into the full Idea Box")

    specific = COMMERCE_CASES[0]
    if module.candidate_seeds_for_seed(specific, limit=20) != [specific]:
        raise AssertionError("specific commerce seed must not be replaced by the Idea Box")

    if not _runner_structure_ok():
        raise AssertionError("NORWAY_COMMERCE runner integration structure is incomplete")

    return {
        "status": "NORWAY_COMMERCE_CONTRACT_PASS",
        "network_calls": 0,
        "paid_api_calls": 0,
        "commerce_case_count": len(COMMERCE_CASES),
        "non_commerce_case_count": len(NON_COMMERCE_CASES),
        "lens_count": len(labels),
        "idea_box_count": len(ideas),
        "discovery_seed": DISCOVERY_CASE,
        "discovery_candidate_count": len(expanded),
        "idea_box": ideas,
    }


def main() -> None:
    print(json.dumps(run_contract(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
