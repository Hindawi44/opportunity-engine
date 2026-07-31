from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/daily-opportunity-pipeline.yml")


def test_generate_installs_runtime_dependencies_before_pipeline_execution() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    install_command = "python -m pip install -r requirements.txt"
    pipeline_command = (
        'python scripts/run_v2_automated_pipeline.py --trigger "$PIPELINE_TRIGGER"'
    )

    assert install_command in workflow
    assert pipeline_command in workflow
    assert workflow.index(install_command) < workflow.index(pipeline_command)
