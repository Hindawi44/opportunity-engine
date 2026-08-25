from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from opportunity_engine.discovery import checkpoint_state_restore
from opportunity_engine.discovery import expansion_route_continuity_v1 as continuity
from opportunity_engine.discovery import unified_search_runtime_cli_hook as runtime


ROOT = Path(__file__).resolve().parents[1]


def _write_minimal_route_db(path: Path, *, market: str, url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE unified_opportunities (
                id INTEGER PRIMARY KEY,
                source_url TEXT NOT NULL,
                title TEXT,
                market_code TEXT NOT NULL,
                domain TEXT NOT NULL,
                source_provider TEXT NOT NULL,
                verified INTEGER NOT NULL,
                identity_stable INTEGER NOT NULL,
                top5_eligible INTEGER NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO unified_opportunities (
                source_url, title, market_code, domain, source_provider,
                verified, identity_stable, top5_eligible, last_seen_at
            ) VALUES (?, ?, ?, 'CLOTHING_INVENTORY', 'EXA', 1, 1, 1, ?)
            """,
            (url, "Verified historical lot", market, "2026-08-25T19:44:40+00:00"),
        )
        connection.commit()
    finally:
        connection.close()


def test_expansion_sqlite_paths_are_restorable() -> None:
    for relative in continuity.EXPANSION_DATABASE_RELATIVE_PATHS:
        assert relative in checkpoint_state_restore.DATABASE_RELATIVE_PATHS


def test_hostless_sqlite_continuity_is_expansion_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INPUT_ROOT", str(tmp_path))
    it_url = "https://stockitaly24.com/products/verified-stock-55-pezzi"
    _write_minimal_route_db(
        tmp_path / "it-exa-exact-lot" / "opportunity_engine.db",
        market="IT",
        url=it_url,
    )

    rows = continuity._load_expansion_route_recovery_candidates(
        market="IT",
        current_hosts={"different-provider.example"},
        current_urls=set(),
        query="Italia abbigliamento moda lotto stock in vendita prezzo pezzi magazzino disponibile",
        limit=12,
    )
    assert [row["url"] for row in rows] == [it_url]
    assert rows[0]["route_memory_origin"] == "EXPANSION_SQLITE_HOSTLESS_CONTINUITY_V1"
    assert rows[0]["route_memory_is_qualification_evidence"] == "false"
    assert rows[0]["fresh_page_verification_required"] == "true"

    de_url = "https://example.test/product/bekleidung-50-stuck"
    _write_minimal_route_db(
        tmp_path / "de-exa-exact-lot" / "opportunity_engine.db",
        market="DE",
        url=de_url,
    )
    de_rows = continuity._load_expansion_route_recovery_candidates(
        market="DE",
        current_hosts={"different-provider.example"},
        current_urls=set(),
        query="Deutschland Restposten Bekleidung Großhandel Lager",
        limit=12,
    )
    assert de_rows == []


def test_transitional_bootstrap_is_used_only_without_restored_db(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INPUT_ROOT", str(tmp_path / "inputs"))
    bootstrap = tmp_path / "bootstrap.json"
    url = "https://stockitaly24.com/products/verified-bootstrap-80-pezzi"
    bootstrap.write_text(
        json.dumps(
            {
                "schema_version": continuity.BOOTSTRAP_SCHEMA_VERSION,
                "market_code": "IT",
                "project_domain": "CLOTHING_INVENTORY",
                "provider": "exa",
                "source_run_id": "32890740443",
                "strict_exact_lot_urls": [url],
                "route_memory_is_qualification_evidence": False,
                "fresh_page_verification_required": True,
                "search_request_count": 0,
                "production_mutation": False,
                "automatic_query_activation": False,
                "automatic_provider_activation": False,
                "automatic_source_promotion": False,
                "automatic_contact": False,
                "automatic_bid": False,
                "automatic_reservation": False,
                "automatic_purchase": False,
                "automatic_payment": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(continuity, "PROVEN_ROUTE_BOOTSTRAP_PATH", bootstrap)

    rows = continuity._load_expansion_route_recovery_candidates(
        market="IT",
        current_hosts={"different-provider.example"},
        current_urls=set(),
        query="Italia abbigliamento moda lotto stock in vendita prezzo pezzi magazzino disponibile",
        limit=12,
    )
    assert [row["url"] for row in rows] == [url]
    assert rows[0]["route_memory_origin"] == "HISTORICAL_STRICT_ROUTE_BOOTSTRAP_V1"
    assert rows[0]["historical_source_run_id"] == "32890740443"

    _write_minimal_route_db(
        tmp_path / "inputs" / "it-exa-exact-lot" / "opportunity_engine.db",
        market="IT",
        url="https://other.example/products/current-memory-10-pezzi",
    )
    rows_with_db = continuity._load_transitional_bootstrap_candidates(
        market="IT",
        current_urls=set(),
        query="Italia abbigliamento moda lotto stock in vendita prezzo pezzi magazzino disponibile",
        limit=12,
    )
    assert rows_with_db == []


def test_expansion_callback_persists_fr_it_nl_without_searching_again(tmp_path: Path, monkeypatch) -> None:
    input_root = tmp_path / "inputs"
    output_dir = tmp_path / "output"
    monkeypatch.setenv("INPUT_ROOT", str(input_root))
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    calls: list[tuple[str, str]] = []

    def fake_original() -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "unified-six-market-exa-runtime.json").write_text(
            json.dumps({"status": "SUCCESS", "markets": {}}),
            encoding="utf-8",
        )
        for market in runtime.EXPANSION_EXA_MARKETS:
            source_dir = input_root / f"{market.casefold()}-exa-exact-lot"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "unified-opportunity-report.json").write_text("{}", encoding="utf-8")

    def fake_persist(report_path, source_dir, *, database_url, config_path):
        calls.append((Path(report_path).parent.name, database_url))
        summary_path = Path(source_dir) / "unified-persistence-summary.json"
        summary_path.write_text("{}", encoding="utf-8")
        return {"persisted_record_count": 1}, summary_path

    monkeypatch.setattr(continuity, "_ORIGINAL_RUN_EXPANSION_CLOTHING_EXA", fake_original)
    monkeypatch.setattr(continuity, "persist_unified_report_with_artifacts", fake_persist)

    continuity._run_expansion_clothing_exa_with_continuity()

    assert [name for name, _ in calls] == [
        "fr-exa-exact-lot",
        "it-exa-exact-lot",
        "nl-exa-exact-lot",
    ]
    assert all(url.endswith("/opportunity_engine.db") for _, url in calls)
    status = json.loads((output_dir / "unified-six-market-exa-runtime.json").read_text())
    assert status["search_requests_added_by_route_continuity"] == 0
    assert status["route_memory_is_qualification_evidence"] is False
    assert status["fresh_page_verification_required"] is True


def test_checked_in_bootstrap_is_exactly_the_audited_run340_it_set() -> None:
    payload = json.loads(
        (ROOT / "config/learning/proven-route-bootstrap-v1.json").read_text(encoding="utf-8")
    )
    urls = payload["strict_exact_lot_urls"]
    assert payload["source_run_id"] == "32890740443"
    assert payload["source_artifact_id"] == 9579899746
    assert payload["market_code"] == "IT"
    assert payload["verified_strict_exact_lot_count"] == 12
    assert len(urls) == 12
    assert len(set(urls)) == 12
    assert all(url.startswith("https://stockitaly24.com/products/") for url in urls)
    assert payload["search_request_count"] == 0
    assert payload["route_memory_is_qualification_evidence"] is False
    assert payload["fresh_page_verification_required"] is True
    assert continuity.SEARCH_REQUESTS_ADDED == 0
