from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_query_gap_scout_imports_in_clean_interpreter() -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = "src:."
    result = subprocess.run(
        [sys.executable, "-c", "import opportunity_engine.automatic_query_gap_miss_scout"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
