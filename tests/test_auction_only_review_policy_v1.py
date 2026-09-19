"""Operator pivot: actual auction source evidence, not advertisements or generic URL shapes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from opportunity_engine.auction_only_review_policy import (
    auction_route, restrict_to_auction_sources, require_dated_open_auction,
    readable_auction_review,
)
from opportunity_engine.balanced_link_review import build_balanced_review
from opportunity_engine.human_listing_review_queue import build_queue
from opportunity_engine.source_status_reconciliation import reconcile_auksjonen_snapshot

AUK = "https://www.auksjonen.no/auksjon/overskuddsvarer/stort-parti-arbeidsklaer/574797"
FINN = "https://www.finn.no/450273961"
WHOLESALE = "https://salzmann-restwaren.de/product/bekleidung-fuer-herren-pullover/"
PS_PARENT = "https://psauction.se/auction/69239/avyttring-av-arbets-och-skyddsklader"


def row(url, *, market="NO"):
    return {"opportunity_identity": url, "source_urls": [url], "canonical_url": None,
            "title": "Butikslager arbeidsklær parti", "market_code": market,
            "listing_status": "ACTIVE", "source_names": ["test"],
            "workflow_status": "REQUIRES_VERIFICATION"}


def report(now):
    return {"generated_at": (now + timedelta(minutes=1)).isoformat(),
            "commercially_qualified_count": 2,
            "deduplicated_opportunities": [row(AUK), row(FINN), row(WHOLESALE, market="DE"),
                                           row(PS_PARENT, market="SE")]}


def snapshot(now):
    return {"schema_version": "auksjonen-live-clothing-test-v1",
            "captured_at": now.isoformat(), "listings": [{
                "source": "Auksjonen Public API", "url": AUK, "status": "INPROGRESS",
                "listing_status": "ACTIVE", "ends_at": (now + timedelta(days=2)).isoformat(),
            }]}


def test_only_exact_known_platform_auction_routes_not_any_ad_or_parents():
    assert auction_route(AUK) == "AUKSJONEN_LOT"
    assert auction_route("https://ny.auksjonen.no/auksjon/torget/arbeidsklaer/631276") == "AUKSJONEN_LOT"
    assert auction_route("https://www.klaravik.se/auktion/produkt/klader-och-skor-stort-parti/") == "KLARAVIK_LOT"
    assert auction_route("https://www.blinto.se/auction/Parti-212451-124376/") == "BLINTO_LOT"
    assert auction_route("https://psauction.se/item/view/12345/arbeidsklaer/") == "PSAUCTION_LOT"
    assert auction_route(PS_PARENT) == "PSAUCTION_PARENT_NAVIGATION_ONLY"
    assert auction_route("https://riegermann.de/de/l/12345/kleider-posten") == "RIEGERMANN_LOT"
    for url in (FINN, WHOLESALE, "https://cubecompany.nl/product/parti-100/",
                "https://evil-auksjonen.no/auksjon/torget/lot/12345",
                "https://auksjonen.no.evil.com/auksjon/torget/lot/12345",
                "https://www.auksjonen.no/auksjon/overskuddsvarer/",
                "https://psauction.se/auction/ended/1111/old-auction",
                "https://www.auksjonen.no/auksjon/torget/lot/12345?utm_source=ad"):
        assert auction_route(url) is None


def test_advertisements_absent_from_all_human_sections_and_original_records_retained():
    now = datetime.now(timezone.utc)
    original = report(now)
    queue = restrict_to_auction_sources(build_queue(original))
    assert len(original["deduplicated_opportunities"]) == 4
    assert queue["counts"]["discovered_records"] == 4
    assert queue["counts"]["advertisements_and_nonauction_pages_hidden_from_review"] == 2
    assert queue["counts"]["commercially_qualified"] == 0
    assert [r["source_url"] for r in queue["review_queue"]] == [AUK]
    assert any(r.get("auction_platform_route") == "PSAUCTION_PARENT_NAVIGATION_ONLY"
               for r in queue["held_separately"])
    queue = reconcile_auksjonen_snapshot(queue, snapshot(now))
    queue = require_dated_open_auction(queue, now=now + timedelta(seconds=10))
    assert queue["counts"]["auction_native_open_evidence"] == 1
    assert queue["daily_batch"][0]["auction_status"] == "SOURCE_REPORTED_OPEN_AT_CAPTURE_NOT_COMMERCIAL_PROOF"
    assert queue["daily_batch"][0]["opportunity_confirmed"] is False
    balanced = build_balanced_review(original, queue)
    rendered = readable_auction_review(queue)
    assert "مزادات فقط" in rendered and AUK in rendered
    assert not balanced["recovered_unverified_item_leads"]
    for serialized in (str(queue["daily_batch"]), str(queue["review_queue"]),
                       str(queue["held_separately"]), rendered, str(balanced)):
        assert FINN not in serialized and WHOLESALE not in serialized
    assert original["deduplicated_opportunities"][1]["source_urls"] == [FINN]


def test_unverified_missing_or_stale_status_fails_closed_without_operator_delete():
    now = datetime.now(timezone.utc)
    queue = restrict_to_auction_sources(build_queue(report(now)))
    without_snapshot = require_dated_open_auction(queue, now=now)
    assert without_snapshot["review_queue"] == []
    assert without_snapshot["counts"]["auction_unverified_held"] == 1
    assert any(item["reason"] == "AUCTION_LIVE_STATUS_NOT_VERIFIED_NOT_OPERATOR_DELETE"
               for item in without_snapshot["held_separately"])
    assert "operator_deleted" not in without_snapshot["counts"]
    queue = restrict_to_auction_sources(build_queue(report(now)))
    reconcile_auksjonen_snapshot(queue, snapshot(now))
    require_dated_open_auction(queue, now=now + timedelta(days=3))
    assert queue["review_queue"] == []
    assert queue["counts"]["auction_unverified_held"] == 1


def test_lookalike_domains_and_only_parent_urls_cannot_become_opportunities():
    now = datetime.now(timezone.utc)
    urls = ["https://www.auksjonen.no.evil.com/auksjon/torget/lot/574797", PS_PARENT,
            "https://psauction.se/auction/ended/1111/old-auction"]
    original = {"deduplicated_opportunities": [row(url) for url in urls]}
    queue = restrict_to_auction_sources(build_queue(original))
    assert not queue["review_queue"] and not queue["daily_batch"]
    assert all(item["auction_platform_route"] == "PSAUCTION_PARENT_NAVIGATION_ONLY"
               for item in queue["held_separately"])
    assert original["deduplicated_opportunities"]  # Raw history remains untouched.
