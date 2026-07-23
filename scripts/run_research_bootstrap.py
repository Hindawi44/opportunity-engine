#!/usr/bin/env python3
"""Forward top preliminary candidates into the guarded External Evidence Loop."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from opportunity_engine.buyer_discovery import BuyerCandidate, BuyerDiscoveryEngine, BuyerType
from opportunity_engine.evidence_scoring import EvidenceScoringEngine
from opportunity_engine.evidence_store import (
    EvidenceConfidence,
    EvidenceDirection,
    EvidenceRepository,
    EvidenceType,
    ResearchEvidence,
)
from opportunity_engine.external_evidence_loop import ExternalEvidenceLoop
from opportunity_engine.external_market_comparables import ComparableCandidate, MarketComparablesEngine
from opportunity_engine.investment_file_sync import InvestmentFileSynchronizer
from opportunity_engine.living_investment_file import LivingInvestmentFileRepository
from opportunity_engine.ods.brave_search import BraveSearchClient
from opportunity_engine.research_bootstrap import ResearchBootstrapPipeline
from opportunity_engine.scenario_generator import ScenarioGeneratorEngine


def _explicit_price(item: dict[str, Any]) -> float | None:
    value = item.get("price_nok")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return None


def comparable_adapter(response: Any) -> Iterable[ComparableCandidate]:
    """Accept only Brave records already carrying an explicit numeric NOK price."""
    rows = response if isinstance(response, list) else []
    now = datetime.now(timezone.utc).isoformat()
    candidates: list[ComparableCandidate] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        price = _explicit_price(item)
        if price is None:
            continue
        url = str(item.get("url") or "")
        title = str(item.get("title") or "").strip()
        if not title or not url.startswith("https://"):
            continue
        candidates.append(ComparableCandidate(
            title=title,
            url=url,
            price_nok=price,
            source_name=str(item.get("source") or "Brave Search"),
            observed_at=str(item.get("published_at") or now),
            similarity_score=float(item.get("similarity_score") or 0.7),
        ))
    return tuple(candidates)


def buyer_adapter(response: Any) -> Iterable[BuyerCandidate]:
    """Convert explicit public search results into unconfirmed buyer candidates."""
    rows = response if isinstance(response, list) else []
    candidates: list[BuyerCandidate] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        name = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not name or not url.startswith("https://"):
            continue
        terms = tuple(
            token.casefold().strip(".,;:()[]{}")
            for token in name.split()
            if len(token.strip(".,;:()[]{}")) >= 4
        )[:12]
        candidates.append(BuyerCandidate(
            name=name,
            website_url=url,
            buyer_type=BuyerType.OTHER,
            source_url=url,
            source_name=str(item.get("source") or "Brave Search"),
            rationale="Public search result may match the opportunity; buying intent is unconfirmed.",
            matched_terms=terms,
        ))
    return tuple(candidates)


class ComparablesAdapter:
    def __init__(self) -> None:
        self.engine = MarketComparablesEngine()

    def evaluate(self, candidates: Iterable[ComparableCandidate]):
        return self.engine.analyse(candidates)


def evidence_factory(**kwargs: Any) -> ResearchEvidence:
    type_value = kwargs.pop("evidence_type")
    return ResearchEvidence.create(
        evidence_type=EvidenceType(type_value),
        confidence=EvidenceConfidence.MEDIUM,
        direction=EvidenceDirection.NEUTRAL,
        **kwargs,
    )


def build_loop() -> ExternalEvidenceLoop:
    return ExternalEvidenceLoop(
        search_provider=BraveSearchClient.from_environment(),
        evidence_repository=EvidenceRepository("data/evidence"),
        evidence_factory=evidence_factory,
        evidence_scorer=EvidenceScoringEngine(),
        scenario_generator=ScenarioGeneratorEngine(),
        market_comparables_engine=ComparablesAdapter(),
        buyer_discovery_engine=BuyerDiscoveryEngine(),
        comparable_adapter=comparable_adapter,
        buyer_adapter=buyer_adapter,
        max_searches_per_opportunity=2,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run V2.7.2.4.2 guarded research bootstrap")
    parser.add_argument("dataset", nargs="?", default="data/todays_opportunities.json")
    parser.add_argument("--output", default="data/validation/v2.7.2.4.2-bootstrap-report.json")
    parser.add_argument("--investment-files-dir", default="data/investment_files")
    parser.add_argument("--threshold", type=float, default=25.0)
    parser.add_argument("--selection-limit", type=int, default=3)
    args = parser.parse_args()

    source = Path(args.dataset)
    payload = json.loads(source.read_text(encoding="utf-8"))
    InvestmentFileSynchronizer(args.investment_files_dir).sync_payload(payload)

    key_present = bool((os.getenv("BRAVE_API_KEY") or os.getenv("BRAVE_SEARCH_API_KEY") or "").strip())
    pipeline = ResearchBootstrapPipeline(
        investment_repository=LivingInvestmentFileRepository(args.investment_files_dir),
        external_loop_factory=build_loop,
        research_threshold=args.threshold,
        selection_limit=args.selection_limit,
        enabled=key_present,
        disabled_reason="missing_brave_api_key",
    )
    report = pipeline.run(payload)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
