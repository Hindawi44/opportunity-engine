"""Remove volatile search-run fields before Brave signals enter persistence.

The radar report may expose query/rank diagnostics for operators, but those
values must not create a changed SQLite observation when the underlying public
page title, snippet, URL, classification, or status did not change.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.brave_market_signal_radar import (
    ProviderFactory,
    collect_manifest_brave_market_signals as _collect_raw_brave_market_signals,
)


_VOLATILE_SIGNAL_METADATA = {"query_id", "query", "source_rank"}
_VOLATILE_EVIDENCE_METADATA = {"query_id", "source_rank"}


def stabilize_brave_signal(signal: Mapping[str, Any]) -> dict[str, Any]:
    """Return a persistence-safe Brave signal with stable semantic state."""
    payload = deepcopy(dict(signal))
    metadata = payload.get("metadata")
    if isinstance(metadata, Mapping):
        payload["metadata"] = {
            key: deepcopy(value)
            for key, value in metadata.items()
            if key not in _VOLATILE_SIGNAL_METADATA
        }

    evidence = payload.get("evidence")
    if isinstance(evidence, list):
        stable_evidence: list[dict[str, Any]] = []
        for raw in evidence:
            if not isinstance(raw, Mapping):
                continue
            item = deepcopy(dict(raw))
            item["captured_at"] = None
            evidence_metadata = item.get("metadata")
            if isinstance(evidence_metadata, Mapping):
                item["metadata"] = {
                    key: deepcopy(value)
                    for key, value in evidence_metadata.items()
                    if key not in _VOLATILE_EVIDENCE_METADATA
                }
            stable_evidence.append(item)
        payload["evidence"] = stable_evidence
    return payload


def _rewrite_artifact(path: Path, stable_by_id: Mapping[str, Mapping[str, Any]]) -> None:
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict) or not isinstance(payload.get("signals"), list):
        return

    rewritten: list[Any] = []
    for raw in payload["signals"]:
        if not isinstance(raw, Mapping):
            rewritten.append(raw)
            continue
        signal_id = str(raw.get("signal_id") or "").strip()
        rewritten.append(deepcopy(stable_by_id.get(signal_id, raw)))
    payload["signals"] = rewritten

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def collect_manifest_brave_market_signals(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at=None,
    environment=None,
    provider_factory: ProviderFactory | None = None,
    queries_per_market: int = 2,
    results_per_query: int = 10,
    freshness: str | None = "pm",
) -> dict[str, Any]:
    """Run the bounded radar and normalize its signals for stable replay."""
    kwargs: dict[str, Any] = {
        "root": root,
        "observed_at": observed_at,
        "environment": environment,
        "queries_per_market": queries_per_market,
        "results_per_query": results_per_query,
        "freshness": freshness,
    }
    if provider_factory is not None:
        kwargs["provider_factory"] = provider_factory
    report = _collect_raw_brave_market_signals(manifest, **kwargs)

    root_path = Path(root)
    stable_by_id: dict[str, dict[str, Any]] = {}
    for source in report.get("sources") or []:
        if not isinstance(source, dict):
            continue
        stable_signals: list[dict[str, Any]] = []
        for raw in source.get("signals") or []:
            if not isinstance(raw, Mapping):
                continue
            stable = stabilize_brave_signal(raw)
            signal_id = str(stable.get("signal_id") or "").strip()
            if signal_id:
                stable_by_id[signal_id] = stable
            stable_signals.append(stable)
        source["signals"] = stable_signals

        artifact_path = str(source.get("artifact_path") or "").strip()
        if artifact_path:
            path = Path(artifact_path)
            if not path.is_absolute():
                path = root_path / path
            _rewrite_artifact(path, stable_by_id)

    report["stable_replay_fields_removed"] = {
        "signal_metadata": sorted(_VOLATILE_SIGNAL_METADATA),
        "evidence_metadata": sorted(_VOLATILE_EVIDENCE_METADATA),
        "evidence_captured_at": True,
    }
    return report
