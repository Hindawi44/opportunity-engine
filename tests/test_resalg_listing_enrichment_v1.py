from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path

from opportunity_engine.discovery import exa_shadow_page_verification as verifier
from opportunity_engine.discovery.keyword_shadow_verification import PageFetchResult
from opportunity_engine.discovery.provider_unique_page_verification import (
    _verify_fetched_candidate,
)
from opportunity_engine.discovery.resalg_listing_enrichment import (
    parse_resalg_listing,
)


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_exa_exact_lot_checkpoint.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_exa_exact_lot_checkpoint_resalg_enrichment",
        RUNNER,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _html(*, deadline: str = "2099-09-18 08:43:00") -> str:
    return f"""
    <meta property="og:title" content="Vinterklær Barn - ReSalg.com">
    <p>Pakket i 1 Palle konteiner</p>
    <p>Varene må hentes på <strong>Stathelle</strong>.</p>
    <p>Det tilkommer <strong>20 % salgsomkostninger</strong> samt mva på hele beløpet.</p>
    <div id="widget-buybox" data-title="Budgivningsalternativer">
      <ul>
        <li class="list-group-item lotid">Produkt-ID <span>#82528</span></li>
        <li class="list-group-item bids">Bud <span>12</span></li>
        <li class="list-group-item condition">Tilstand <span> Ny</span></li>
      </ul>
    </div>
    <script>let gonCurrentPrice = "7000";</script>
    <span data-ppt-countdown="2099-09-18 09:33:32"
          data-postid="82605" data-timezone="2"></span>
    <span data-ppt-countdown="{deadline}"
          data-postid="82528" data-timezone="2"></span>
    """


def _visible_text() -> str:
    return (
        "Vinterklær Barn. Dresser, jakker og bukser. "
        "Pakket i 1 Palle konteiner. Budgivning."
    )


def test_parser_binds_bid_and_deadline_to_current_product_id() -> None:
    facts = parse_resalg_listing(
        url="https://resalg.com/listing/vinter-klaer-barn/",
        html=_html(),
        now=datetime(2026, 9, 10, tzinfo=timezone.utc),
    )

    assert facts is not None
    assert facts["listing_id"] == "82528"
    assert facts["listing_status"] == "ACTIVE"
    assert facts["current_bid"]["amount"] == 7000.0
    assert facts["current_bid"]["currency"] == "NOK"
    assert facts["bid_count"] == 12
    assert facts["ends_at"] == "2099-09-18T08:43:00+02:00"
    assert facts["condition"] == "NEW"
    assert facts["pickup_location"] == "Stathelle"
    assert facts["lot_container_quantity"] == {
        "amount": 1,
        "unit": "PALLET_CONTAINER",
    }
    assert facts["buyer_fee_percent"] == 20
    assert facts["vat_applies_to_entire_amount"] is True


def test_resalg_source_values_replace_retail_value_noise_and_make_exact_lot() -> None:
    classification, evidence = verifier._classify_page(
        title="Vinterklær Barn",
        text=(
            f"{_visible_text()} Varer i utsalg fra butikk for kr 143 367. "
            "Relatert vare koster 104 000 NOK."
        ),
        url="https://resalg.com/listing/vinter-klaer-barn/",
        raw_html=_html(),
    )

    assert classification == verifier.EXACT_LOT_CANDIDATE
    assert evidence["item_specific_url_evidence"] is True
    assert evidence["source_native_price_candidates"] == ["7000 NOK"]
    assert evidence["source_native_quantity_candidates"] == ["1 Palle konteiner"]
    assert evidence["source_current_bid"]["amount"] == 7000.0
    assert evidence["auction_end_at"] == "2099-09-18T08:43:00+02:00"


def test_ended_resalg_deadline_cannot_enter_active_exact_lot_lane() -> None:
    classification, evidence = verifier._classify_page(
        title="Vinterklær Barn",
        text=_visible_text(),
        url="https://resalg.com/listing/vinter-klaer-barn/",
        raw_html=_html(deadline="2020-09-18 08:43:00"),
    )

    assert classification == verifier.UNPROVEN_PAGE
    assert evidence["source_listing_status"] == "ENDED"


def test_resalg_404_is_fetch_failed_and_cannot_reuse_search_cache() -> None:
    candidate = {
        "market_code": "NO",
        "query": "Norge klær vareparti nettauksjon",
        "title": "Cached ended ReSalg lot",
        "url": "https://resalg.com/listing/vareparti-med-klaer-2/",
        "domain": "resalg.com",
        "provider": "exa",
    }

    row, ok = _verify_fetched_candidate(
        candidate,
        page_fetcher=lambda url: PageFetchResult(
            requested_url=url,
            final_url=url,
            ok=False,
            status_code=404,
            title="",
            text="",
            error="HTTP_404",
        ),
        allow_tool_learning_credit=True,
    )

    assert ok is False
    assert row["classification"] == verifier.FETCH_FAILED
    assert row["status_code"] == 404
    assert row["tool_learning_useful"] is False
    assert row["evidence"] == {}


def test_checkpoint_candidate_carries_resalg_bid_deadline_and_pallet_basis() -> None:
    classification, evidence = verifier._classify_page(
        title="Vinterklær Barn",
        text=_visible_text(),
        url="https://resalg.com/listing/vinter-klaer-barn/",
        raw_html=_html(),
    )
    assert classification == verifier.EXACT_LOT_CANDIDATE
    runner = _load_runner()

    candidate = runner._candidate_from_exact_lot(
        {
            "url": "https://resalg.com/listing/vinter-klaer-barn/",
            "final_url": "https://resalg.com/listing/vinter-klaer-barn/",
            "title": "Vinterklær Barn",
            "query": "Norge klær vareparti nettauksjon",
            "exact_lot_origin": "DIRECT_SEARCH_RESULT",
            "evidence": evidence,
        },
        market="NO",
    )

    assert candidate["listing_status"] == "ACTIVE"
    assert candidate["sale_mode"] == "AUCTION"
    assert candidate["current_bid"] == 7000.0
    assert candidate["currency"] == "NOK"
    assert candidate["auction_end_text"] == "2099-09-18T08:43:00+02:00"
    assert candidate["lot_units"] == 1
    assert candidate["lot_unit_type"] == "PALLET_CONTAINER"
    assert candidate["stock_location"] == "Stathelle"
    assert candidate["analysis_eligible"] is False
