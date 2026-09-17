"""Read-only source page evidence must not be confused with URL/stock/site truth."""
from __future__ import annotations

import json
from dataclasses import dataclass

from opportunity_engine.source_page_audit import _source_product, audit_review_batch

URL = "https://stockitaly24.com/products/fixed-lot-100"


@dataclass
class Page:
    requested_url: str = URL
    final_url: str = URL
    ok: bool = True
    status_code: int = 200
    title: str = "Fixed lot"
    text: str = "Stock 100 pcs"
    error: str | None = None
    raw_html: str = ""


def html(url=URL, identifier="LOT-100", availability="InStock"):
    return ('<nav>Collections 300 shoes at 10 EUR</nav>'
            '<script type="application/ld+json">'
            + json.dumps({"@context": "https://schema.org", "@type": "Product",
                          "url": url, "name": "Fixed 100-piece lot", "sku": identifier,
                          "offers": {"@type": "Offer", "availability": "https://schema.org/" + availability}})
            + "</script>")


def queue(url=URL):
    row = {"identity": "lot-100", "source_url": url, "title": "Fixed lot", "market": "IT",
           "stock_confidence": "UNVERIFIED", "site_identity_status": "UNVERIFIED",
           "page_type": "DIRECT_URL_SHAPE_ONLY_UNVERIFIED"}
    return {"review_queue": [row], "daily_batch": [row], "held_separately": [],
            "counts": {"direct_waiting_for_review": 1, "daily_batch": 1,
                       "remaining": 0, "url_shape_only_unverified": 1}}


def test_source_product_requires_exact_page_url_and_source_id():
    assert _source_product(html(), URL)["id"] == "LOT-100"
    assert _source_product(html("https://stockitaly24.com/collections/shoes"), URL) is None
    assert _source_product(html(identifier=""), URL) is None
    assert _source_product('<script type="application/ld+json">'
                           + json.dumps({"@type": "ItemList", "itemListElement": [{"@type": "Product", "url": URL, "sku": "fake"}]})
                           + "</script>", URL) is None


def test_anchored_native_identity_does_not_prove_stock_or_site():
    result = audit_review_batch(queue(), fetcher=lambda _: Page(raw_html=html()),
                                checked_at="2026-09-17T10:00:00Z")
    row = result["daily_batch"][0]
    assert row["source_page_check_status"] == "SOURCE_PRODUCT_ID_EVIDENCE"
    assert row["source_product_identifier"] == "LOT-100"
    assert row["page_type"] == "SOURCE_PRODUCT_ID_EVIDENCE_NOT_FIXED_LOT"
    assert row["stock_confidence"] == "UNVERIFIED"
    assert row["site_identity_status"] == "UNVERIFIED"
    assert result["counts"]["page_audit_product_id_evidence"] == 1
    assert result["counts"]["direct_waiting_for_review"] == 1


def test_page_200_with_nav_prices_is_not_product_identity():
    result = audit_review_batch(queue(), fetcher=lambda _: Page(raw_html="<p>300 pcs 15 EUR</p>"))
    assert result["daily_batch"][0]["source_page_check_status"] == "READABLE_ITEM_IDENTITY_UNPROVEN"
    assert result["counts"]["page_audit_identity_unproven"] == 1


def test_redirect_to_generic_page_held_without_erasing_history():
    result = audit_review_batch(queue(), fetcher=lambda _: Page(final_url="https://stockitaly24.com/collections/all"))
    assert result["review_queue"] == result["daily_batch"] == []
    assert result["held_separately"][0]["reason"] == "REDIRECT_NON_DIRECT_OR_CROSS_SITE_UNVERIFIED"
    assert result["counts"]["direct_waiting_for_review"] == 0
    assert result["counts"]["page_audit_redirect_held"] == 1


def test_cross_site_redirect_does_not_verify_other_site():
    result = audit_review_batch(queue(), fetcher=lambda _: Page(final_url="https://friptadium.com/products/fixed-lot-100"))
    assert result["counts"]["page_audit_redirect_held"] == 1
    assert result["held_separately"]


def test_explicit_structured_source_sold_out_held_not_human_delete():
    result = audit_review_batch(queue(), fetcher=lambda _: Page(raw_html=html(availability="OutOfStock")))
    assert result["counts"]["page_audit_sold_out_held"] == 1
    assert result["review_queue"] == []
    assert result["held_separately"][0]["reason"] == "SOURCE_REPORTED_SOLD_OUT"
    assert "operator_deleted" not in result["counts"]


def test_global_sold_out_cannot_prove_variant_stock():
    variant = URL + "?variant=123"
    raw = html(url=variant, availability="OutOfStock")
    result = audit_review_batch(queue(variant), fetcher=lambda _: Page(final_url=variant, raw_html=raw))
    assert result["counts"]["page_audit_sold_out_held"] == 0
    assert result["daily_batch"][0]["stock_confidence"] == "UNVERIFIED"


def test_blocked_page_remains_unverified_review_record():
    result = audit_review_batch(queue(), fetcher=lambda _: Page(ok=False, status_code=403, error="HTTP_403"))
    assert result["counts"]["page_audit_fetch_failed"] == 1
    assert result["daily_batch"][0]["source_page_check_status"] == "FETCH_FAILED_UNVERIFIED"
    assert result["daily_batch"][0]["stock_confidence"] == "UNVERIFIED"


def test_no_fetch_over_budget_and_does_not_fetch_unshown_records():
    q = queue()
    for idx in range(1, 15):
        record = {"identity": str(idx), "source_url": URL + "-" + str(idx),
                  "title": str(idx), "page_type": "DIRECT_URL_SHAPE_ONLY_UNVERIFIED"}
        q["review_queue"].append(record)
        if idx < 10:
            q["daily_batch"].append(record)
    q["counts"].update(direct_waiting_for_review=15, daily_batch=10, remaining=5)
    fetched = []
    def fetch(url):
        fetched.append(url)
        return Page(requested_url=url, final_url=url, raw_html="<p>Not proven</p>")
    result = audit_review_batch(q, fetcher=fetch)
    assert len(fetched) == 10
    assert result["counts"]["page_audit_attempted"] == 10
    assert result["counts"]["remaining"] == 5


def test_zero_audit_budget_is_safe_and_no_network():
    result = audit_review_batch(queue(), limit=0, fetcher=lambda _: (_ for _ in ()).throw(AssertionError("fetch")))
    assert result["counts"]["page_audit_attempted"] == 0
    assert result["counts"]["direct_waiting_for_review"] == 1
