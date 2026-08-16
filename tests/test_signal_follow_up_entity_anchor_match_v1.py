from __future__ import annotations

from datetime import datetime, timezone

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.signal_follow_up_continuity import (
    run_signal_follow_up_engine_with_continuity,
)


FIRST_SEEN = "2026-08-15T14:18:02+00:00"


def _schuemer_signal() -> dict:
    return {
        "signal_id": "schuemer-entity-scent",
        "signal_type": "INSOLVENCY_OR_LIQUIDATION",
        "source": "Cross-source scent expansion V2 + entity quality gate V1",
        "source_country": "DE",
        "source_url": "https://example.test/schuemer-source",
        "title": "Schümer Textil GmbH insolvency signal",
        "first_observed_at": FIRST_SEEN,
        "latest_observed_at": FIRST_SEEN,
        "observed_at": FIRST_SEEN,
        "status": "WATCH",
        "confidence": 0.72,
        "metadata": {
            "entity_scent_classification": "ENTITY_SCENT",
            "entity_scent_quality_gate": "ENTITY_SCENT_QUALITY_GATE_V1",
            "entity_key": "schümer textil",
            "entity_label": "Schümer Textil GmbH",
            "entity_cluster_score": 75,
            "entity_evidence_count": 1,
            "entity_independent_source_count": 1,
            "signal_only": True,
            "source_page_verification_required": True,
            "promotion_to_opportunity_allowed": False,
        },
        "evidence": [],
        "missing_information": [],
    }


class _FakeProvider:
    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits

    def search(self, query: str, *, count: int = 10) -> list[SearchHit]:
        return self.hits[:count]


def _run(hits: list[SearchHit]) -> dict:
    provider = _FakeProvider(hits)
    return run_signal_follow_up_engine_with_continuity(
        {"cases": []},
        entity_signals=[_schuemer_signal()],
        environment={"BRAVE_SEARCH_API_KEY": "test-key"},
        provider_factory=lambda market, key: provider,
        observed_at=datetime(2026, 8, 16, 8, 0, tzinfo=timezone.utc),
        max_cases=1,
        results_per_case=5,
    )


def test_generic_gmbh_auction_is_not_identity_evidence_for_schuemer() -> None:
    report = _run(
        [
            SearchHit(
                title="Wallow Auktionen GmbH – aktuelle Versteigerung",
                url="https://wallow.example/auction",
                description="GmbH versteigert Warenbestand und Restposten.",
                provider="Brave Search",
            )
        ]
    )

    assert report["commercial_lead_count"] == 0
    assert report["top_follow_up_lead"] is None
    assert report["cases"][0]["leads"] == []
    assert report["cases"][0]["follow_up_state"] == "MONITORING"


def test_distinctive_schuemer_anchor_qualifies_the_auction_lead() -> None:
    report = _run(
        [
            SearchHit(
                title="Schümer Auktion – Warenbestand wird versteigert",
                url="https://auction.example/schuemer-stock",
                description="Textil-Warenbestand aus der Verwertung.",
                provider="Brave Search",
            )
        ]
    )

    assert report["commercial_lead_count"] == 1
    lead = report["cases"][0]["leads"][0]
    assert lead["source_url"] == "https://auction.example/schuemer-stock"
    assert lead["entity_identity_anchor"] == "schümer"
    assert "schümer" in lead["matched_target_tokens"]
    assert lead["verification_status"] == "UNVERIFIED_PUBLIC_WEB_SEARCH_HIT"
    assert lead["promotion_to_opportunity_allowed"] is False


def test_entity_anchor_uses_exact_token_boundary_not_substring() -> None:
    report = _run(
        [
            SearchHit(
                title="Altschümer GmbH Auktion",
                url="https://auction.example/altschuemer",
                description="Warenbestand wird versteigert.",
                provider="Brave Search",
            )
        ]
    )

    assert report["commercial_lead_count"] == 0
    assert report["cases"][0]["leads"] == []
