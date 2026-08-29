from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_search_experiment_bridge_imports_in_clean_interpreter() -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = "src:."
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from opportunity_engine.search_experiment_execution_bridge_v1 import select_search_experiment_spec; assert callable(select_search_experiment_spec)",
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
