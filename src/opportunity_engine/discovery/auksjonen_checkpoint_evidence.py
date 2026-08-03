"""Reconcile Auksjonen verification blockers in the final operator checkpoint.

The base checkpoint predates the source-native Auksjonen lifecycle adapter and may
inject a conservative legacy blocker list. This module replaces that list only when
the current run produced an auditable Auksjonen candidate carrying the separated
verification_blockers and analysis_tasks contracts.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _text_list(value: object) -> list[str]:
    if isinstance(value, str):
        text = _compact(value)
        return [text] if text else []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    result: list[str] = []
    for item in value:
        text = _compact(item)
        if text and text not in result:
            result.append(text)
    return result


def _auksjonen_spec(manifest: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for spec in manifest.get("sources") or []:
        if not isinstance(spec, Mapping):
            continue
        source_name = _compact(spec.get("source_name") or spec.get("source"))
        market_code = _compact(spec.get("market_code")).upper()
        if market_code == "NO" and source_name.casefold().startswith("auksjonen"):
            return spec
    return None


def _candidate_map(
    manifest: Mapping[str, Any],
    *,
    root: str | Path,
) -> dict[str, dict[str, Any]]:
    spec = _auksjonen_spec(manifest)
    if spec is None:
        return {}
    artifact_dir = Path(root) / _compact(spec.get("artifact_dir"))
    candidates_path = artifact_dir / _compact(
        spec.get("candidates_file") or "all-discovered-candidates.json"
    )
    if not candidates_path.exists():
        return {}
    payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Auksjonen candidate artifact must be a JSON array")

    result: dict[str, dict[str, Any]] = {}
    for raw in payload:
        if not isinstance(raw, Mapping):
            continue
        identity = _compact(
            raw.get("opportunity_identity")
            or raw.get("canonical_url")
            or raw.get("url")
        )
        blockers = _text_list(
            raw.get("verification_blockers") or raw.get("missing_information")
        )
        tasks = _text_list(raw.get("analysis_tasks"))
        if identity and blockers:
            result[identity] = {
                "verification_blockers": blockers,
                "analysis_tasks": tasks,
            }
    return result


def reconcile_auksjonen_checkpoint_evidence(
    report: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
) -> dict[str, Any]:
    """Return a checkpoint copy using current Auksjonen evidence contracts."""
    reconciled = deepcopy(dict(report))
    candidates = _candidate_map(manifest, root=root)
    if not candidates:
        return reconciled

    selected_identity = _compact(
        (reconciled.get("next_human_action") or {}).get("opportunity_identity")
    )
    for record in reconciled.get("deduplicated_opportunities") or []:
        if not isinstance(record, dict):
            continue
        identity = _compact(record.get("opportunity_identity"))
        source_names = {
            _compact(item).casefold() for item in record.get("source_names") or []
        }
        candidate = candidates.get(identity)
        if candidate is None or not any(
            value.startswith("auksjonen") for value in source_names
        ):
            continue
        record["missing_evidence"] = list(candidate["verification_blockers"])
        record["analysis_tasks"] = list(candidate["analysis_tasks"])

        if identity == selected_identity:
            action = reconciled.get("next_human_action")
            if isinstance(action, dict):
                action["missing_evidence"] = list(candidate["verification_blockers"])
                action["analysis_tasks"] = list(candidate["analysis_tasks"])

    all_missing: set[str] = set()
    for record in reconciled.get("deduplicated_opportunities") or []:
        if not isinstance(record, Mapping):
            continue
        all_missing.update(_text_list(record.get("missing_evidence")))
    reconciled["missing_evidence"] = sorted(all_missing)
    return reconciled
