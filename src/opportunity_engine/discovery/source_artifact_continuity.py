"""Fill missing canonical persistence artifacts for bounded checkpoint sources."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.finn_signal_artifacts import (
    write_finn_market_signal_report,
)
from opportunity_engine.discovery.unified_opportunity_report import (
    write_unified_opportunity_report,
)
from opportunity_engine.persistence.live_unified_persistence import (
    persist_unified_report_with_artifacts,
)

SCHEMA_VERSION = "source-artifact-continuity-1.0"
CURRENCIES = {"NO": "NOK", "SE": "SEK", "DE": "EUR"}


class SourceArtifactContinuityError(ValueError):
    pass


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SourceArtifactContinuityError(f"Missing source artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SourceArtifactContinuityError(f"Invalid JSON source artifact: {path}") from exc


def _time(value: object) -> datetime:
    text = _text(value)
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourceArtifactContinuityError(
            f"Invalid source timestamp: {text}"
        ) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _market(directory: Path, report: Mapping[str, Any]) -> str:
    values = (
        report.get("market_code"),
        _text(report.get("market"))[:2],
        directory.name.split("-", 1)[0],
    )
    for value in values:
        code = _text(value).upper()
        if code in CURRENCIES:
            return code
    raise SourceArtifactContinuityError(
        f"Cannot infer market code for source artifact directory: {directory}"
    )


def ensure_source_artifact_continuity(
    output_dir: str | Path, *, config_path: str | Path = "alembic.ini"
) -> dict[str, Any]:
    directory = Path(output_dir)
    candidates_path = directory / "all-discovered-candidates.json"
    run_report_path = directory / "search-run-report.json"
    if not candidates_path.exists() or not run_report_path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "NOT_APPLICABLE",
            "output_dir": directory.as_posix(),
            "reason": "source did not emit discovery candidates and a search report",
        }
    raw_candidates, report = _load(candidates_path), _load(run_report_path)
    if not isinstance(raw_candidates, list) or not isinstance(report, Mapping):
        raise SourceArtifactContinuityError("Invalid source discovery artifact contract")
    candidates = [item for item in raw_candidates if isinstance(item, Mapping)]
    market_code = _market(directory, report)
    generated_at = _time(report.get("discovered_at"))
    unified_path = directory / "unified-opportunity-report.json"
    summary_path = directory / "unified-persistence-summary.json"
    created = False
    if not summary_path.exists():
        unified_path = write_unified_opportunity_report(
            {"all_discovered_candidates": candidates},
            directory,
            generated_at=generated_at,
            market_code=market_code,
            currency=CURRENCIES[market_code],
        )
        persist_unified_report_with_artifacts(
            unified_path,
            directory,
            database_url=f"sqlite:///{directory / 'opportunity_engine.db'}",
            config_path=config_path,
        )
        created = True
    signal_path, signal_count = write_finn_market_signal_report(
        directory,
        candidates,
        generated_at=generated_at,
        market_code=market_code,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SUCCESS",
        "output_dir": directory.as_posix(),
        "market_code": market_code,
        "currency": CURRENCIES[market_code],
        "candidate_count": len(candidates),
        "canonical_persistence_created": created,
        "unified_report_path": unified_path.as_posix() if unified_path.exists() else None,
        "persistence_summary_path": summary_path.as_posix() if summary_path.exists() else None,
        "market_signal_report_path": signal_path.as_posix() if signal_path else None,
        "market_signal_count": signal_count,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
