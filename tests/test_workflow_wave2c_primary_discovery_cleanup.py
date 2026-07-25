from pathlib import Path


WORKFLOW = Path('.github/workflows/discovery-v1.2-live-pilot.yml')
TESTS_WORKFLOW = Path('.github/workflows/tests.yml')


def test_wave2c_primary_discovery_workflow_scope() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')

    assert 'name: 1 — Discover Clothing Inventory Opportunities' in text
    assert 'workflow_dispatch:' in text
    assert 'contract-tests:' in text
    assert 'live-pilot:' in text
    assert "if: ${{ github.event_name == 'workflow_dispatch' }}" in text

    for path in (
        '.github/workflows/discovery-v1.2-live-pilot.yml',
        'src/opportunity_engine/discovery/models.py',
        'src/opportunity_engine/discovery/quality_engine.py',
        'src/opportunity_engine/discovery/result_filter.py',
        'src/opportunity_engine/discovery/live_search.py',
        'src/opportunity_engine/discovery/query_builder.py',
        'src/opportunity_engine/discovery/search_provider.py',
        'scripts/run_discovery_v12_live_pilot.py',
        'tests/test_discovery_v12_live_pilot.py',
        'tests/test_discovery_v15_result_filter.py',
        'tests/test_discovery_v16_quality_engine.py',
    ):
        assert f'- "{path}"' in text

    assert 'pytest tests/test_discovery_v16_quality_engine.py -q' in text
    assert 'pytest tests/test_discovery_v15_result_filter.py -q' in text
    assert 'pytest tests/test_discovery_v12_live_pilot.py -q' in text
    assert 'Run regression suite' not in text
    assert '\n        run: pytest -q\n' not in text

    assert 'BRAVE_SEARCH_API_KEY: ${{ secrets.BRAVE_SEARCH_API_KEY }}' in text
    assert 'artifacts/discovery-v1.6-live-report.json' in text
    assert 'artifacts/discovery-v1.6-phone-report.txt' in text
    assert 'name: discovery-v1.6-opportunity-quality-engine' in text


def test_tests_workflow_remains_full_regression_gate() -> None:
    text = TESTS_WORKFLOW.read_text(encoding='utf-8')
    assert 'pytest -q > pytest-output.log 2>&1' in text
    assert 'name: pytest-output' in text
