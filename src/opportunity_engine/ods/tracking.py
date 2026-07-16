"""Adapters that feed ODS workflow opportunities into persistent memory."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .memory import MemoryRunResult, OpportunityMemoryEngine
from .models import OpportunityCandidate
from .scanner import ConnectorScanStatus, ScanSnapshot


def track_workflow_opportunities(
    candidates: Iterable[OpportunityCandidate],
    *,
    storage_path: str | Path,
    country: str | None = None,
    scan_id: str | None = None,
) -> MemoryRunResult:
    """Persist one workflow result using the same snapshot contract as the scanner.

    This adapter lets the current curated ODS workflow use the memory engine today.
    Future live connectors will pass their ``ScanSnapshot`` directly to the same
    memory engine without changing the storage contract.
    """
    opportunities = tuple(candidates)
    now = datetime.now(timezone.utc)
    snapshot = ScanSnapshot(
        scan_id=scan_id or f"workflow-{now.strftime('%Y%m%dT%H%M%S%fZ')}",
        started_at=now,
        completed_at=now,
        documents=(),
        opportunities=opportunities,
        connector_statuses=(
            ConnectorScanStatus(
                connector_name="ods_curated_workflow",
                status="completed",
                document_count=0,
            ),
        ),
        duplicate_count=0,
    )
    return OpportunityMemoryEngine(storage_path).run(snapshot, country=country)
