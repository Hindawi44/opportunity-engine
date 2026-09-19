from pathlib import Path

WORKFLOWS = Path(".github/workflows")
ARCHIVED = Path("docs/archive/foreign-manual-research-20260919.yaml.txt")


def test_tests_workflow_is_pure_ci() -> None:
    text = (WORKFLOWS / "tests.yml").read_text(encoding="utf-8")
    assert "pytest -q > pytest-output.log 2>&1" in text
    for forbidden in (
        "BRAVE_SEARCH_API_KEY", "EXA_API_KEY", "build_italy_market_discovery.py",
        "build_france_market_discovery.py", "build_netherlands_market_discovery.py",
        "run_keyword_discovery_lab.py", "run_keyword_shadow_verification.py",
        "actions/workflows/${TARGET_WORKFLOW}/dispatches",
    ):
        assert forbidden not in text


def test_manual_workflow_is_norway_only_and_no_paid_or_foreign_search() -> None:
    text = (WORKFLOWS / "research-shadow-manual.yaml").read_text(encoding="utf-8")
    trigger = text.split("on:", 1)[1].split("jobs:", 1)[0]
    assert "workflow_dispatch:" in trigger
    assert "push:" not in trigger
    assert "pull_request:" not in trigger
    assert "schedule:" not in trigger
    assert text.startswith("name: Norway Hunter Manual Verification\n")
    for forbidden in ("BRAVE_SEARCH_API_KEY:", "EXA_API_KEY:", "OPENAI_API_KEY:",
                      "italy_live_validation:", "france_live_validation:",
                      "netherlands_live_validation:", "keyword_lab:", "keyword_shadow_verify:",
                      "run_keyword_discovery_lab.py", "build_italy_market_discovery.py",
                      "build_france_market_discovery.py", "build_netherlands_market_discovery.py"):
        assert forbidden not in text
    assert "test_event_first_hunter_pilot.py" in text
    assert "test_event_auction_evidence_link_v1.py" in text
    assert "BRAVE_SEARCH_API_KEY: ${{ secrets.BRAVE_SEARCH_API_KEY }}" in ARCHIVED.read_text(encoding="utf-8")


def test_production_dispatch_waits_for_successful_ci() -> None:
    text = (WORKFLOWS / "production-dispatch-after-ci.yaml").read_text(encoding="utf-8")
    assert "workflow_run:" in text
    assert "workflows: [Tests]" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "TARGET_WORKFLOW: multi-market-daily-operator-checkpoint.yaml" in text
    assert "BRAVE_SEARCH_API_KEY" not in text
    assert "EXA_API_KEY" not in text
