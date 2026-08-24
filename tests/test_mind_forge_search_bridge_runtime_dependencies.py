from pathlib import Path


WORKFLOW = Path(".github/workflows/mind-forge-live-research-launcher.yaml")


def test_search_bridge_dependencies_are_verified_before_paid_mind_forge_cycle():
    source = WORKFLOW.read_text(encoding="utf-8")

    dependency_step = source.index("Install bounded Creative V2 dependencies")
    paid_cycle = source.index("Run one autonomous MIND FORGE V2 cycle from the raw seed")
    preflight = source[dependency_step:paid_cycle]

    assert '"alembic>=1.14,<2.0"' in preflight
    assert "PYTHONPATH=src:. python -c" in preflight
    assert "Search Experiment bridge import: OK" in preflight
    assert "search_experiment_execution_bridge_v1" in preflight
