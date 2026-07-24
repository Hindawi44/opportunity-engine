#!/usr/bin/env python3
"""Focused V2.8.2A pass that integrates only valid persisted market comparables."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from opportunity_engine.external_evidence_loop import ResearchNeed
from opportunity_engine.investment_file_sync import InvestmentFileSynchronizer
from opportunity_engine.living_investment_file import LivingInvestmentFileRepository
from opportunity_engine.research_bootstrap import ResearchBootstrapPipeline

from run_research_bootstrap import ProductionExternalEvidenceLoop, _search_subject, build_loop


def _evidence_type_value(item: Any) -> str:
    value = getattr(item, "evidence_type", "")
    return str(getattr(value, "value", value)).casefold()


def _has_verified_nok_observation(item: Any) -> bool:
    """Return true only for a usable HTTPS market-price observation in NOK.

    Older runs may contain ``market_price`` evidence shells with no numeric observation.
    Counting those shells as completed comparables stops Brave searches prematurely and
    leaves the financial bridge with zero verified comparables.
    """
    if _evidence_type_value(item) != "market_price":
        return False
    source_url = str(getattr(item, "source_url", "") or "").strip()
    if not source_url.startswith("https://"):
        return False
    for observation in getattr(item, "observations", ()) or ():
        value = getattr(observation, "numeric_value", None)
        currency = str(getattr(observation, "currency", "") or "").upper()
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value > 0
            and currency == "NOK"
        ):
            return True
    return False


class ComparableCollectionLoop(ProductionExternalEvidenceLoop):
    """Generate query variants and link persisted evidence to living scenarios."""

    def detect_needs(self, investment_file: Any) -> tuple[ResearchNeed, ...]:
        opportunity_id = str(investment_file.opportunity_id)
        existing = tuple(getattr(self.evidence_repository, "list_for_opportunity", lambda _id: ())(opportunity_id))
        existing_prices = sum(_has_verified_nok_observation(item) for item in existing)
        if existing_prices >= 3:
            return ()

        subject = _search_subject(str(getattr(investment_file, "title", "")))
        variants = (
            f"{subject} brukt pris Norge",
            f"{subject} til salgs pris Norge",
            f"{subject} site:finn.no",
        )
        missing = max(1, 3 - existing_prices)
        return tuple(
            ResearchNeed("market", query, "Accumulate three verified independent market comparables", "high")
            for query in variants[: min(2, missing)]
        )

    def _store_external_evidence(self, investment_file: Any, **kwargs: Any) -> tuple[str | bool, str | None]:
        """Return the living-file evidence ID accepted by ScenarioGenerator.

        The persistent EvidenceRepository uses ``rev_*`` IDs, while the living investment
        file creates its own mirror Evidence ID. ScenarioGenerator validates IDs against
        the living file, so passing the repository ID causes ``Unknown evidence ids``.
        This method reloads the persisted record, then resolves its living mirror and
        returns the mirror ID for scenario regeneration.
        """
        changed, persisted_id = super()._store_external_evidence(investment_file, **kwargs)
        if not persisted_id:
            return changed, None

        loader = getattr(self.evidence_repository, "load", None)
        if callable(loader):
            try:
                persisted = loader(str(investment_file.opportunity_id), str(persisted_id))
                persisted_id = str(getattr(persisted, "evidence_id", persisted_id))
            except (FileNotFoundError, ValueError, OSError):
                pass

        expected_note = f"research:{persisted_id}"
        for item in getattr(investment_file, "evidence", ()):
            if str(getattr(item, "notes", "")) == expected_note:
                living_id = str(getattr(item, "evidence_id", "")).strip()
                if living_id:
                    return changed, living_id
        return changed, None


def build_comparable_loop() -> ComparableCollectionLoop:
    base = build_loop()
    return ComparableCollectionLoop(
        search_provider=base.search_provider,
        evidence_repository=base.evidence_repository,
        evidence_factory=base.evidence_factory,
        evidence_scorer=base.evidence_scorer,
        scenario_generator=base.scenario_generator,
        market_comparables_engine=base.market_comparables_engine,
        comparable_adapter=base.comparable_adapter,
        max_searches_per_opportunity=2,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", nargs="?", default="data/todays_opportunities.json")
    parser.add_argument("--output", default="data/validation/v2.8.2-comparable-collection.json")
    parser.add_argument("--investment-files-dir", default="data/investment_files")
    parser.add_argument("--threshold", type=float, default=25.0)
    parser.add_argument("--selection-limit", type=int, default=3)
    args = parser.parse_args()

    payload = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    InvestmentFileSynchronizer(args.investment_files_dir).sync_payload(payload)
    key_present = bool((os.getenv("BRAVE_API_KEY") or os.getenv("BRAVE_SEARCH_API_KEY") or "").strip())
    pipeline = ResearchBootstrapPipeline(
        investment_repository=LivingInvestmentFileRepository(args.investment_files_dir),
        external_loop_factory=build_comparable_loop,
        research_threshold=args.threshold,
        selection_limit=args.selection_limit,
        enabled=key_present,
        disabled_reason="missing_brave_api_key",
    )
    report = pipeline.run(payload).to_dict()
    report["schema_version"] = "2.8.2A"
    report["audit_scope"] = "Valid comparable gate and evidence integration"
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
