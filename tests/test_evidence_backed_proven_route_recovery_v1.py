from __future__ import annotations

import sqlite3

from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult
from opportunity_engine.discovery.provider_unique_page_verification import (
    PROVEN_ROUTE_RECOVERY_PROVIDER,
    verify_provider_unique_pages,
)


CURRENT_ROOT = "https://salzmann-restwaren.de/"
PRIOR_EXACT = "https://salzmann-restwaren.de/product/damen-jacken-restposten-a-ware/"


def _benchmark(current_url: str = CURRENT_ROOT, *, extra_urls: list[str] | None = None) -> dict:
    urls = [current_url, *(extra_urls or [])]
    return {
        "status": "SUCCESS",
        "shadow_only": True,
        "project_domain_gate_enforced": True,
        "project_domain": "CLOTHING_INVENTORY",
        "market_results": [
            {
                "market_code": "DE",
                "query": "Deutschland Restposten Bekleidung Großhandel Lager",
                "exa": {
                    "results": [
                        {
                            "title": "Bekleidung Restposten Großhandel",
                            "url": url,
                            "domain": url.split("/", 3)[2],
                        }
                        for url in urls
                    ]
                },
                "brave": {"results": []},
            }
        ],
    }


def _seed_previous_exact_lot(input_root, *, url: str = PRIOR_EXACT) -> None:
    db_dir = input_root / "de-exa-exact-lot"
    db_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_dir / "opportunity_engine.db")
    try:
        connection.execute(
            """
            CREATE TABLE unified_opportunities (
                id INTEGER PRIMARY KEY,
                source_url TEXT NOT NULL,
                title TEXT NOT NULL,
                market_code TEXT NOT NULL,
                domain TEXT NOT NULL,
                source_provider TEXT NOT NULL,
                verified INTEGER NOT NULL,
                identity_stable INTEGER NOT NULL,
                top5_eligible INTEGER NOT NULL,
                last_seen_at TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO unified_opportunities (
                id, source_url, title, market_code, domain, source_provider,
                verified, identity_stable, top5_eligible, last_seen_at
            ) VALUES (1, ?, ?, 'DE', 'CLOTHING_INVENTORY', 'EXA', 1, 1, 1, '2026-08-25T07:31:23Z')
            """,
            (url, "Damen Jacken Restposten Bekleidung"),
        )
        connection.commit()
    finally:
        connection.close()


def _fetcher(*, recovered_has_quantity: bool = True):
    def fetch(url: str) -> PageFetchResult:
        if url == CURRENT_ROOT:
            return PageFetchResult(
                url,
                url,
                True,
                200,
                "Bekleidung Restposten Großhandel",
                "Restposten Bekleidung Lager Großhandel.",
            )
        if url == PRIOR_EXACT:
            quantity = "100 Stk. " if recovered_has_quantity else ""
            return PageFetchResult(
                url,
                url,
                True,
                200,
                "Damen Jacken Restposten Bekleidung",
                f"Restposten Bekleidung Lagerbestand. {quantity}5 EUR. Zu verkaufen.",
            )
        return PageFetchResult(url, url, False, 404, "", "", "HTTP_404")

    return fetch


def test_same_exa_host_can_reverify_prior_exact_url_from_spare_global_capacity(
    tmp_path, monkeypatch
) -> None:
    input_root = tmp_path / "multi-market-inputs"
    _seed_previous_exact_lot(input_root)
    monkeypatch.setenv("INPUT_ROOT", str(input_root))

    report = verify_provider_unique_pages(
        _benchmark(),
        provider="exa",
        page_fetcher=_fetcher(),
        max_page_fetches=1,
    )

    assert report["page_fetches_attempted"] == 1
    assert report["proven_route_recovery_page_fetches_attempted"] == 1
    assert report["total_page_fetches_attempted"] == 2
    assert report["total_page_fetches_attempted"] <= report["total_page_fetch_cap"] == 30
    assert report["provider_exact_lot_candidate_count"] == 0
    assert report["proven_route_recovery_exact_lot_candidate_count"] == 1
    assert report["exact_lot_candidate_count"] == 1

    recovered = [
        row for row in report["verified_pages"] if row.get("provider") == PROVEN_ROUTE_RECOVERY_PROVIDER
    ]
    assert len(recovered) == 1
    assert recovered[0]["url"] == PRIOR_EXACT
    assert recovered[0]["fetch_ok"] is True
    assert recovered[0]["tool_learning_useful"] is False
    assert recovered[0]["proven_route_memory_is_qualification_evidence"] is False
    assert recovered[0]["evidence"]["price_evidence"] is True
    assert recovered[0]["evidence"]["quantity_evidence"] is True


def test_prior_url_is_not_recovered_without_same_host_in_current_exa_results(
    tmp_path, monkeypatch
) -> None:
    input_root = tmp_path / "multi-market-inputs"
    _seed_previous_exact_lot(input_root)
    monkeypatch.setenv("INPUT_ROOT", str(input_root))

    report = verify_provider_unique_pages(
        _benchmark("https://example-wholesale.de/"),
        provider="exa",
        page_fetcher=_fetcher(),
        max_page_fetches=1,
    )

    assert report["proven_route_recovery_candidate_count"] == 0
    assert report["proven_route_recovery_page_fetches_attempted"] == 0
    assert report["exact_lot_candidate_count"] == 0


def test_recovery_memory_never_bypasses_fresh_price_quantity_exact_gate(
    tmp_path, monkeypatch
) -> None:
    input_root = tmp_path / "multi-market-inputs"
    _seed_previous_exact_lot(input_root)
    monkeypatch.setenv("INPUT_ROOT", str(input_root))

    report = verify_provider_unique_pages(
        _benchmark(),
        provider="exa",
        page_fetcher=_fetcher(recovered_has_quantity=False),
        max_page_fetches=1,
    )

    assert report["proven_route_recovery_page_fetches_attempted"] == 1
    assert report["proven_route_recovery_exact_lot_candidate_count"] == 0
    assert report["exact_lot_candidate_count"] == 0


def test_recovery_never_exceeds_existing_global_thirty_page_cap(tmp_path, monkeypatch) -> None:
    input_root = tmp_path / "multi-market-inputs"
    _seed_previous_exact_lot(input_root)
    monkeypatch.setenv("INPUT_ROOT", str(input_root))

    extra_urls = [f"https://example-{index}.de/catalog" for index in range(29)]
    report = verify_provider_unique_pages(
        _benchmark(extra_urls=extra_urls),
        provider="exa",
        page_fetcher=_fetcher(),
        max_page_fetches=30,
    )

    assert report["page_fetches_attempted"] == 30
    assert report["proven_route_recovery_page_fetches_attempted"] == 0
    assert report["total_page_fetches_attempted"] == 30
    assert report["total_page_fetch_cap"] == 30
