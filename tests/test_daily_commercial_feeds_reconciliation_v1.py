import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_domain_market_intelligence_feed.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("daily_commercial_reconciliation", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bridal_highlights_surface_named_no_se_de_signals_and_filter_other_markets() -> None:
    module = _load_module()
    report = {
        "sources": [
            {
                "signals": [
                    {
                        "signal_id": "se-1",
                        "source_country": "SE",
                        "title": "Utförsäljning av brudklänningar",
                        "source_url": "https://example.se/utforsaljning",
                        "status": "WATCH",
                        "confidence": 0.75,
                        "metadata": {"verification_status": "UNVERIFIED_PUBLIC_WEB"},
                    },
                    {
                        "signal_id": "nl-1",
                        "source_country": "NL",
                        "title": "Outside production market scope",
                        "source_url": "https://example.nl/clearance",
                        "status": "WATCH",
                        "confidence": 0.99,
                    },
                ]
            }
        ]
    }

    highlights = module._bridal_highlights(report)

    assert len(highlights) == 1
    assert highlights[0]["signal_id"] == "se-1"
    assert highlights[0]["source_country"] == "SE"
    assert highlights[0]["title"] == "Utförsäljning av brudklänningar"
    assert highlights[0]["source_url"] == "https://example.se/utforsaljning"


def test_b2b_compaction_preserves_commercial_decision_fields() -> None:
    module = _load_module()
    compact = module._compact_b2b_candidate(
        {
            "candidate_id": "merkandi-b2b:1",
            "source_name": "Merkandi",
            "title": "Clothing liquidation stocklot",
            "source_url": "https://merkandi.com/example",
            "quantity": 500,
            "quantity_unit": "units",
            "total_price": 1500,
            "currency": "EUR",
            "stock_location": "Germany",
            "b2b_relevance_score": 82,
            "opportunity_state": "B2B_LEAD_REQUIRES_VERIFICATION",
            "missing_information": ["SELLER_IDENTITY"],
            "irrelevant_internal_field": "must not leak",
        }
    )

    assert compact["candidate_id"] == "merkandi-b2b:1"
    assert compact["quantity"] == 500
    assert compact["currency"] == "EUR"
    assert compact["stock_location"] == "Germany"
    assert compact["b2b_relevance_score"] == 82
    assert "irrelevant_internal_field" not in compact
