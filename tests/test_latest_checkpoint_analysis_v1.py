from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from opportunity_engine.discovery.latest_checkpoint_analysis import (
    extract_checkpoint_analysis,
)


def _archive() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "artifacts/multi-market-daily-operator-checkpoint/one-opportunity-daily-analysis.json",
            json.dumps({"selection_status": "SELECTED"}),
        )
        archive.writestr(
            "artifacts/multi-market-daily-operator-checkpoint/one-opportunity-daily-analysis.txt",
            "selected\n",
        )
        archive.writestr("artifacts/multi-market-inputs/no-auksjonen/opportunity_engine.db", b"ignored")
    return buffer.getvalue()


def test_extracts_only_allow_listed_analysis_files(tmp_path: Path) -> None:
    extracted = extract_checkpoint_analysis(_archive(), tmp_path)
    assert (tmp_path / "one-opportunity-daily-analysis.json").exists()
    assert (tmp_path / "one-opportunity-daily-analysis.txt").exists()
    assert not (tmp_path / "opportunity_engine.db").exists()
    assert len(extracted) == 2
