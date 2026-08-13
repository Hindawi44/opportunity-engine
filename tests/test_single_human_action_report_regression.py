from __future__ import annotations

from pathlib import Path

from opportunity_engine.discovery.central_intelligence_orchestrator_cli_hook import (
    _rewrite_delivery_text,
)


def test_central_rewrite_replaces_legacy_action_without_dropping_later_sections(
    tmp_path: Path,
) -> None:
    domain_text = tmp_path / "domain-market-intelligence-brief.txt"
    domain_text.write_text(
        "\n".join(
            [
                "نشرة استخبارات سوق مخزون الملابس",
                "أفضل فرصة مباشرة اليوم:",
                "الاسم: Example opportunity",
                "",
                "الإجراء البشري الوحيد: راجع فرصة واحدة تحتاج إلى تحقق",
                "السبب: قرار أولي قبل العقل المركزي.",
                "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي.",
                "",
                "## Fabric procurement watch",
                "FABRIC PROCUREMENT WATCH",
                "candidate_count: 7",
                "",
            ]
        ),
        encoding="utf-8",
    )

    brief = {
        "status": "SUCCESS",
        "market_visibility": ["NO", "SE", "DE", "IT"],
        "today_snapshot": {
            "actionable_now_count": 1,
            "market_watch_count": 2,
            "fabric_candidate_count": 7,
            "fabric_ai_status": "SUCCESS",
            "market_decision_quality": "UNIFIED_PRIORITY_ONLY",
            "official_route_status": "ROUTE_INPUT_REQUIRED",
            "official_freight_status": "SHIPMENT_INPUT_REQUIRED",
        },
        "top_actionable_opportunity": {
            "headline": "Example opportunity",
            "source_urls": ["https://example.test/opportunity"],
        },
        "top_market_signal": {
            "headline": "Example market signal",
            "source_urls": ["https://example.test/signal"],
        },
        "top_fabric_supplier": {
            "source_name": "Example Fabrics",
            "source_url": "https://example.test/fabric",
            "ai_review_priority": "HIGH",
        },
        "primary_human_action": {
            "action_type": "PROVIDE_SHIPMENT_INPUTS_FOR_OFFICIAL_QUOTE",
            "target": "Example opportunity",
            "reason": "Structured shipment inputs are still missing.",
        },
    }

    _rewrite_delivery_text(tmp_path, brief)

    text = domain_text.read_text(encoding="utf-8")
    assert text.count("الإجراء البشري الوحيد:") == 1
    assert "قرار أولي قبل العقل المركزي" not in text
    assert "FABRIC PROCUREMENT WATCH" in text
    assert "candidate_count: 7" in text
    assert "PROVIDE_SHIPMENT_INPUTS_FOR_OFFICIAL_QUOTE" in text
    assert text.count("CENTRAL INTELLIGENCE ORCHESTRATOR") == 1
