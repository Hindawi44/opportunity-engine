#!/usr/bin/env python3
"""Run the automated daily opportunity pipeline and smart alert processor."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urljoin

from opportunity_engine.ods.auksjonen import AuksjonenClient, parse_auksjonen_listing_page
from opportunity_engine.ods.bjaroy import BjaroyFeedClient
from opportunity_engine.ods.daily_pipeline import AutomatedDailyPipeline, DailyPipelineConfig
from opportunity_engine.ods.finn import FinnApiClient
from opportunity_engine.ods.konkurs_app import KonkursAppFeedClient
from opportunity_engine.ods.konkurskupp import KonkurskuppFeedClient
from opportunity_engine.ods.market_pricing import MarketComparable
from opportunity_engine.ods.real_cost import RealCostInputs
from opportunity_engine.ods.snapshot_alerts import SnapshotAlertProcessor


# Discovery Engine v2: read the public category pages directly. The former ?q=
# searches could return the vehicle-heavy general catalogue even when a target
# keyword was supplied, so they are no longer used for the default discovery run.
DEFAULT_AUKSJONEN_DISCOVERY_PATHS = (
    "/auksjoner/torget/vareparti-og-konkursbo",
    "/auksjoner/overskuddsvarer/vareparti-og-konkursbo",
    "/auksjoner/interior_kontor-innredning",
    "/auksjoner/varelager",
)


class TargetedAuksjonenClient(AuksjonenClient):
    """Collect directly from business-opportunity category pages.

    An explicit keyword still uses AuksjonenClient.search for manual diagnostics.
    The normal daily run never falls back to the general /auksjoner/ page.
    """

    def search(self, *, keyword: str | None = None):
        if keyword and keyword.strip():
            return super().search(keyword=keyword)

        documents = []
        seen: set[str] = set()
        for path in DEFAULT_AUKSJONEN_DISCOVERY_PATHS:
            url = urljoin(f"{self.base_url}/", path.lstrip("/"))
            html = self.transport(url, self.timeout, self.headers)
            for document in parse_auksjonen_listing_page(html, base_url=self.base_url):
                if document.document_id in seen:
                    continue
                seen.add(document.document_id)
                documents.append(document)
        return tuple(documents)


def _load_verified_inputs(path: str | None):
    if not path:
        return {}, {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    comparables = {
        opportunity_id: tuple(MarketComparable(**item) for item in items)
        for opportunity_id, items in payload.get("comparables_by_id", {}).items()
    }
    costs = {
        opportunity_id: RealCostInputs(**item)
        for opportunity_id, item in payload.get("costs_by_id", {}).items()
    }
    return comparables, costs


def _finn_client_from_environment() -> FinnApiClient | None:
    api_key = os.getenv("FINN_API_KEY", "").strip()
    org_id = os.getenv("FINN_ORG_ID", "").strip()
    if not api_key and not org_id:
        return None
    if not api_key or not org_id:
        raise RuntimeError("FINN_API_KEY and FINN_ORG_ID must be configured together")
    return FinnApiClient(
        api_key=api_key,
        org_id=org_id,
        market=os.getenv("FINN_MARKET", "bap/forsale").strip() or "bap/forsale",
    )


def _konkurskupp_client_from_environment() -> KonkurskuppFeedClient | None:
    feed_url = os.getenv("KONKURSKUPP_FEED_URL", "").strip()
    token = os.getenv("KONKURSKUPP_FEED_TOKEN", "").strip() or None
    return KonkurskuppFeedClient(feed_url=feed_url, token=token) if feed_url else None


def _bjaroy_client_from_environment() -> BjaroyFeedClient | None:
    feed_url = os.getenv("BJAROY_FEED_URL", "").strip()
    token = os.getenv("BJAROY_FEED_TOKEN", "").strip() or None
    return BjaroyFeedClient(feed_url=feed_url, token=token) if feed_url else None


def _konkurs_app_client_from_environment() -> KonkursAppFeedClient | None:
    feed_url = os.getenv("KONKURS_APP_FEED_URL", "").strip()
    token = os.getenv("KONKURS_APP_FEED_TOKEN", "").strip() or None
    return KonkursAppFeedClient(feed_url=feed_url, token=token) if feed_url else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate today's opportunity dashboard snapshot")
    parser.add_argument("--keyword", default=None, help="Optional source search keyword")
    parser.add_argument("--limit", type=int, default=25, help="Maximum rows in the report")
    parser.add_argument("--finn-rows", type=int, default=30, help="Maximum authorized FINN rows")
    parser.add_argument("--output", default="data/todays_opportunities.json")
    parser.add_argument("--alerts-output", default="data/smart_alerts.json")
    parser.add_argument(
        "--verified-inputs",
        default=None,
        help="Optional JSON file containing verified comparables and explicit costs",
    )
    args = parser.parse_args()

    comparables, costs = _load_verified_inputs(args.verified_inputs)
    result = AutomatedDailyPipeline(
        client=TargetedAuksjonenClient(),
        finn_client=_finn_client_from_environment(),
        konkurskupp_client=_konkurskupp_client_from_environment(),
        bjaroy_client=_bjaroy_client_from_environment(),
        konkurs_app_client=_konkurs_app_client_from_environment(),
    ).run(
        DailyPipelineConfig(
            keyword=args.keyword,
            limit=args.limit,
            output_path=args.output,
            finn_rows=args.finn_rows,
        ),
        comparables_by_id=comparables,
        costs_by_id=costs,
    )
    alerts = SnapshotAlertProcessor().process(args.output, args.alerts_output)
    response = {**result.__dict__, "alert_count": len(alerts), "alerts_path": args.alerts_output}
    print(json.dumps(response, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
