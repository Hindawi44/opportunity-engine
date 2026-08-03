from __future__ import annotations

import json
from pathlib import Path

from opportunity_engine.discovery.auksjonen_checkpoint_evidence import (
    reconcile_auksjonen_checkpoint_evidence,
)
from opportunity_engine.discovery.auksjonen_unified_lifecycle import (
    AUKSJONEN_ANALYSIS_TASKS,
    AUKSJONEN_REQUIRED_VERIFICATION,
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_final_checkpoint_uses_verification_blockers_not_analysis_tasks(
    tmp_path: Path,
) -> None:
    identity = "https://ny.auksjonen.no/auksjon/torget/test/528194"
    _write(
        tmp_path / "no-auksjonen" / "all-discovered-candidates.json",
        [
            {
                "opportunity_identity": identity,
                "verification_blockers": list(AUKSJONEN_REQUIRED_VERIFICATION),
                "analysis_tasks": list(AUKSJONEN_ANALYSIS_TASKS),
            }
        ],
    )
    manifest = {
        "sources": [
            {
                "market_code": "NO",
                "source_name": "Auksjonen.no",
                "artifact_dir": "no-auksjonen",
                "candidates_file": "all-discovered-candidates.json",
            }
        ]
    }
    report = {
        "deduplicated_opportunities": [
            {
                "opportunity_identity": identity,
                "source_names": ["Auksjonen.no"],
                "missing_evidence": [
                    "verified exact item-page evidence",
                    "verified quantity and condition",
                    "documented final payable price including auction fees and VAT",
                    "domestic pickup or delivery logistics basis",
                    "documented resale-market evidence",
                ],
            },
            {
                "opportunity_identity": "blinto:historical",
                "source_names": ["Blinto"],
                "missing_evidence": ["price"],
            },
        ],
        "missing_evidence": [
            "verified exact item-page evidence",
            "verified quantity and condition",
            "documented final payable price including auction fees and VAT",
            "domestic pickup or delivery logistics basis",
            "documented resale-market evidence",
            "price",
        ],
        "next_human_action": {
            "action": "REVIEW_ONE_OPPORTUNITY",
            "opportunity_identity": identity,
            "missing_evidence": ["legacy blocker"],
        },
    }

    reconciled = reconcile_auksjonen_checkpoint_evidence(
        report,
        manifest,
        root=tmp_path,
    )

    auksjonen = reconciled["deduplicated_opportunities"][0]
    assert auksjonen["missing_evidence"] == list(AUKSJONEN_REQUIRED_VERIFICATION)
    assert auksjonen["analysis_tasks"] == list(AUKSJONEN_ANALYSIS_TASKS)
    assert reconciled["deduplicated_opportunities"][1]["missing_evidence"] == [
        "price"
    ]
    assert reconciled["missing_evidence"] == [
        "price",
        "verified exact item-page evidence",
    ]
    assert reconciled["next_human_action"]["missing_evidence"] == list(
        AUKSJONEN_REQUIRED_VERIFICATION
    )
    assert reconciled["next_human_action"]["analysis_tasks"] == list(
        AUKSJONEN_ANALYSIS_TASKS
    )


def test_checkpoint_is_unchanged_without_current_auksjonen_candidates(
    tmp_path: Path,
) -> None:
    report = {
        "deduplicated_opportunities": [],
        "missing_evidence": ["existing"],
    }
    manifest = {"sources": []}

    assert reconcile_auksjonen_checkpoint_evidence(
        report,
        manifest,
        root=tmp_path,
    ) == report
