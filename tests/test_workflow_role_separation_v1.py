from pathlib import Path


WORKFLOWS = Path(".github/workflows")


def test_tests_workflow_is_pure_ci() -> None:
    text = (WORKFLOWS / "tests.yml").read_text(encoding="utf-8")

    assert "pytest -q > pytest-output.log 2>&1" in text
    for forbidden in (
        "BRAVE_SEARCH_API_KEY",
        "EXA_API_KEY",
        "build_italy_market_discovery.py",
        "build_france_market_discovery.py",
        "build_netherlands_market_discovery.py",
        "run_keyword_discovery_lab.py",
        "run_keyword_shadow_verification.py",
        "actions/workflows/${TARGET_WORKFLOW}/dispatches",
    ):
        assert forbidden not in text


def test_research_workflow_is_manual_only() -> None:
    text = (WORKFLOWS / "research-shadow-manual.yaml").read_text(encoding="utf-8")
    trigger = text.split("on:", 1)[1].split("jobs:", 1)[0]

    assert "workflow_dispatch:" in trigger
    assert "push:" not in trigger
    assert "pull_request:" not in trigger
    assert "schedule:" not in trigger
    assert "BRAVE_SEARCH_API_KEY" in text


def test_production_dispatch_waits_for_successful_ci() -> None:
    text = (WORKFLOWS / "production-dispatch-after-ci.yaml").read_text(encoding="utf-8")

    assert "workflow_run:" in text
    assert "workflows: [Tests]" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "TARGET_WORKFLOW: multi-market-daily-operator-checkpoint.yaml" in text
    assert "BRAVE_SEARCH_API_KEY" not in text
    assert "EXA_API_KEY" not in text
