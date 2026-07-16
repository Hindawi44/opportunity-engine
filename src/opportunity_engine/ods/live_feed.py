"""Persistent live opportunity feed built from grounded collector results."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable

from .brreg_collector import BrregCollectionResult, BrregOpportunityCollector, BrregSearchSlice


@dataclass(frozen=True)
class FeedItem:
    opportunity_id: str
    title: str
    category: str
    description: str
    source: str
    discovered_at: str
    last_seen_at: str
    times_seen: int
    score: float | None
    status: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class LiveFeedResult:
    generated_at: str
    items: tuple[FeedItem, ...]
    new_count: int
    updated_count: int
    unchanged_count: int
    removed_count: int
    collector: BrregCollectionResult


class LiveOpportunityFeed:
    """Run bounded live collection and maintain a deduplicated JSON feed."""

    def __init__(self, feed_path: str | Path, memory_path: str | Path, *, shortlist_size: int = 20) -> None:
        self.feed_path = Path(feed_path)
        self.collector = BrregOpportunityCollector(memory_path, shortlist_size=shortlist_size)

    def refresh(self, slices: Iterable[BrregSearchSlice], *, country: str = "Norway") -> LiveFeedResult:
        collection = self.collector.collect(slices, country=country)
        now = datetime.now(timezone.utc).isoformat()
        previous = self._load()
        ranked_scores = {
            item.opportunity.opportunity_id: item.final_score
            for item in collection.ranked_opportunities
        }
        current_ids = set()
        new_count = updated_count = unchanged_count = 0

        for candidate in collection.snapshot.opportunities:
            current_ids.add(candidate.opportunity_id)
            existing = previous.get(candidate.opportunity_id)
            fingerprint = _fingerprint(candidate.title, candidate.description, candidate.evidence)
            if existing is None:
                new_count += 1
                discovered_at = now
                times_seen = 1
                status = "NEW"
            else:
                discovered_at = str(existing.get("discovered_at") or now)
                times_seen = int(existing.get("times_seen") or 0) + 1
                old_fingerprint = str(existing.get("fingerprint") or "")
                if old_fingerprint != fingerprint:
                    updated_count += 1
                    status = "UPDATED"
                else:
                    unchanged_count += 1
                    status = "UNCHANGED"
            previous[candidate.opportunity_id] = {
                "opportunity_id": candidate.opportunity_id,
                "title": candidate.title,
                "category": candidate.category,
                "description": candidate.description,
                "source": candidate.source_plugin,
                "discovered_at": discovered_at,
                "last_seen_at": now,
                "times_seen": times_seen,
                "score": ranked_scores.get(candidate.opportunity_id),
                "status": status,
                "evidence": list(candidate.evidence),
                "fingerprint": fingerprint,
                "active": True,
            }

        removed_count = 0
        for opportunity_id, record in previous.items():
            if opportunity_id not in current_ids and record.get("active", True):
                record["active"] = False
                record["status"] = "REMOVED"
                removed_count += 1

        self._save(previous)
        items = tuple(
            FeedItem(
                opportunity_id=str(record["opportunity_id"]),
                title=str(record["title"]),
                category=str(record["category"]),
                description=str(record["description"]),
                source=str(record["source"]),
                discovered_at=str(record["discovered_at"]),
                last_seen_at=str(record["last_seen_at"]),
                times_seen=int(record["times_seen"]),
                score=float(record["score"]) if record.get("score") is not None else None,
                status=str(record["status"]),
                evidence=tuple(str(value) for value in record.get("evidence", ())),
            )
            for record in sorted(
                previous.values(),
                key=lambda value: (not bool(value.get("active", True)), -float(value.get("score") or 0), str(value.get("title", ""))),
            )
        )
        return LiveFeedResult(now, items, new_count, updated_count, unchanged_count, removed_count, collection)

    def _load(self) -> dict[str, dict[str, object]]:
        if not self.feed_path.exists():
            return {}
        try:
            payload = json.loads(self.feed_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not read live feed storage: {exc}") from exc
        records = payload.get("records", {}) if isinstance(payload, dict) else {}
        return records if isinstance(records, dict) else {}

    def _save(self, records: dict[str, dict[str, object]]) -> None:
        self.feed_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "records": records}
        self.feed_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fingerprint(title: str, description: str, evidence: tuple[str, ...]) -> str:
    return "|".join((title.strip(), description.strip(), *sorted(evidence)))
