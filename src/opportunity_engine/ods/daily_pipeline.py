"""End-to-end daily pipeline for public auction opportunities.

The pipeline is conservative by design: missing market comparables or operating
costs never become zero. Such opportunities remain visible as ``monitor`` until
verified inputs are supplied.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Iterable, Mapping

from .auksjonen import AuksjonenClient
from .daily_opportunity_report import DailyOpportunityReportEngine
from .live_data import SourceDocument
from .market_pricing import MarketComparable, MarketPriceComparisonEngine
from .opportunity_profit import OpportunityProfitDecisionEngine
from .real_cost import RealCostEngine, RealCostInputs
from .today_dashboard import OpportunityDisplayMetadata, build_today_dashboard
from .unified_opportunity import UnifiedOpportunityExtractor


@dataclass(frozen=True)
class DailyPipelineConfig:
    keyword: str | None = None
    limit: int = 25
    output_path: str = "data/todays_opportunities.json"

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("limit must be positive")
        if not self.output_path.strip():
            raise ValueError("output_path must not be empty")


@dataclass(frozen=True)
class DailyPipelineResult:
    fetched_count: int
    extracted_count: int
    output_path: str
    generated_at: str
    buy_count: int
    monitor_count: int
    reject_count: int


class AutomatedDailyPipeline:
    """Run collection, normalization, pricing, costing, decision and reporting."""

    def __init__(
        self,
        *,
        client: AuksjonenClient | None = None,
        extractor: UnifiedOpportunityExtractor | None = None,
        market_engine: MarketPriceComparisonEngine | None = None,
        cost_engine: RealCostEngine | None = None,
        decision_engine: OpportunityProfitDecisionEngine | None = None,
        report_engine: DailyOpportunityReportEngine | None = None,
    ) -> None:
        self.client = client or AuksjonenClient()
        self.extractor = extractor or UnifiedOpportunityExtractor()
        self.market_engine = market_engine or MarketPriceComparisonEngine()
        self.cost_engine = cost_engine or RealCostEngine()
        self.decision_engine = decision_engine or OpportunityProfitDecisionEngine()
        self.report_engine = report_engine or DailyOpportunityReportEngine()

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
        source_documents = tuple(
            documents if documents is not None else self.client.search(keyword=config.keyword)
        )
        opportunities = self.extractor.extract(source_documents)
        comparables_by_id = comparables_by_id or {}
        costs_by_id = costs_by_id or {}

        decisions = []
        metadata: dict[str, OpportunityDisplayMetadata] = {}
        for opportunity in opportunities:
            market = self.market_engine.compare(
                opportunity,
                comparables_by_id.get(opportunity.opportunity_id, ()),
            )
            cost_inputs = costs_by_id.get(opportunity.opportunity_id)
            if cost_inputs is None:
                cost_inputs = RealCostInputs(
                    purchase_price_nok=opportunity.current_price_nok,
                    vat_status=opportunity.mva_status,
                )
            costs = self.cost_engine.calculate(cost_inputs)
            decisions.append(self.decision_engine.decide(market, costs))
            metadata[opportunity.opportunity_id] = OpportunityDisplayMetadata(
                title=opportunity.title,
                url=opportunity.url,
                city=opportunity.city,
                ends_at=opportunity.ends_at.isoformat() if opportunity.ends_at else None,
            )

        report = self.report_engine.build(
            decisions,
            report_date=report_date,
            limit=config.limit,
        )
        dashboard = build_today_dashboard(report, metadata)
        generated_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "schema_version": 1,
            "generated_at": generated_at,
            "source": "Auksjonen.no public listings",
            "keyword": config.keyword,
            "fetched_count": len(source_documents),
            "extracted_count": len(opportunities),
            **asdict(dashboard),
        }
        self._write_json_atomic(Path(config.output_path), payload)
        return DailyPipelineResult(
            fetched_count=len(source_documents),
            extracted_count=len(opportunities),
            output_path=config.output_path,
            generated_at=generated_at,
            buy_count=report.buy_count,
            monitor_count=report.monitor_count,
            reject_count=report.reject_count,
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
