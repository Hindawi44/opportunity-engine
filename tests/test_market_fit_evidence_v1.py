from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from opportunity_engine.discovery import market_fit_evidence_v1 as market_fit


def test_supported_market_fit_requires_multiple_independent_signal_families() -> None:
    evidence = market_fit.assess_market_fit_evidence(
        market="IT",
        url="https://stock.example.it/lotto/123",
        title="Stock abbigliamento Italia",
        text="Sede in Italia. Tel +39 02 1234567.",
    )

    assert evidence["status"] == "SUPPORTED_MARKET_FIT"
    assert set(evidence["matching_signal_families"]) == {
        "COUNTRY_TERM",
        "HOST_CCTLD",
        "PHONE_PREFIX",
    }
    assert evidence["market_fit_is_qualification_evidence"] is False
    assert evidence["changes_exact_lot_decision"] is False


def test_conflicting_foreign_host_and_phone_are_reported_not_auto_rejected() -> None:
    evidence = market_fit.assess_market_fit_evidence(
        market="IT",
        url="https://lager.example.de/posten/77",
        title="Bekleidung Restposten",
        text="Kontakt +49 30 123456",
    )

    assert evidence["status"] == "CONFLICTING_MARKET_EVIDENCE"
    assert "DE" in evidence["conflicting_market_codes"]
    assert evidence["automatic_rejection"] is False
    assert evidence["production_mutation"] is False


def test_generic_com_with_one_country_signal_stays_partial() -> None:
    evidence = market_fit.assess_market_fit_evidence(
        market="NL",
        url="https://wholesale.example.com/partij/12",
        title="Nederland kledingpartij",
        text="Wholesale stock available now",
    )

    assert evidence["status"] == "PARTIAL_MARKET_EVIDENCE"
    assert evidence["matching_signal_families"] == ["COUNTRY_TERM"]


def test_shared_euro_symbol_is_not_country_identity_evidence() -> None:
    evidence = market_fit.assess_market_fit_evidence(
        market="DE",
        url="https://example.com/lot/1",
        title="Clothing lot € 1000",
        text="100 pieces available",
    )

    assert evidence["status"] == "UNPROVEN_MARKET_FIT"
    assert evidence["matching_signal_family_count"] == 0


def test_row_annotation_preserves_upstream_classification_and_tool_learning(monkeypatch) -> None:
    market_fit._MARKET_FIT_BY_MARKET_URL.clear()

    def upstream(candidate, *, page_fetcher, allow_tool_learning_credit):
        fetched = page_fetcher(candidate["url"])
        assert fetched.ok is True
        return (
            {
                **candidate,
                "classification": "EXACT_LOT_CANDIDATE",
                "tool_learning_useful": allow_tool_learning_credit,
                "evidence": {"project_domain": "CLOTHING_INVENTORY"},
            },
            True,
        )

    fetched = SimpleNamespace(
        ok=True,
        final_url="https://stock.example.no/parti/1",
        title="Norge restlager klær",
        text="Norge lager. Ring +47 12345678. Pris 1000 NOK.",
    )
    monkeypatch.setattr(market_fit, "_UPSTREAM_VERIFY_ROW", upstream)

    row, ok = market_fit._verify_row_with_market_fit(
        {
            "market_code": "NO",
            "url": "https://stock.example.no/parti/1",
            "title": "lot",
        },
        page_fetcher=lambda _url: fetched,
        allow_tool_learning_credit=True,
    )

    assert ok is True
    assert row["classification"] == "EXACT_LOT_CANDIDATE"
    assert row["tool_learning_useful"] is True
    assert row["market_fit_evidence"]["status"] == "SUPPORTED_MARKET_FIT"
    assert row["exact_lot_decision_changed_by_market_fit"] is False
    assert market_fit._MARKET_FIT_BY_MARKET_URL[
        ("NO", "https://stock.example.no/parti/1")
    ]["status"] == "SUPPORTED_MARKET_FIT"


def test_report_annotation_adds_zero_budget_and_no_qualification_effect(monkeypatch) -> None:
    def upstream(*_args, **_kwargs):
        return {
            "status": "SUCCESS",
            "strict_exact_lot_count": 2,
            "verified_pages": [
                {"market_fit_evidence": {"status": "SUPPORTED_MARKET_FIT"}},
                {"market_fit_evidence": {"status": "UNPROVEN_MARKET_FIT"}},
            ],
        }

    monkeypatch.setattr(market_fit, "_UPSTREAM_VERIFY_REPORT", upstream)
    report = market_fit._verify_report_with_market_fit({})

    assert report["strict_exact_lot_count"] == 2
    assert report["market_fit_status_counts"] == {
        "SUPPORTED_MARKET_FIT": 1,
        "UNPROVEN_MARKET_FIT": 1,
    }
    assert report["search_requests_added_by_market_fit"] == 0
    assert report["page_fetches_added_by_market_fit"] == 0
    assert report["market_fit_is_qualification_evidence"] is False
    assert report["market_fit_changes_exact_lot_decision"] is False


def test_exact_lot_result_reuses_existing_market_fit_after_hard_gate(monkeypatch) -> None:
    market_fit._MARKET_FIT_BY_MARKET_URL.clear()
    url = "https://stock.example.se/parti/640"
    evidence = market_fit.assess_market_fit_evidence(
        market="SE",
        url=url,
        title="Sverige klädparti",
        text="Sverige lager. Ring +46 8 123456. Pris 1000 SEK.",
    )
    market_fit._cache_market_fit_evidence(market="SE", evidence=evidence, urls=[url])
    monkeypatch.setattr(
        market_fit,
        "_UPSTREAM_TOP5_GATE",
        lambda result: deepcopy(dict(result)),
    )

    candidate = {
        "market_code": "SE",
        "source_urls": [url],
        "canonical_urls": [url],
        "opportunity_identity": url,
        "verification": [{"verified": True}],
        "top5_eligible": True,
        "analysis_eligible": False,
    }
    result = {
        "search_run_report": {
            "source_mode": "EXA_EXACT_LOT_MULTIHOP",
            "market_code": "SE",
            "strict_exact_lot_count": 1,
        },
        "all_discovered_candidates": [candidate],
        "discovery_top5": [deepcopy(candidate)],
    }

    corrected = market_fit._apply_reused_market_fit_to_exact_lot_result(result)
    report = corrected["search_run_report"]
    row = corrected["all_discovered_candidates"][0]

    assert report["strict_exact_lot_count"] == 1
    assert report["market_fit_exact_lot_reused_evidence_count"] == 1
    assert report["market_fit_exact_lot_unavailable_count"] == 0
    assert report["market_fit_status_counts"] == {"SUPPORTED_MARKET_FIT": 1}
    assert report["search_requests_added_by_market_fit"] == 0
    assert report["page_fetches_added_by_market_fit"] == 0
    assert report["market_fit_changes_exact_lot_decision"] is False
    assert row["market_fit_evidence"]["status"] == "SUPPORTED_MARKET_FIT"
    assert row["market_fit_evidence_reused_from_verification"] is True
    assert row["top5_eligible"] is True
    assert corrected["discovery_top5"][0]["market_fit_evidence"]["status"] == (
        "SUPPORTED_MARKET_FIT"
    )


def test_exact_lot_result_marks_missing_reused_page_evidence_without_refetch(monkeypatch) -> None:
    market_fit._MARKET_FIT_BY_MARKET_URL.clear()
    monkeypatch.setattr(
        market_fit,
        "_UPSTREAM_TOP5_GATE",
        lambda result: deepcopy(dict(result)),
    )
    url = "https://example.com/lot/1"
    candidate = {
        "market_code": "NL",
        "source_urls": [url],
        "canonical_urls": [url],
        "opportunity_identity": url,
        "verification": [{"verified": True}],
        "top5_eligible": True,
        "analysis_eligible": False,
    }
    result = {
        "search_run_report": {
            "source_mode": "EXA_EXACT_LOT_MULTIHOP",
            "market_code": "NL",
            "strict_exact_lot_count": 1,
        },
        "all_discovered_candidates": [candidate],
        "discovery_top5": [deepcopy(candidate)],
    }

    corrected = market_fit._apply_reused_market_fit_to_exact_lot_result(result)
    row = corrected["all_discovered_candidates"][0]
    report = corrected["search_run_report"]

    assert row["market_fit_evidence"]["status"] == "UNAVAILABLE"
    assert row["market_fit_evidence"]["reason"] == "NO_REUSED_PAGE_EVIDENCE"
    assert row["market_fit_evidence_reused_from_verification"] is False
    assert report["market_fit_exact_lot_reused_evidence_count"] == 0
    assert report["market_fit_exact_lot_unavailable_count"] == 1
    assert report["search_requests_added_by_market_fit"] == 0
    assert report["page_fetches_added_by_market_fit"] == 0
