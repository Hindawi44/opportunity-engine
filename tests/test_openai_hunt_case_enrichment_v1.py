"""Run original OpenAI enrichment unit tests; migrate only the obsolete workflow contract.

The intact pre-Norway test suite is preserved under tests/_legacy_six_market/.
No tests of the OpenAI model client, signal selection or advisory safety are lost.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "tests/_legacy_six_market/openai_hunt_case_enrichment_v1.py"
ARCHIVED_WORKFLOW = ROOT / "docs/archive/legacy-six-market-checkpoint-20260919.yaml.txt"
ACTIVE = ROOT / ".github/workflows/multi-market-daily-operator-checkpoint.yaml"
spec = spec_from_file_location("archived_openai_hunt_unit_tests", LEGACY)
assert spec is not None and spec.loader is not None
legacy = module_from_spec(spec)
spec.loader.exec_module(legacy)
legacy.ROOT = ROOT
legacy.WORKFLOW = ARCHIVED_WORKFLOW
legacy.BUILD_SCRIPT = ROOT / "scripts/build_domain_market_intelligence_feed.py"
for name, test in vars(legacy).items():
    if name.startswith("test_") and name != "test_checkpoint_workflow_injects_secret_and_bounded_models":
        globals()[name] = test


def test_model_credentials_are_restored_only_for_bounded_norway_hunt() -> None:
    old = ARCHIVED_WORKFLOW.read_text(encoding="utf-8")
    active = ACTIVE.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in old
    assert 'OPENAI_HUNT_MAX_API_REQUESTS: "3"' in old
    norway = active.split("  norway-all-assets:\n", 1)[1].split("  norway-existing-engine:\n", 1)[0]
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in norway
    assert 'OPENAI_HUNT_MAX_API_REQUESTS: "2"' in norway
    assert 'OPENAI_HUNT_MAX_ESTIMATED_COST_USD: "0.08"' in norway
    assert "run_norway_openai_search_intelligence.py" in norway
    for foreign in ("--market SE", "--market DE", "--market FR", "--market IT", "--market NL"):
        assert foreign not in active
    assert "run_event_first_hunter_pilot.py" in active
    assert "automatic_purchase: true" not in active
