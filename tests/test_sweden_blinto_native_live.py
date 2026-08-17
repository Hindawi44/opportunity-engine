from __future__ import annotations

from pathlib import Path

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ENDED,
    ITEM_LISTING,
    PageVerification,
)
from opportunity_engine.discovery.sweden_blinto_native_live import (
    BLINTO_NATIVE_QUERY,
    BlintoNativeLiveSearchProvider,
    BlintoNativeLiveVerifier,
    NativeListingFetch,
)
from scripts.run_blinto_native_live_discovery import run_native_live_pipeline


LISTING_HTML = """
<html><body>
  <a href="/auction/Varulager-med-Jackor-Fristads--6-stycken-275599-146253/">
    <img alt="Fristads jackets">
  </a>
  <a href="/auction/Varulager-med-Jackor-Fristads--6-stycken-275599-146253/">
    <span>Varulager med Jackor Fristads - 6 stycken</span>
  </a>
  <a href="https://www.blinto.se/auction/Restlager-arbetsklader-24-stycken-275600-146255/">
    Restlager arbetskläder - 24 stycken
  </a>
  <a href="/auction/Varulager-med-kladskap-20-stycken-275601-146256/">
    Varulager med klädskåp - 20 stycken
  </a>
  <a href="/auction/Varulager-med-svarv-275602-146257/">
    Varulager med svarv
  </a>
  <a href="/auction/l/">Varulager &amp; Överskott</a>
</body></html>
"""


def _listing_fetch(_url: str, _timeout: float) -> NativeListingFetch:
    return NativeListingFetch(
        final_url="https://www.blinto.se/auction/l/",
        html=LISTING_HTML,
    )


def _active_verification(url: str) -> PageVerification:
    occurrence = url.rstrip("/").split("-")[-1]
    return PageVerification(
        url=url,
        title="Varulager med Jackor Fristads - 6 stycken",
        text="Varulager med jackor. Auktionen avslutas. Högsta bud 250 kr.",
        inventory_type="mixed_clothing_inventory",
        quantity=6,
        listing_status=ACTIVE,
        page_role=ITEM_LISTING,
        opportunity_identity=f"blinto-auction:test:{occurrence}",
        identity_stable=True,
        clothing_inventory_evidence=True,
        sale_evidence=True,
        event_scenario="WAREHOUSE_SURPLUS",
        bounded_context="auktionen avslutas | högsta bud 250 kr",
        verified=True,
    )


def test_native_listing_fetches_once_deduplicates_and_filters_locally() -> None:
    provider = BlintoNativeLiveSearchProvider(fetch_listing=_listing_fetch)

    first = tuple(provider.search(BLINTO_NATIVE_QUERY.query, count=20))
    second = tuple(provider.search(BLINTO_NATIVE_QUERY.query, count=20))

    assert [hit.title for hit in first] == [
        "Varulager med Jackor Fristads - 6 stycken",
        "Restlager arbetskläder - 24 stycken",
    ]
    assert second == first
    diagnostics = provider.diagnostics()
    assert diagnostics["listing_requests"] == 1
    assert diagnostics["brave_requests"] == 0
    assert diagnostics["paid_search_used"] is False
    assert diagnostics["raw_exact_auction_links"] == 4
    assert diagnostics["accepted_hits"] == 2
    assert diagnostics["rejected_hits"] == 2


def test_native_verifier_preserves_source_lifecycle_truth_and_counts_status() -> None:
    calls: list[str] = []

    def delegate(url: str) -> PageVerification:
        calls.append(url)
        status = ACTIVE if url.endswith("active") else ENDED
        return PageVerification(url=url, listing_status=status, verified=True)

    verifier = BlintoNativeLiveVerifier(delegate)
    assert verifier("https://blinto.se/auction/example-1000-2000-active").listing_status == ACTIVE
    assert verifier("https://blinto.se/auction/example-1000-2001-ended").listing_status == ENDED

    diagnostics = verifier.diagnostics()
    assert len(calls) == 2
    assert diagnostics["exact_page_verification_attempts"] == 2
    assert diagnostics["active_pages"] == 1
    assert diagnostics["ended_pages"] == 1
    assert diagnostics["brave_requests"] == 0


def test_pipeline_writes_opportunity_engine_artifacts_with_zero_brave(tmp_path: Path) -> None:
    result, paths = run_native_live_pipeline(
        output_dir=tmp_path,
        results_per_query=20,
        verification_limit=20,
        fetch_listing=_listing_fetch,
        page_verifier=_active_verification,
    )

    report = result["search_run_report"]
    assert report["source_mode"] == "BLINTO_NATIVE_LIVE"
    assert report["query_pack"] == "BLINTO_NATIVE_LIVE_DISCOVERY_V1"
    assert report["source_target"] == "blinto.se"
    assert report["brave_requests"] == 0
    assert report["paid_search_used"] is False
    assert report["search_engine_used"] is False
    assert report["source_diagnostics"]["listing_requests"] == 1
    assert report["source_page_verifier_diagnostics"]["active_pages"] == 2
    assert report["confirmed_sales"] >= 1
    assert paths["search_run_report"].exists()
    assert paths["unified_opportunity_report"].exists()
