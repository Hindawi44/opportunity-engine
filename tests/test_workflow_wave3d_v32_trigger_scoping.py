from pathlib import Path


WORKFLOW = Path('.github/workflows/v3.2-continuous-opportunity-monitoring.yml')

APPROVED_PATHS = (
    '.github/workflows/v3.2-continuous-opportunity-monitoring.yml',
    'scripts/run_v32_continuous_opportunity_monitoring.py',
    'src/opportunity_engine/continuous_opportunity_monitoring.py',
    'scripts/run_v31_live_batch_validation.py',
    'tests/test_v32_continuous_opportunity_monitoring.py',
    'data/live_validation/v3.1-auksjonen-live-batch.json',
)


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_v32_pull_request_trigger_has_exact_approved_paths():
    text = _workflow_text()

    assert 'pull_request:' in text
    assert 'branches: [ main ]' in text
    assert 'paths:' in text

    path_lines = {
        line.strip()[3:-1]
        for line in text.splitlines()
        if line.strip().startswith("- '") and line.strip().endswith("'")
    }
    assert path_lines == set(APPROVED_PATHS)


def test_v32_manual_state_cache_report_and_artifact_are_preserved():
    text = _workflow_text()

    required_fragments = (
        'name: V3.2 Continuous Opportunity Monitoring',
        'workflow_dispatch:',
        'continuous-monitoring:',
        "python-version: '3.11'",
        'PYTHONPATH: ${{ github.workspace }}/src:${{ github.workspace }}',
        'path: data/monitoring/v3.2-seen-state.json',
        'key: v3.2-monitoring-state-${{ github.run_id }}',
        'v3.2-monitoring-state-',
        'pytest tests/test_v32_continuous_opportunity_monitoring.py -q',
        'python scripts/run_v32_continuous_opportunity_monitoring.py',
        'cat data/validation/v3.2-continuous-monitoring.json || true',
        'name: v3.2-continuous-monitoring',
        'path: data/validation/v3.2-continuous-monitoring.json',
        'if-no-files-found: warn',
    )

    for fragment in required_fragments:
        assert fragment in text

    assert "cron: '17 * * * *'" not in text
    assert '\n  schedule:' not in text
    assert 'Legacy hourly scheduler retired' in text
    assert text.count('if: always()') == 2
