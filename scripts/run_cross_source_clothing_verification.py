#!/usr/bin/env python3
"""Run the bounded multi-source clothing inventory verification pipeline.

The default operator run combines:

* Konkurs.app bankruptcy leads cross-verified against Auksjonen inventory lots.
* Direct active clothing inventory lots from Vareauksjonen.
* Current active clothing inventory auctions from Auksjoner.no.

Only commercially verified active inventory lots enter the unified Top 5.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from opportunity_engine.discovery.auksjoner_no_public_adapter import (
    MAX_AUCTIONS,
    AuksjonerNoCollection,
    AuksjonerNoLiveClothingAuction,
    AuksjonerNoPublicCollector,
    write_auksjoner_no_artifacts,
)
from opportunity_engine.discovery.cross_source_clothing_sale_verifier import (
    CrossSourceClothingSaleVerifier,
    CrossSourceVerificationRecord,
    CrossSourceVerificationResult,
    write_cross_source_artifacts,
)
from opportunity_engine.discovery.vareauksjonen_public_adapter import (
    MAX_CANDIDATE_DETAILS,
    VareauksjonenCollection,
    VareauksjonenLiveClothingListing,
    VareauksjonenPublicCollector,
    write_vareauksjonen_artifacts,
)


def _cross_source_opportunity(record: CrossSourceVerificationRecord) -> dict[str, Any]:
    listing = record.listing
    price = listing.buy_now_price_nok
    if price is None:
        price = listing.current_bid_nok
    if price is None:
        price = listing.start_price_nok
    return {
        "title": listing.title,
        "url": listing.url,
        "listing_status": listing.listing_status,
        "price_nok": price,
        "quantity": None,
        "location": listing.city,
        "inventory_lot_signal": listing.inventory_lot_signal,
        "verification_state": record.verification_state,
        "source_channel": "KONKURS_APP_AUKSJONEN_EXACT_ORGNR",
        "source": listing.source,
        "top5_eligible": record.inventory_sale_verified,
        "analysis_eligible": record.inventory_sale_verified,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase_decision": False,
        "automatic_payment": False,
    }


def _vareauksjonen_opportunity(
    listing: VareauksjonenLiveClothingListing,
) -> dict[str, Any]:
    return {
        "title": listing.title,
        "url": listing.url,
        "listing_status": listing.listing_status,
        "price_nok": listing.price_nok,
        "quantity": listing.quantity,
        "location": listing.location,
        "inventory_lot_signal": listing.inventory_lot_signal,
        "verification_state": "VERIFIED_ACTIVE_DIRECT_INVENTORY_SALE",
        "source_channel": "VAREAUKSJONEN_DIRECT_ACTIVE_LOT",
        "source": listing.source,
        "top5_eligible": True,
        "analysis_eligible": True,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase_decision": False,
        "automatic_payment": False,
    }


def _auksjoner_no_opportunity(
    auction: AuksjonerNoLiveClothingAuction,
) -> dict[str, Any]:
    return {
        "title": auction.title,
        "url": auction.url,
        "listing_status": auction.listing_status,
        "price_nok": None,
        "quantity": None,
        "location": None,
        "inventory_lot_signal": auction.inventory_lot_signal,
        "verification_state": "VERIFIED_ACTIVE_CURRENT_INVENTORY_AUCTION",
        "source_channel": "AUKSJONER_NO_CURRENT_ACTIVE_LOT",
        "source": auction.source,
        "starts_at": auction.starts_at,
        "ends_at": auction.ends_at,
        "buyers_premium_percent": auction.buyers_premium_percent,
        "top5_eligible": True,
        "analysis_eligible": True,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase_decision": False,
        "automatic_payment": False,
    }


def build_combined_top5(
    cross_source: CrossSourceVerificationResult,
    vareauksjonen: VareauksjonenCollection,
    auksjoner_no: AuksjonerNoCollection,
) -> list[dict[str, Any]]:
    """Combine only verified opportunities, preserving evidence strength order."""
    candidates = [
        *(_cross_source_opportunity(record) for record in cross_source.verified_sales),
        *(
            _vareauksjonen_opportunity(listing)
            for listing in vareauksjonen.inventory_opportunities
        ),
        *(
            _auksjoner_no_opportunity(auction)
            for auction in auksjoner_no.inventory_opportunities
        ),
    ]
    unique: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for candidate in candidates:
        url = str(candidate.get("url") or "")
        if not url or url in seen_urls:
            continue
        if not candidate.get("top5_eligible"):
            continue
        seen_urls.add(url)
        unique.append(candidate)
        if len(unique) >= 5:
            break
    return unique


def write_combined_outputs(
    *,
    cross_source: CrossSourceVerificationResult,
    vareauksjonen: VareauksjonenCollection,
    auksjoner_no: AuksjonerNoCollection,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    top5 = build_combined_top5(cross_source, vareauksjonen, auksjoner_no)
    scan_complete = (
        cross_source.scan_complete
        and vareauksjonen.scan_complete
        and auksjoner_no.scan_complete
    )
    error_count = (
        len(cross_source.errors)
        + len(vareauksjonen.errors)
        + len(auksjoner_no.errors)
    )
    report = {
        "schema_version": "multi-source-live-clothing-verification-1.1",
        "scan_complete": scan_complete,
        "commercial_top5_count": len(top5),
        "sources": {
            "konkurs_app_auksjonen": {
                "bankruptcy_records_received": cross_source.bankruptcy_items_received,
                "bankruptcy_leads": len(cross_source.bankruptcy_leads),
                "auksjonen_categories_scanned": len(cross_source.auksjonen_result.scans),
                "verified_inventory_sales": len(cross_source.verified_sales),
                "review_leads": len(cross_source.review_leads),
                "scan_complete": cross_source.scan_complete,
                "errors": len(cross_source.errors),
            },
            "vareauksjonen": {
                "public_pages_read": len(vareauksjonen.page_diagnostics),
                "candidate_details_read": len(vareauksjonen.listings),
                "verified_inventory_sales": len(
                    vareauksjonen.inventory_opportunities
                ),
                "individual_clothing_items": len(
                    vareauksjonen.individual_clothing_items
                ),
                "scan_complete": vareauksjonen.scan_complete,
                "errors": len(vareauksjonen.errors),
            },
            "auksjoner_no": {
                "current_auctions_received": auksjoner_no.items_received,
                "verified_inventory_auctions": len(
                    auksjoner_no.inventory_opportunities
                ),
                "clothing_non_lots": len(auksjoner_no.clothing_non_lots),
                "past_page_queried": False,
                "scan_complete": auksjoner_no.scan_complete,
                "errors": len(auksjoner_no.errors),
            },
        },
        "live_clothing_top5": top5,
        "errors": error_count,
        "paid_search_used": False,
        "openai_api_used": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase_decision": False,
        "automatic_payment": False,
    }
    report_path = output_dir / "multi-source-live-report.json"
    top5_path = output_dir / "live-clothing-top5.json"
    summary_path = output_dir / "operator-summary.txt"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    top5_path.write_text(
        json.dumps(top5, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "Multi-source live clothing inventory verification",
        "",
        "Konkurs.app + Auksjonen:",
        f"- Bankruptcy records received: {cross_source.bankruptcy_items_received}",
        f"- Bankruptcy leads retained: {len(cross_source.bankruptcy_leads)}",
        f"- Auksjonen categories scanned: {len(cross_source.auksjonen_result.scans)}",
        f"- Exact-orgnr verified inventory sales: {len(cross_source.verified_sales)}",
        f"- Identity review leads: {len(cross_source.review_leads)}",
        "",
        "Vareauksjonen:",
        f"- Public pages read: {len(vareauksjonen.page_diagnostics)}",
        f"- Crawl delay respected: {vareauksjonen.crawl_delay_seconds:g} seconds",
        f"- Candidate details read: {len(vareauksjonen.listings)}",
        f"- Verified direct inventory sales: {len(vareauksjonen.inventory_opportunities)}",
        f"- Individual clothing items excluded: {len(vareauksjonen.individual_clothing_items)}",
        "",
        "Auksjoner.no:",
        f"- Current auctions received: {auksjoner_no.items_received}",
        f"- Crawl delay respected: {auksjoner_no.crawl_delay_seconds:g} seconds",
        f"- Verified current inventory auctions: {len(auksjoner_no.inventory_opportunities)}",
        f"- Clothing auctions without lot evidence excluded: {len(auksjoner_no.clothing_non_lots)}",
        "- Past auction page queried: false",
        "",
        f"Unified commercial Top 5 count: {len(top5)}",
        f"Scan complete: {scan_complete}",
        f"Errors: {error_count}",
        "Paid Brave/OpenAI calls: 0",
        "Automatic contact/bid/purchase/payment: false",
    ]
    if top5:
        lines.extend(("", "Verified opportunities:"))
        for item in top5:
            lines.append(
                f"- {item['title']} | {item.get('location') or 'unknown'} | "
                f"{item['url']}"
            )
    else:
        lines.extend(("", "No verified active clothing inventory opportunity was found."))
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"report": report_path, "commercial_top5": top5_path, "summary": summary_path}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/cross-source-clothing-verification"),
    )
    parser.add_argument("--lookback-days", type=int, default=365)
    parser.add_argument("--max-bankruptcy-leads", type=int, default=100)
    parser.add_argument("--max-detail-pages", type=int, default=5)
    parser.add_argument(
        "--max-vareauksjonen-details",
        type=int,
        default=MAX_CANDIDATE_DETAILS,
    )
    parser.add_argument(
        "--max-auksjoner-no-auctions",
        type=int,
        default=MAX_AUCTIONS,
    )
    args = parser.parse_args()

    cross_source = CrossSourceClothingSaleVerifier(
        lookback_days=args.lookback_days,
        max_bankruptcy_leads=args.max_bankruptcy_leads,
        max_detail_pages=args.max_detail_pages,
    ).collect()
    vareauksjonen = VareauksjonenPublicCollector(
        max_candidate_details=args.max_vareauksjonen_details,
    ).collect()
    auksjoner_no = AuksjonerNoPublicCollector(
        max_auctions=args.max_auksjoner_no_auctions,
    ).collect()

    cross_paths = write_cross_source_artifacts(
        cross_source,
        args.output_dir / "konkurs-auksjonen",
    )
    vare_paths = write_vareauksjonen_artifacts(
        vareauksjonen,
        args.output_dir / "vareauksjonen",
    )
    auksjoner_no_paths = write_auksjoner_no_artifacts(
        auksjoner_no,
        args.output_dir / "auksjoner-no",
    )
    combined_paths = write_combined_outputs(
        cross_source=cross_source,
        vareauksjonen=vareauksjonen,
        auksjoner_no=auksjoner_no,
        output_dir=args.output_dir,
    )

    print(f"Konkurs.app API requests: {cross_source.bankruptcy_requests}")
    print(f"Bankruptcy records received: {cross_source.bankruptcy_items_received}")
    print(f"Bankruptcy leads retained: {len(cross_source.bankruptcy_leads)}")
    print(f"Auksjonen categories scanned: {len(cross_source.auksjonen_result.scans)}")
    print(f"Auksjonen verified inventory sales: {len(cross_source.verified_sales)}")
    print(f"Vareauksjonen public pages read: {len(vareauksjonen.page_diagnostics)}")
    print(f"Vareauksjonen candidates read: {len(vareauksjonen.listings)}")
    print(
        "Vareauksjonen verified inventory sales: "
        f"{len(vareauksjonen.inventory_opportunities)}"
    )
    print(f"Auksjoner.no current auctions received: {auksjoner_no.items_received}")
    print(
        "Auksjoner.no verified inventory auctions: "
        f"{len(auksjoner_no.inventory_opportunities)}"
    )
    combined = build_combined_top5(cross_source, vareauksjonen, auksjoner_no)
    print(f"Unified commercial Top 5 count: {len(combined)}")
    scan_complete = (
        cross_source.scan_complete
        and vareauksjonen.scan_complete
        and auksjoner_no.scan_complete
    )
    print(f"Scan complete: {scan_complete}")
    print(
        "Errors: "
        f"{len(cross_source.errors) + len(vareauksjonen.errors) + len(auksjoner_no.errors)}"
    )
    print("Paid Brave/OpenAI calls: 0")
    for prefix, paths in (
        ("konkurs_auksjonen", cross_paths),
        ("vareauksjonen", vare_paths),
        ("auksjoner_no", auksjoner_no_paths),
        ("combined", combined_paths),
    ):
        for label, path in paths.items():
            print(f"{prefix}_{label}: {path}")

    return 0 if scan_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
