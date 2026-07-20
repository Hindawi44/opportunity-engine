"""End-to-end daily pipeline for authorized and public opportunity sources.

Missing market comparables or operating costs never become zero. Opportunities
remain ``monitor`` until verified inputs are supplied.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Iterable, Mapping

from .auksjonen import AuksjonenClient
from .bjaroy import BjaroyFeedClient
from .daily_opportunity_report import DailyOpportunityReportEngine
from .finn import FinnApiClient
from .konkurs_app import KonkursAppFeedClient
from .konkurskupp import KonkurskuppFeedClient
from .live_data import SourceDocument
from .market_pricing import MarketComparable, MarketPriceComparisonEngine
from .multi_source import UnifiedMultiSourceEngine
from .opportunity_profit import OpportunityProfitDecisionEngine
from .opportunity_scoring import OpportunityScoringEngine
from .real_cost import RealCostEngine, RealCostInputs
from .today_dashboard import OpportunityDisplayMetadata, build_today_dashboard
from .unified_opportunity import UnifiedOpportunityExtractor


@dataclass(frozen=True)
class DailyPipelineConfig:
    keyword: str | None = None
    limit: int = 25
    output_path: str = "data/todays_opportunities.json"
    finn_rows: int = 30

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("limit must be positive")
        if not self.output_path.strip():
            raise ValueError("output_path must not be empty")
        if not 1 <= self.finn_rows <= 1000:
            raise ValueError("finn_rows must be between 1 and 1000")


@dataclass(frozen=True)
class DailyPipelineResult:
    fetched_count: int
    extracted_count: int
    deduplicated_count: int
    duplicate_count: int
    output_path: str
    generated_at: str
    buy_count: int
    monitor_count: int
    reject_count: int
    source_counts: dict[str, int]
    source_errors: dict[str, str]


class AutomatedDailyPipeline:
    """Run collection, normalization, deduplication, scoring and reporting."""

    def __init__(
        self,
        *,
        client: AuksjonenClient | None = None,
        finn_client: FinnApiClient | None = None,
        konkurskupp_client: KonkurskuppFeedClient | None = None,
        bjaroy_client: BjaroyFeedClient | None = None,
        konkurs_app_client: KonkursAppFeedClient | None = None,
        extractor: UnifiedOpportunityExtractor | None = None,
        multi_source_engine: UnifiedMultiSourceEngine | None = None,
        market_engine: MarketPriceComparisonEngine | None = None,
        cost_engine: RealCostEngine | None = None,
        decision_engine: OpportunityProfitDecisionEngine | None = None,
        scoring_engine: OpportunityScoringEngine | None = None,
        report_engine: DailyOpportunityReportEngine | None = None,
    ) -> None:
        self.client = client or AuksjonenClient()
        self.finn_client = finn_client
        self.konkurskupp_client = konkurskupp_client
        self.bjaroy_client = bjaroy_client
        self.konkurs_app_client = konkurs_app_client
        self.extractor = extractor or UnifiedOpportunityExtractor()
        self.multi_source_engine = multi_source_engine or UnifiedMultiSourceEngine()
        self.market_engine = market_engine or MarketPriceComparisonEngine()
        self.cost_engine = cost_engine or RealCostEngine()
        self.decision_engine = decision_engine or OpportunityProfitDecisionEngine()
        self.scoring_engine = scoring_engine or OpportunityScoringEngine()
        self.report_engine = report_engine or DailyOpportunityReportEngine()

    def _collect(self, config: DailyPipelineConfig) -> tuple[tuple[SourceDocument, ...], dict[str, int], dict[str, str]]:
        documents: list[SourceDocument] = []
        counts: dict[str, int] = {}
        errors: dict[str, str] = {}
        sources = [("Auksjonen.no", lambda: self.client.search(keyword=config.keyword))]
        if self.finn_client is not None:
            sources.append(("FINN.no", lambda: self.finn_client.search(keyword=config.keyword, rows=config.finn_rows)))
        if self.konkurskupp_client is not None:
            sources.append(("Konkurskupp", lambda: self.konkurskupp_client.fetch(keyword=config.keyword)))
        if self.bjaroy_client is not None:
            sources.append(("Bjarøy", lambda: self.bjaroy_client.fetch(keyword=config.keyword)))
        if self.konkurs_app_client is not None:
            sources.append(("Konkurs.app", lambda: self.konkurs_app_client.fetch(keyword=config.keyword)))
        for source_name, fetch in sources:
            try:
                items = tuple(fetch())
            except RuntimeError as exc:
                counts[source_name] = 0
                errors[source_name] = str(exc)
                continue
            counts[source_name] = len(items)
            documents.extend(items)
        return tuple(documents), counts, errors

    def run(
        self,
        config: DailyPipelineConfig | None = None,
        *,
        documents: Iterable[SourceDocument] | None = None,
        comparables_by_id: Mapping[str, Iterable[MarketComparable]] | None = None,
        costs_by_id: Mapping[str, RealCostInputs] | None = None,
        report_date: date | None = None,
    ) -> DailyPipelineResult:
        config = config or DailyPipelineConfig()
        if documents is None:
            source_documents, source_counts, source_errors = self._collect(config)
        else:
            source_documents = tuple(documents)
            source_counts: dict[str, int] = {}
            for item in source_documents:
                source_counts[item.source_name] = source_counts.get(item.source_name, 0) + 1
            source_errors = {}

        extracted = self.extractor.extract(source_documents)
        merge_result = self.multi_source_engine.merge(extracted)
        opportunities = merge_result.opportunities
        comparables_by_id = comparables_by_id or {}
        costs_by_id = costs_by_id or {}

        decisions = []
        scores_by_id = {}
        metadata: dict[str, OpportunityDisplayMetadata] = {}
        for opportunity in opportunities:
            market = self.market_engine.compare(opportunity, comparables_by_id.get(opportunity.opportunity_id, ()))
            cost_inputs = costs_by_id.get(opportunity.opportunity_id)
            if cost_inputs is None:
                cost_inputs = RealCostInputs(
                    purchase_price_nok=opportunity.current_price_nok,
                    vat_status=opportunity.mva_status,
                )
            costs = self.cost_engine.calculate(cost_inputs)
            decision = self.decision_engine.decide(market, costs)
            decisions.append(decision)
            scores_by_id[opportunity.opportunity_id] = self.scoring_engine.score(opportunity, decision)
            metadata[opportunity.opportunity_id] = OpportunityDisplayMetadata(
                title=opportunity.title,
                url=opportunity.url,
                city=opportunity.city,
                ends_at=opportunity.ends_at.isoformat() if opportunity.ends_at else None,
            )

        report = self.report_engine.build(
            decisions,
            scores_by_id=scores_by_id,
            report_date=report_date,
            limit=config.limit,
        )
        dashboard = build_today_dashboard(report, metadata)
        generated_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "schema_version": 6,
            "generated_at": generated_at,
            "source": "Auksjonen public listings + authorized FINN/Konkurskupp/Bjarøy/Konkurs.app feeds when configured",
            "sources": source_counts,
            "source_errors": source_errors,
            "keyword": config.keyword,
            "fetched_count": len(source_documents),
            "extracted_count": len(extracted),
            "deduplicated_count": len(opportunities),
            "duplicate_count": merge_result.duplicate_count,
            "duplicate_groups_merged": merge_result.groups_merged,
            **asdict(dashboard),
        }
        self._write_json_atomic(Path(config.output_path), payload)
        return DailyPipelineResult(
            fetched_count=len(source_documents),
            extracted_count=len(extracted),
            deduplicated_count=len(opportunities),
            duplicate_count=merge_result.duplicate_count,
            output_path=config.output_path,
            generated_at=generated_at,
            buy_count=report.buy_count,
            monitor_count=report.monitor_count,
            reject_count=report.reject_count,
            source_counts=source_counts,
            source_errors=source_errors,
        )

    @staticmethod
    def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
