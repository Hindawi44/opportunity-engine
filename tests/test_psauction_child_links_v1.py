from types import SimpleNamespace

import pytest

from opportunity_engine.psauction_child_links import (
    MAX_PARENT_READS, extract_child_anchors, extract_parent_children, readable_child_links,
)

PARENT = "https://psauction.se/auction/69239/avyttring-av-arbets-och-skyddsklader-frakt-mojligt-4"
ITEM = "https://psauction.se/item/view/1567233/jacka-cutter-buck-xs"


def balanced(*urls):
    return {"campaign_parents_for_child_extraction": [
        {"identity": f"parent-{i}", "source_url": url, "title": f"Parent {i}",
         "market": "SE", "role": "PARENT_PAGE_FIND_CHILD_LISTINGS",
         "offer_or_stock_verified": False}
        for i, url in enumerate(urls)
    ]}


def response(html, *, final=PARENT, ok=True, status=200):
    return SimpleNamespace(raw_html=html, final_url=final, ok=ok,
                           status_code=status, error="HTTP_202" if not ok else None)


def test_literal_source_anchors_only_with_native_id_and_source_title():
    html = '''<html><a href="/item/view/1567233/jacka-cutter-buck-xs"><h3>Jacka Cutter &amp; Buck XS</h3></a>
    <a href="https://www.psauction.se/item/view/1567258/arbetsbyxor"><img alt="2 st arbetsbyxor"></a>
    <a href="/item/view/1567233/jacka-cutter-buck-xs">duplicate</a>
    <a href="https://evil-psauction.se/item/view/123/fake">spoof</a>
    <a href="https://psauction.se.evil.test/item/view/124/fake">spoof</a>
    <a href="/auction/69239/parent">parent not item</a>
    <a href="/item/view/123/fake?redirect=evil">query variant</a>
    <script>"/item/view/999/not-an-anchor"</script></html>'''
    result = extract_child_anchors(html, PARENT)
    assert [i["native_item_id"] for i in result] == ["1567233", "1567258"]
    assert result[0]["source_url"] == ITEM
    assert "Jacka Cutter" in result[0]["title_from_parent_anchor"]
    assert result[1]["title_from_parent_anchor"] == "2 st arbetsbyxor"


def test_no_fabricated_links_from_numbers_but_generic_source_item_href_is_kept():
    html = '''36 objekt <span>1567233 Jacka Cutter &amp; Buck</span>
    <a href="/item/view/1567233/jacka-cutter-buck-xs">Mer info</a>
    <a href="/item/view/123"></a>'''
    result = extract_child_anchors(html, PARENT)
    assert len(result) == 1 and result[0]["source_url"] == ITEM
    assert result[0]["title_from_parent_anchor"] is None
    assert result[0]["title_evidence"] == "NOT_EXTRACTED"
    assert extract_child_anchors("36 objekt 1567233", PARENT) == []
    assert extract_child_anchors(html, "https://psauction.se/auctions") == []


def test_bounded_parent_extraction_preserves_provenance_and_unverified_flags():
    html = '<a href="/item/view/1567233/jacka-cutter-buck-xs">12 jackor</a>'
    called = []
    def fetch(url):
        called.append(url)
        return response(html)
    result = extract_parent_children(balanced(PARENT), fetcher=fetch,
                                     checked_at="2026-09-17T13:00:00+00:00")
    assert called == [PARENT]
    assert result["counts"]["parents_attempted"] == 1
    assert result["counts"]["child_links_extracted_unverified"] == 1
    assert result["counts"]["parents_with_child_links"] == 1
    assert result["parents"][0]["child_listings_extracted"] is True
    child = result["child_item_url_leads"][0]
    assert child["source_url"] == ITEM and child["parent_url"] == PARENT
    assert child["identity"] == "psauction-item:1567233"
    assert child["operator_decision"] is None
    assert not child["stock_verified"] and not child["seller_verified"]
    assert not child["item_page_verified"] and not child["commercially_qualified"]
    assert "1567233" in readable_child_links(result)
    assert result["paid_search_requests"] == 0


def test_blocked_is_not_zero_stock_and_parent_redirect_not_mined():
    blocked = extract_parent_children(balanced(PARENT), fetcher=lambda _: response("", ok=False, status=202))
    assert blocked["counts"]["parent_fetch_failed"] == 1
    assert blocked["counts"]["child_links_extracted_unverified"] == 0
    assert blocked["parents"][0]["child_extraction_status"] == "FETCH_FAILED_UNVERIFIED"
    redirected = extract_parent_children(balanced(PARENT), fetcher=lambda _: response(
        f'<a href="{ITEM}">12 jackets</a>', final="https://psauction.se/auctions"))
    assert redirected["counts"]["child_links_extracted_unverified"] == 0
    assert redirected["parents"][0]["child_extraction_status"] == "REDIRECTED_PARENT_NOT_MINED"
    js = extract_parent_children(balanced(PARENT), fetcher=lambda _: response("<html>36 objekt</html>"))
    assert js["parents"][0]["child_extraction_status"] == "NO_NATIVE_ITEM_ANCHORS_FOUND_UNVERIFIED"


def test_read_limit_does_not_skip_as_zero_inventory():
    other = "https://psauction.se/auction/69254/partier-med-slippers"
    result = extract_parent_children(balanced(PARENT, other), limit=1,
                                     fetcher=lambda _: response("<html>javascript</html>"))
    assert result["counts"]["parents_total"] == 2
    assert result["counts"]["parents_attempted"] == 1
    assert result["parents"][1]["child_extraction_status"] == "NOT_CHECKED_BOUNDED_LIMIT"
    with pytest.raises(ValueError):
        extract_parent_children(balanced(PARENT), limit=MAX_PARENT_READS + 1)


def test_invalid_parent_cannot_trigger_fetch_and_duplicates_across_parents_suppressed():
    invalid = "https://psauction.se.evil.test/auction/69239/fake"
    result = extract_parent_children(balanced(invalid), fetcher=lambda _: pytest.fail("never fetch invalid"))
    assert result["counts"]["parents_attempted"] == 0
    assert result["parents"][0]["child_extraction_status"] == "INVALID_PARENT_URL_NOT_FETCHED"
    other = "https://psauction.se/auction/69254/partier-med-slippers"
    result = extract_parent_children(balanced(PARENT, other), fetcher=lambda url: response(
        f'<a href="{ITEM}">12 jackor</a>', final=url))
    assert result["counts"]["parents_attempted"] == 2
    assert result["counts"]["child_links_extracted_unverified"] == 1
    assert result["parents"][1]["child_listings_extracted"] is False
