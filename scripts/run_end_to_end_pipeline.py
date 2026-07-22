from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


@dataclass
class StageResult:
    name: str
    command: list[str]
    status: str
    started_at: str
    finished_at: str | None = None
    exit_code: int | None = None


STAGES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("source_coverage", ("scripts/build_source_coverage_report.py",)),
    (
        "public_auction_events",
        (
            "scripts/build_public_auction_event_leads.py",
            "--output",
            "data/public_auction_event_leads.json",
            "--limit",
            "10",
        ),
    ),
    (
        "brave_search",
        (
            "scripts/collect_brave_search_results.py",
            "--config",
            "config/brave_search_queries.json",
            "--output",
            "data/web_search_results.json",
        ),
    ),
    (
        "web_discovery",
        (
            "scripts/build_web_discovery_leads.py",
            "--input",
            "data/web_search_results.json",
            "--output",
            "data/discovery_leads.json",
            "--limit",
            "100",
        ),
    ),
    (
        "daily_opportunities",
        (
            "scripts/run_daily_pipeline.py",
            "--finn-rows",
            "100",
            "--output",
            "data/todays_opportunities.json",
            "--alerts-output",
            "data/smart_alerts.json",
        ),
    ),
    (
        "auksjonen_diagnostics",
        (
            "scripts/annotate_auksjonen_diagnostics.py",
            "--snapshot",
            "data/todays_opportunities.json",
        ),
    ),
    (
        "review_queue",
        (
            "scripts/build_opportunity_review_queue.py",
            "--snapshot",
            "data/todays_opportunities.json",
            "--output",
            "data/opportunity_review_queue.json",
            "--limit",
            "12",
        ),
    ),
    (
        "listing_metadata",
        (
            "scripts/enrich_auksjonen_listing_metadata.py",
            "--queue",
            "data/opportunity_review_queue.json",
            "--output",
            "data/opportunity_review_queue.json",
            "--evidence-output",
            "data/listing_metadata_evidence.json",
        ),
    ),
    (
        "market_evidence_queue",
        (
            "scripts/build_market_evidence_discovery_queue.py",
            "--queue",
            "data/opportunity_review_queue.json",
            "--output",
            "data/market_evidence_discovery_queue.json",
        ),
    ),
    (
        "market_price_candidates",
        (
            "scripts/collect_market_price_candidates.py",
            "--queue",
            "data/opportunity_review_queue.json",
            "--output",
            "data/market_price_candidates.json",
            "--limit",
            "5",
            "--results-per-query",
            "10",
        ),
    ),
    (
        "market_evidence_registry",
        (
            "scripts/build_market_evidence_registry.py",
            "--input",
            "data/market_price_candidates.json",
            "--output",
            "data/market_evidence_registry.json",
            "--review-output",
            "data/market_evidence_review_queue.json",
        ),
    ),
    (
        "opportunity_evidence",
        (
            "scripts/build_opportunity_evidence_registry.py",
            "--queue",
            "data/opportunity_review_queue.json",
            "--existing",
            "data/opportunity_evidence.json",
            "--market-evidence",
            "data/market_evidence_registry.json",
            "--output",
            "data/opportunity_evidence.json",
        ),
    ),
    (
        "economic_evaluation",
        (
            "scripts/build_economic_evaluation_queue.py",
            "--queue",
            "data/opportunity_review_queue.json",
            "--evidence",
            "data/opportunity_evidence.json",
            "--output",
            "data/economic_evaluation_queue.json",
        ),
    ),
    (
        "top5_report",
        (
            "scripts/build_top5_opportunity_report.py",
            "--queue",
            "data/opportunity_review_queue.json",
            "--evaluations",
            "data/economic_evaluation_queue.json",
            "--output",
            "data/top5_opportunities.json",
            "--limit",
            "5",
        ),
    ),
    (
        "opportunity_channels",
        (
            "scripts/build_opportunity_channels_report.py",
            "--actionable",
            "data/top5_opportunities.json",
            "--output",
            "data/opportunity_channels.json",
            "--limit",
            "5",
        ),
    ),
    (
        "source_funnel",
        (
            "scripts/build_source_funnel_report.py",
            "--coverage",
            "data/source_coverage.json",
            "--snapshot",
            "data/todays_opportunities.json",
            "--channels",
            "data/opportunity_channels.json",
            "--event-leads",
            "data/public_auction_event_leads.json",
            "--output",
            "data/source_funnel.json",
        ),
    ),
    ("source_expansion", ("scripts/build_source_expansion_status.py",)),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def publish_canonical_outputs(root: Path, generated_at: str) -> None:
    data = root / "data"
    shutil.copyfile(data / "top5_opportunities.json", data / "opportunities.json")
    shutil.copyfile(data / "todays_opportunities.json", data / "dashboard.json")

    report = {
        "schema_version": 1,
        "generated_at": generated_at,
        "status": "SUCCESS",
        "opportunities": load_json(data / "top5_opportunities.json"),
        "channels": load_json(data / "opportunity_channels.json"),
        "source_funnel": load_json(data / "source_funnel.json"),
        "alerts": load_json(data / "smart_alerts.json"),
    }
    write_json_atomic(data / "daily_report.json", report)


def run_pipeline(
    root: Path,
    *,
    stages: Sequence[tuple[str, Sequence[str]]] = STAGES,
    dry_run: bool = False,
) -> int:
    started_at = utc_now()
    status_path = root / "data/pipeline_run_status.json"
    results: list[StageResult] = []

    write_json_atomic(
        status_path,
        {
            "schema_version": 1,
            "status": "RUNNING",
            "started_at": started_at,
            "finished_at": None,
            "failed_stage": None,
            "stages": [],
        },
    )

    for name, arguments in stages:
        command = [sys.executable, *arguments]
        result = StageResult(
            name=name,
            command=command,
            status="RUNNING",
            started_at=utc_now(),
        )
        results.append(result)

        if dry_run:
            result.status = "SKIPPED_DRY_RUN"
            result.exit_code = 0
            result.finished_at = utc_now()
            continue

        completed = subprocess.run(command, cwd=root, check=False)
        result.exit_code = completed.returncode
        result.finished_at = utc_now()

        if completed.returncode != 0:
            result.status = "FAILED"
            write_json_atomic(
                status_path,
                {
                    "schema_version": 1,
                    "status": "FAILED",
                    "started_at": started_at,
                    "finished_at": utc_now(),
                    "failed_stage": name,
                    "stages": [asdict(item) for item in results],
                },
            )
            return completed.returncode

        result.status = "SUCCESS"

    if dry_run:
        write_json_atomic(
            status_path,
            {
                "schema_version": 1,
                "status": "DRY_RUN",
                "started_at": started_at,
                "finished_at": utc_now(),
                "failed_stage": None,
                "stages": [asdict(item) for item in results],
            },
        )
        return 0

    finished_at = utc_now()
    publish_canonical_outputs(root, finished_at)
    write_json_atomic(
        status_path,
        {
            "schema_version": 1,
            "status": "SUCCESS",
            "started_at": started_at,
            "finished_at": finished_at,
            "failed_stage": None,
            "stages": [asdict(item) for item in results],
            "canonical_outputs": {
                "opportunities": "data/opportunities.json",
                "dashboard": "data/dashboard.json",
                "daily_report": "data/daily_report.json",
                "alerts": "data/smart_alerts.json",
            },
        },
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the complete opportunity pipeline in strict dependency order."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root. Defaults to the parent directory of scripts/.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate orchestration order without executing stage scripts.",
    )
    args = parser.parse_args()
    return run_pipeline(args.root.resolve(), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
