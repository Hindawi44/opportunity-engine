from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_cli_writes_detached_taxonomy_audit(tmp_path: Path) -> None:
    input_path = tmp_path / "candidates.json"
    output_path = tmp_path / "audit.json"
    input_path.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "candidate_id": "fabric-1",
                        "title": "Restlager stoffruller og metervare selges",
                    },
                    {
                        "candidate_id": "noise-1",
                        "title": "Varelager for kjøkken- og møbelproduksjon",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_textile_taxonomy_audit.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    printed = json.loads(result.stdout)
    assert saved["candidate_count"] == 2
    assert saved["included_count"] == 1
    assert saved["rejected_count"] == 1
    assert saved["decisions"][0]["taxonomy"]["primary_category"] == (
        "FABRIC_TEXTILE_STOCK"
    )
    assert saved["decisions"][1]["taxonomy"]["status"] == "OUT_OF_SCOPE"
    assert printed == {
        "candidate_count": 2,
        "included_count": 1,
        "output": str(output_path),
        "rejected_count": 1,
    }
