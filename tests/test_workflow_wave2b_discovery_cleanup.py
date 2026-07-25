from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


EXPECTED = {
    ".github/workflows/discovery-v1-clothing-inventory.yml": {
        "paths": (
            ".github/workflows/discovery-v1-clothing-inventory.yml",
            "src/opportunity_engine/discovery/models.py",
            "src/opportunity_engine/discovery/opportunity_maps.py",
            "src/opportunity_engine/discovery/classifier.py",
            "tests/test_discovery_opportunity_maps.py",
            "tests/test_discovery_classifier.py",
        ),
        "focused": "pytest tests/test_discovery_opportunity_maps.py tests/test_discovery_classifier.py -q",
    },
    ".github/workflows/discovery-v1.1-live-search.yml": {
        "paths": (
            ".github/workflows/discovery-v1.1-live-search.yml",
            "src/opportunity_engine/discovery/brave_search.py",
            "src/opportunity_engine/discovery/live_search.py",
            "src/opportunity_engine/discovery/search_provider.py",
            "src/opportunity_engine/discovery/query_builder.py",
            "src/opportunity_engine/discovery/result_filter.py",
            "tests/test_discovery_v11_live_search.py",
        ),
        "focused": "pytest tests/test_discovery_v11_live_search.py -q",
    },
}


def test_wave2b_discovery_workflows_are_focused_and_path_scoped() -> None:
    for relative_path, expected in EXPECTED.items():
        text = (ROOT / relative_path).read_text(encoding="utf-8")

        assert "workflow_dispatch:" in text
        assert expected["focused"] in text
        assert "run: pytest -q" not in text
        assert "Run full regression suite" not in text
        assert "Run complete regression suite" not in text

        for owned_path in expected["paths"]:
            assert f'- "{owned_path}"' in text


def test_canonical_regression_workflow_remains_complete() -> None:
    text = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")

    assert "pytest -q > pytest-output.log 2>&1" in text
    assert "name: pytest-output" in text
    assert "path: pytest-output.log" in text
