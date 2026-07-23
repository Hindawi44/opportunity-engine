"""Scenario generation that resolves repository evidence IDs to living-file evidence IDs."""
from __future__ import annotations

from typing import Any, Iterable

from .scenario_generator import ScenarioGeneratorEngine


class LinkedScenarioGeneratorEngine(ScenarioGeneratorEngine):
    """Map persisted research evidence IDs to their living-file mirror IDs before generation."""

    def generate(
        self,
        item: Any,
        inputs: Any | None = None,
        *,
        evidence_ids: Iterable[str] = (),
    ):
        known = {str(getattr(entry, "evidence_id", "")): entry for entry in getattr(item, "evidence", ())}
        by_research_id = {
            str(getattr(entry, "notes", ""))[len("research:"):]: str(getattr(entry, "evidence_id", ""))
            for entry in getattr(item, "evidence", ())
            if str(getattr(entry, "notes", "")).startswith("research:")
        }

        resolved: list[str] = []
        for evidence_id in evidence_ids:
            value = str(evidence_id)
            if value in known:
                resolved.append(value)
                continue
            mirror_id = by_research_id.get(value)
            if mirror_id:
                resolved.append(mirror_id)

        return super().generate(
            item,
            inputs,
            evidence_ids=tuple(dict.fromkeys(resolved)),
        )
