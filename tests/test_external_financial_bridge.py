import json

from opportunity_engine.external_financial_bridge import (
    collect_external_financial_evidence,
    merge_evidence,
)


def test_collects_only_explicit_nok_market_prices(tmp_path):
    payload = {
        "evidence": [
            {
                "evidence_id": "rev_1",
                "opportunity_id": "opp-1",
                "evidence_type": "market_price",
                "source_name": "external_market_comparable",
                "source_url": "https://example.no/item",
                "observations": [
                    {"numeric_value": 12500, "currency": "NOK", "observed_at": "2026-01-01T00:00:00Z"},
                    {"numeric_value": 99, "currency": "USD", "observed_at": "2026-01-01T00:00:00Z"},
                ],
            },
            {
                "evidence_id": "rev_2",
                "opportunity_id": "opp-1",
                "evidence_type": "buyer",
                "source_name": "buyer",
                "source_url": "https://buyer.no",
                "observations": [{"numeric_value": 5000, "currency": "NOK"}],
            },
        ]
    }
    (tmp_path / "opp-1.json").write_text(json.dumps(payload), encoding="utf-8")

    result = collect_external_financial_evidence(tmp_path)

    assert result["opp-1"]["market_comparables"] == [
        {
            "verified": True,
            "source": "external_market_comparable",
            "url": "https://example.no/item",
            "price_nok": 12500.0,
            "evidence_id": "rev_1",
            "observed_at": "2026-01-01T00:00:00Z",
        }
    ]


def test_merge_preserves_cost_inputs_and_deduplicates_comparables():
    existing = {
        "evidence": {
            "opp-1": {
                "transport_cost_nok": 1000,
                "market_comparables": [
                    {"verified": True, "source": "x", "url": "https://x.no", "price_nok": 5000}
                ],
            }
        }
    }
    external = {
        "opp-1": {
            "market_comparables": [
                {"verified": True, "source": "x", "url": "https://x.no", "price_nok": 5000},
                {"verified": True, "source": "y", "url": "https://y.no", "price_nok": 6000},
            ]
        }
    }

    merged = merge_evidence(existing, external)

    record = merged["evidence"]["opp-1"]
    assert record["transport_cost_nok"] == 1000
    assert len(record["market_comparables"]) == 2
