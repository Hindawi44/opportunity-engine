from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery.signal_follow_up_source_verification import (
    OUTPUT_FILENAME,
    write_signal_follow_up_source_verification,
)


def test_writer_emits_artifact_and_attaches_zero_summary(tmp_path: Path) -> None:
    (tmp_path / "domain-market-intelligence-brief.json").write_text(
        json.dumps({"status": "SUCCESS"}), encoding="utf-8"
    )
    (tmp_path / "domain-market-intelligence-brief.txt").write_text(
        "BASE BRIEF\n", encoding="utf-8"
    )

    report = write_signal_follow_up_source_verification(
        tmp_path,
        follow_up_report={"cases": []},
    )

    assert report["status"] == "VALID_ZERO_NO_FOLLOW_UP_LEADS"
    artifact = json.loads((tmp_path / OUTPUT_FILENAME).read_text(encoding="utf-8"))
    assert artifact["candidate_lead_count"] == 0
    brief = json.loads(
        (tmp_path / "domain-market-intelligence-brief.json").read_text(encoding="utf-8")
    )
    assert brief["signal_follow_up_source_verification"]["source_page_verified_count"] == 0
    text = (tmp_path / "domain-market-intelligence-brief.txt").read_text(encoding="utf-8")
    assert "SIGNAL FOLLOW-UP SOURCE VERIFICATION V1" in text
    assert "promotion_to_opportunity_allowed: false" in text
