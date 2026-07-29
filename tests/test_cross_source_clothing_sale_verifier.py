import json
from datetime import date
from pathlib import Path

from opportunity_engine.discovery.auksjonen_multi_category_adapter import (
    AuksjonenCategoryScan,
    AuksjonenCategorySpec,
    AuksjonenMultiCategoryResult,
)
from opportunity_engine.discovery.auksjonen_public_api_adapter import (
    AuksjonenLiveClothingListing,
)
from opportunity_engine.discovery.cross_source_clothing_sale_verifier import (
    AuksjonenItemIdentityEvidence,
    BankruptcyIdentityLead,
    CrossSourceClothingSaleVerifier,
    is_approved_auksjonen_item_url,
    match_listing_to_bankruptcy_leads,
    normalize_entity_name,
    parse_auksjonen_item_identity,
    write_cross_source_artifacts,
)
from opportunity_engine.discovery.konkurs_app_clothing_adapter import (
    normalize_api_record,
)

TODAY = date(2026, 7, 30)


def bankruptcy_record(**overrides):
    record = {
        "orgnr": "938018014",
        "navn": "MENSWEAR NORGE AS KONKURSBO",
        "stiftelsesdato": "2026-07-01",
        "registreringsdato": "2026-07-01",
        "naeringskode": "47.710",
        "naeringsbeskrivelse": "Detaljhandel med klær",
        "kommune": "OSLO",
        "poststed": "OSLO",
        "mva_registrert": 1,
        "aktiv": 1,
        "debitor_navn": "MENSWEAR NORGE AS",
        "debitor_orgnr": "930111222",
        "regnskap_aar": "2025",
        "regnskap_valuta": "NOK",
        "regnskap_driftsinntekter": 12_000_000,
        "regnskap_sum_eiendeler": 3_000_000,
        "regnskap_sum_gjeld": 4_000_000,
    }
    record.update(overrides)
    return record


def identity_lead(**overrides):
    record = bankruptcy_record(**overrides)
    lead = normalize_api_record(record, today=TODAY)
    assert lead is not None
    return BankruptcyIdentityLead(lead=lead, debtor_orgnr=record["debitor_orgnr"])


def inventory_listing(**overrides):
    values = {
        "title": "Vareparti med 200 herreklær",
        "url": "https://ny.auksjonen.no/auksjon/torget/Vareparti_med_200_herreklaer/700001",
        "auction_id": 900001,
        "object_id": 700001,
        "status": "INPROGRESS",
        "listing_status": "ACTIVE",
        "current_bid_nok": 10_000.0,
        "buy_now_price_nok": None,
        "start_price_nok": 0.0,
        "bid_count": 2,
        "bidder_count": 2,
        "city": "Oslo",
        "zip_code": "0001",
        "address": None,
        "ends_at": "2026-08-10T10:00:00+00:00",
        "main_image": "image.jpg",
        "inventory_lot_signal": True,
    }
    values.update(overrides)
    return AuksjonenLiveClothingListing(**values)


def item_html(*, company="MENSWEAR NORGE AS", orgnr="930 111 222"):
    state = {
        "auction-700001": {
            "projectAuctionText": (
                f"Selges på vegne av {company}. Organisasjonsnummer: {orgnr}."
            ),
            "description": "Vareparti med 200 herreklær selges samlet.",
            "principalId": 12345,
        }
    }
    product = {
        "@type": "Product",
        "name": "Vareparti med 200 herreklær",
        "offers": {
            "@type": "Offer",
            "availability": "https://schema.org/InStock",
            "seller": {"@type": "Organization", "name": company},
        },
    }
    return f"""
    <html><head>
      <meta name="description" content="Vareparti · Selges av {company} · Oslo">
      <script id="structured-data-product" type="application/ld+json">{json.dumps(product)}</script>
      <script id="ng-state" type="application/json">{json.dumps(state)}</script>
    </head><body></body></html>
    """


def multi_category_result(listings):
    category = AuksjonenCategorySpec("10110508", "Klær, kosmetikk og accessoirer")
    scan = AuksjonenCategoryScan(
        category=category,
        reported_size=len(listings),
        items_received=len(listings),
        pages_fetched=1,
        page_size=30,
        max_pages=10,
        listings=tuple(listings),
        errors=(),
    )
    return AuksjonenMultiCategoryResult(
        captured_at="2026-07-30T00:00:00+00:00",
        scans=(scan,),
        max_listings=300,
    )


class FakeAuksjonenCollector:
    def __init__(self, result):
        self.result = result

    def collect(self):
        return self.result


def test_parser_extracts_exact_public_company_and_orgnr_evidence():
    listing = inventory_listing()
    evidence = parse_auksjonen_item_identity(
        item_html(), item_url=listing.url, object_id=listing.object_id
    )

    assert evidence.source_status == "PARSED"
    assert "MENSWEAR NORGE AS" in evidence.entity_names
    assert evidence.organisation_numbers == ("930111222",)
    assert evidence.seller_label == "MENSWEAR NORGE AS"
    assert "Selges på vegne av" in evidence.project_auction_text


def test_exact_orgnr_promotes_active_inventory_lot_to_verified_sale():
    listing = inventory_listing()
    lead = identity_lead()
    evidence = parse_auksjonen_item_identity(
        item_html(), item_url=listing.url, object_id=listing.object_id
    )

    record = match_listing_to_bankruptcy_leads(listing, evidence, [lead])

    assert record.match_method == "EXACT_ORGANISATION_NUMBER"
    assert record.verification_state == "VERIFIED_ACTIVE_INVENTORY_SALE"
    assert record.inventory_sale_verified is True
    assert record.requires_human_verification is False
    assert record.to_dict()["top5_eligible"] is True


def test_exact_name_without_orgnr_is_review_only_and_not_top5():
    listing = inventory_listing()
    lead = identity_lead()
    evidence = parse_auksjonen_item_identity(
        item_html(orgnr=""), item_url=listing.url, object_id=listing.object_id
    )

    record = match_listing_to_bankruptcy_leads(listing, evidence, [lead])

    assert record.match_method == "EXACT_NORMALIZED_COMPANY_NAME"
    assert record.inventory_sale_verified is False
    assert record.requires_human_verification is True
    assert record.to_dict()["top5_eligible"] is False
    assert record.to_dict()["analysis_eligible"] is False


def test_weak_or_generic_seller_evidence_never_matches():
    listing = inventory_listing()
    lead = identity_lead()
    evidence = AuksjonenItemIdentityEvidence(
        item_url=listing.url,
        object_id=listing.object_id,
        seller_label="Næringsvirksomhet (ikke av Auksjonen.no)",
        project_auction_text=None,
        meta_description="Selges av Næringsvirksomhet (ikke av Auksjonen.no)",
        entity_names=(),
        organisation_numbers=(),
        source_status="PARSED",
    )

    record = match_listing_to_bankruptcy_leads(listing, evidence, [lead])

    assert record.match_method == "NONE"
    assert record.inventory_sale_verified is False
    assert record.requires_human_verification is False


def test_individual_item_never_enters_cross_source_commercial_gate():
    listing = inventory_listing(
        title="Jakke størrelse XL",
        inventory_lot_signal=False,
    )
    evidence = parse_auksjonen_item_identity(
        item_html(), item_url=listing.url, object_id=listing.object_id
    )

    record = match_listing_to_bankruptcy_leads(listing, evidence, [identity_lead()])

    assert record.verification_state == "NOT_AN_ACTIVE_INVENTORY_LOT"
    assert record.inventory_sale_verified is False


def test_live_collector_uses_two_bankruptcy_queries_and_only_inventory_detail_pages():
    calls = []

    def fetch_json(url):
        calls.append(url)
        return {"data": [bankruptcy_record()]}

    detail_calls = []

    def fetch_html(url):
        detail_calls.append(url)
        return item_html()

    lot = inventory_listing()
    individual = inventory_listing(
        title="Jakke størrelse XL",
        object_id=700002,
        url="https://ny.auksjonen.no/auksjon/torget/Jakke_storrelse_XL/700002",
        inventory_lot_signal=False,
    )
    verifier = CrossSourceClothingSaleVerifier(
        fetch_json=fetch_json,
        fetch_html=fetch_html,
        auksjonen_collector=FakeAuksjonenCollector(
            multi_category_result([individual, lot])
        ),
        today=TODAY,
    )

    result = verifier.collect()

    assert len(calls) == 2
    assert result.bankruptcy_requests == 2
    assert result.bankruptcy_items_received == 2
    assert len(result.bankruptcy_leads) == 1
    assert result.bankruptcy_leads[0].debtor_orgnr == "930111222"
    assert detail_calls == [lot.url]
    assert result.detail_pages_requested == 1
    assert len(result.verified_sales) == 1
    assert result.scan_complete is True
    assert result.errors == ()


def test_artifacts_separate_review_from_verified_commercial_top5(tmp_path: Path):
    name_only_html = item_html(orgnr="")
    verifier = CrossSourceClothingSaleVerifier(
        fetch_json=lambda url: {"data": [bankruptcy_record()]},
        fetch_html=lambda url: name_only_html,
        auksjonen_collector=FakeAuksjonenCollector(
            multi_category_result([inventory_listing()])
        ),
        today=TODAY,
    )
    result = verifier.collect()

    paths = write_cross_source_artifacts(result, tmp_path)
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    review = json.loads(paths["review_top5"].read_text(encoding="utf-8"))
    commercial = json.loads(paths["commercial_top5"].read_text(encoding="utf-8"))
    summary = paths["summary"].read_text(encoding="utf-8")

    assert report["review_lead_count"] == 1
    assert report["verified_inventory_sales"] == 0
    assert len(review) == 1
    assert review[0]["requires_human_verification"] is True
    assert review[0]["top5_eligible"] is False
    assert commercial == []
    assert "Exact-name review leads: 1" in summary
    assert "Exact-orgnr verified inventory sales: 0" in summary


def test_url_and_name_normalization_are_strict():
    assert is_approved_auksjonen_item_url(inventory_listing().url)
    assert not is_approved_auksjonen_item_url("https://evil.example/item/700001")
    assert normalize_entity_name("MENSWEAR NORGE AS KONKURSBO") == "MENSWEAR NORGE AS"
