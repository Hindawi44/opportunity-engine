from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from opportunity_engine.discovery.commercial_anchor_query_expansion import (
    MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET,
    SWEDEN_OFFICIAL_ANCHOR_ORIGIN,
    build_commercial_anchor_queries,
    load_sweden_official_company_anchors,
)
from opportunity_engine.project_domain_boundary import CLOTHING_INVENTORY, classify_project_domain
from opportunity_engine.search_experiment_execution_bridge_v1 import _market_anchored


def _create_market_signal_db(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE market_signals (
                signal_id TEXT PRIMARY KEY,
                signal_type TEXT,
                source_provider TEXT,
                source_country TEXT,
                company_name TEXT,
                status TEXT,
                confidence REAL,
                payload_json TEXT,
                last_seen_at TEXT
            )
            """
        )
        for index, row in enumerate(rows, start=1):
            connection.execute(
                """
                INSERT INTO market_signals (
                    signal_id, signal_type, source_provider, source_country,
                    company_name, status, confidence, payload_json, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"signal-{index}",
                    row.get("signal_type", "INSOLVENCY_OR_LIQUIDATION"),
                    row.get("source_provider", "Bolagsverket Värdefulla datamängder"),
                    row.get("source_country", "SE"),
                    row.get("company_name"),
                    row.get("status", "WATCH"),
                    row.get("confidence", 1.0),
                    json.dumps(row.get("payload") or {}, ensure_ascii=False),
                    row.get("last_seen_at", f"2026-08-{20 + index:02d}T10:00:00+00:00"),
                ),
            )
        connection.commit()
    finally:
        connection.close()


def _official_payload(company_name: str, *, official_bulk_anchor: bool = False) -> dict:
    metadata = {
        "official_register": True,
        "signal_only": True,
        "organisation_number": "5560000000",
        "legal_status_code": "KK",
    }
    if official_bulk_anchor:
        metadata["official_bulk_anchor_v1"] = True
    return {
        "signal_type": "INSOLVENCY_OR_LIQUIDATION",
        "source_country": "SE",
        "company_name": company_name,
        "status": "WATCH",
        "metadata": metadata,
        "evidence": [
            {
                "evidence_type": "OFFICIAL_SWEDISH_COMPANY_STATUS",
                "verified": True,
                "source_url": "https://gw.api.bolagsverket.se/vardefulla-datamangder/v1/organisationer",
            }
        ],
    }


def test_loader_accepts_only_verified_bolagsverket_liquidation_signals(tmp_path: Path) -> None:
    database = tmp_path / "opportunity_engine.db"
    _create_market_signal_db(
        database,
        [
            {
                "company_name": "Nordic Mode AB",
                "payload": _official_payload("Nordic Mode AB"),
                "last_seen_at": "2026-08-25T10:00:00+00:00",
            },
            {
                "company_name": "Unverified Fashion AB",
                "payload": {"metadata": {"official_register": True, "signal_only": True}},
            },
            {
                "company_name": "Wrong Provider AB",
                "source_provider": "Brave Search",
                "payload": _official_payload("Wrong Provider AB"),
            },
        ],
    )

    anchors = load_sweden_official_company_anchors(database_path=database)

    assert anchors == (("OFFICIAL_COMPANY", "Nordic Mode AB"),)


def test_loader_prioritizes_bulk_clothing_anchor_over_newer_legacy_signal(tmp_path: Path) -> None:
    database = tmp_path / "opportunity_engine.db"
    _create_market_signal_db(
        database,
        [
            {
                "company_name": "Legacy Official AB",
                "payload": _official_payload("Legacy Official AB"),
                "last_seen_at": "2026-08-25T12:35:55+00:00",
            },
            {
                "company_name": "Bulk Clothing Konkurs AB",
                "payload": _official_payload(
                    "Bulk Clothing Konkurs AB",
                    official_bulk_anchor=True,
                ),
                "last_seen_at": "2026-08-25T12:34:00+00:00",
            },
        ],
    )

    anchors = load_sweden_official_company_anchors(
        database_path=database,
        max_anchors=1,
    )

    assert anchors == (("OFFICIAL_COMPANY", "Bulk Clothing Konkurs AB"),)


def test_sweden_uses_official_company_before_generic_catalog(monkeypatch, tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    database = input_root / "se-blinto" / "opportunity_engine.db"
    _create_market_signal_db(
        database,
        [
            {
                "company_name": "Svenska Kläder Konkurs AB",
                "payload": _official_payload("Svenska Kläder Konkurs AB"),
            },
            {
                "company_name": "Mode Lager Likvidation AB",
                "payload": _official_payload("Mode Lager Likvidation AB"),
                "last_seen_at": "2026-08-24T10:00:00+00:00",
            },
        ],
    )
    monkeypatch.setenv("INPUT_ROOT", str(input_root))

    rows = build_commercial_anchor_queries(
        market="SE",
        project_domain=CLOTHING_INVENTORY,
        max_queries=MAX_COMMERCIAL_ANCHOR_QUERIES_PER_MARKET,
    )

    assert len(rows) == 2
    assert all(row["anchor_type"] == "OFFICIAL_COMPANY" for row in rows)
    assert all(row["anchor_origin"] == SWEDEN_OFFICIAL_ANCHOR_ORIGIN for row in rows)
    assert all(row["anchor_is_qualification_evidence"] is False for row in rows)
    assert all(row["source_specific"] is False for row in rows)
    assert all(_market_anchored(row["query"], "SE") for row in rows)
    assert all(classify_project_domain(text=row["query"]) == CLOTHING_INVENTORY for row in rows)
    assert all("site:" not in row["query"].casefold() for row in rows)
    assert {row["anchor_value"] for row in rows} == {
        "Svenska Kläder Konkurs AB",
        "Mode Lager Likvidation AB",
    }


def test_sweden_falls_back_to_existing_catalog_when_no_official_signal(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("INPUT_ROOT", str(tmp_path / "missing"))

    rows = build_commercial_anchor_queries(
        market="SE",
        project_domain=CLOTHING_INVENTORY,
    )

    assert rows
    assert rows[0]["anchor_type"] == "BRAND"
    assert rows[0]["anchor_value"] == "Jack & Jones"
    assert rows[0]["anchor_origin"] == "CONTROLLED_GLOBAL_CATALOG_V1"


def test_official_company_name_is_never_qualification_evidence(monkeypatch, tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    database = input_root / "se-blinto" / "opportunity_engine.db"
    _create_market_signal_db(
        database,
        [{"company_name": "Verified Konkurs Mode AB", "payload": _official_payload("Verified Konkurs Mode AB")}],
    )
    monkeypatch.setenv("INPUT_ROOT", str(input_root))

    row = build_commercial_anchor_queries(
        market="SE",
        project_domain=CLOTHING_INVENTORY,
        max_queries=1,
    )[0]

    assert row["anchor_type"] == "OFFICIAL_COMPANY"
    assert row["anchor_is_qualification_evidence"] is False
    assert "Verified Konkurs Mode AB" in row["query"]
