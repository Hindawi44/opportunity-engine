import json
from pathlib import Path

from opportunity_engine.discovery.vareauksjonen_public_adapter import (
    BASE_URL,
    PUBLIC_PAGE_SPECS,
    ROBOTS_URL,
    VareauksjonenBrowseCandidate,
    VareauksjonenPublicCollector,
    is_approved_listing_url,
    is_approved_public_page,
    parse_browse_candidates,
    parse_listing_detail,
    write_vareauksjonen_artifacts,
)

ROBOTS = """User-agent: *
Crawl-delay: 10
Disallow: /Browse/*/*ViewStyle
Disallow: /Browse?ViewStyle
Disallow: /Account/
"""


def browse_html(*rows):
    anchors = []
    for url, title in rows:
        anchors.extend(
            (
                f'<a href="{url}"><img alt=""></a>',
                f'<a href="{url}">{title}</a>',
                f'<a href="{url}">Kjøp nå</a>',
            )
        )
    return f"""
    <html><body>
      <form action="/Browse" method="get">
        <input name="StatusFilter" value="active_only">
      </form>
      {''.join(anchors)}
    </body></html>
    """


def detail_html(
    *,
    title="Vareparti med 120 herreklær",
    description="Restlager fra klesbutikk med jakker, bukser og skjorter selges samlet.",
    listing_id="200001",
    listing_type="Auction",
    quantity="120",
    status="Aktiv",
    action="Send bud",
    price="12 500",
    location="Oslo",
):
    return f"""
    <html><head>
      <meta property="og:title" content="{title}">
      <meta property="og:description" content="{description}">
      <meta property="og:image" content="https://images.example/item.jpg">
      <meta name="keywords" content="Klær">
    </head><body>
      <h1>{title} Vis overvåkningsliste</h1>
      <div>{status}</div>
      <div>Pris <span>{price}</span> kr</div>
      <div>{location}, NO</div>
      <div>Beskrivelse</div><p>{description}</p>
      <input type="hidden" name="ListingID" value="{listing_id}">
      <input type="hidden" name="ListingType" value="{listing_type}">
      <input type="hidden" name="Quantity" value="{quantity}">
      <input type="submit" value="{action}">
    </body></html>
    """


def candidate(title="Vareparti med 120 herreklær"):
    return VareauksjonenBrowseCandidate(
        listing_id=200001,
        title=title,
        url=f"{BASE_URL}/Listing/Details/200001/Vareparti-med-herreklaer",
        source_pages=(PUBLIC_PAGE_SPECS[0][0],),
        source_roles=("ALL_ACTIVE",),
    )


def test_approved_scope_is_narrow():
    assert is_approved_public_page(PUBLIC_PAGE_SPECS[0][0])
    assert not is_approved_public_page(f"{BASE_URL}/Search")
    assert is_approved_listing_url(candidate().url)
    assert not is_approved_listing_url("https://evil.example/Listing/Details/200001/x")
    assert not is_approved_listing_url(f"{BASE_URL}/Account/LogOn")


def test_all_active_page_keeps_clothing_titles_and_rejects_unrelated_items():
    clothing_url = "/Listing/Details/200001/Vareparti-med-herreklaer"
    grill_url = "/Listing/Details/200002/Gassgrill"
    results = parse_browse_candidates(
        browse_html(
            (clothing_url, "Vareparti med 120 herreklær"),
            (grill_url, "Gassgrill for innebygging"),
        ),
        page_url=PUBLIC_PAGE_SPECS[0][0],
        page_role="ALL_ACTIVE",
    )

    assert len(results) == 1
    assert results[0].listing_id == 200001
    assert results[0].title == "Vareparti med 120 herreklær"
    assert results[0].url == f"{BASE_URL}{clothing_url}"


def test_clothing_category_accepts_generic_title_for_detail_verification():
    results = parse_browse_candidates(
        browse_html(("/Listing/Details/200003/Objekt-12", "Objekt 12")),
        page_url=PUBLIC_PAGE_SPECS[1][0],
        page_role="CLOTHING_CATEGORY",
    )

    assert len(results) == 1
    assert results[0].title == "Objekt 12"


def test_inventory_category_requires_lot_or_clothing_signal_in_title():
    results = parse_browse_candidates(
        browse_html(
            ("/Listing/Details/200004/Lagerparti", "Varelager fra butikk"),
            ("/Listing/Details/200005/Maskin", "Metallmaskin"),
        ),
        page_url=PUBLIC_PAGE_SPECS[2][0],
        page_role="INVENTORY_BANKRUPTCY_CATEGORY",
    )

    assert [item.listing_id for item in results] == [200004]


def test_active_clothing_lot_is_commercially_eligible():
    listing = parse_listing_detail(detail_html(), candidate())
    payload = listing.to_dict()

    assert listing.title == "Vareparti med 120 herreklær"
    assert listing.listing_status == "ACTIVE"
    assert listing.listing_type == "Auction"
    assert listing.price_nok == 12500.0
    assert listing.quantity == 120
    assert listing.location == "Oslo"
    assert listing.clothing_signal is True
    assert listing.inventory_lot_signal is True
    assert payload["top5_eligible"] is True
    assert payload["automatic_bid"] is False
    assert payload["automatic_purchase_decision"] is False


def test_individual_clothing_item_stays_out_of_top5():
    listing = parse_listing_detail(
        detail_html(
            title="Jakke størrelse XL",
            description="En jakke i størrelse XL.",
            quantity="1",
            price="500",
        ),
        candidate("Jakke størrelse XL"),
    )

    assert listing.listing_status == "ACTIVE"
    assert listing.clothing_signal is True
    assert listing.inventory_lot_signal is False
    assert listing.to_dict()["top5_eligible"] is False


def test_completed_listing_is_rejected_even_if_action_text_exists():
    listing = parse_listing_detail(
        detail_html(status="Fullført", action="Send bud"),
        candidate(),
    )

    assert listing.listing_status == "NOT_ACTIVE_OR_UNVERIFIED"
    assert listing.to_dict()["top5_eligible"] is False


def test_collector_respects_crawl_delay_deduplicates_and_reads_only_candidates():
    calls = []
    sleeps = []
    item_url = candidate().url

    pages = {
        ROBOTS_URL: ROBOTS,
        PUBLIC_PAGE_SPECS[0][0]: browse_html(
            ("/Listing/Details/200001/Vareparti-med-herreklaer", "Vareparti med 120 herreklær"),
            ("/Listing/Details/200099/Gassgrill", "Gassgrill"),
        ),
        PUBLIC_PAGE_SPECS[1][0]: browse_html(
            ("/Listing/Details/200001/Vareparti-med-herreklaer", "Vareparti med 120 herreklær")
        ),
        PUBLIC_PAGE_SPECS[2][0]: browse_html(),
        item_url: detail_html(),
    }

    def fetch_text(url):
        calls.append(url)
        return pages[url]

    collection = VareauksjonenPublicCollector(
        fetch_text=fetch_text,
        sleep_fn=sleeps.append,
    ).collect()

    assert calls == [
        ROBOTS_URL,
        PUBLIC_PAGE_SPECS[0][0],
        PUBLIC_PAGE_SPECS[1][0],
        PUBLIC_PAGE_SPECS[2][0],
        item_url,
    ]
    assert sleeps == [10.0, 10.0, 10.0, 10.0]
    assert len(collection.candidates) == 1
    assert collection.candidates[0].source_roles == (
        "ALL_ACTIVE",
        "CLOTHING_CATEGORY",
    )
    assert len(collection.inventory_opportunities) == 1
    assert collection.scan_complete is True
    assert collection.errors == ()


def test_empty_live_market_is_successful_and_truthful():
    pages = {
        ROBOTS_URL: ROBOTS,
        **{url: browse_html() for url, _ in PUBLIC_PAGE_SPECS},
    }
    collection = VareauksjonenPublicCollector(
        fetch_text=lambda url: pages[url],
        sleep_fn=lambda seconds: None,
    ).collect()

    assert collection.scan_complete is True
    assert collection.candidates == ()
    assert collection.listings == ()
    assert collection.inventory_opportunities == ()
    assert collection.errors == ()


def test_robots_listing_block_fails_closed_without_browse_requests():
    calls = []

    def fetch_text(url):
        calls.append(url)
        return "User-agent: *\nCrawl-delay: 10\nDisallow: /Listing/\n"

    collection = VareauksjonenPublicCollector(
        fetch_text=fetch_text,
        sleep_fn=lambda seconds: None,
    ).collect()

    assert calls == [ROBOTS_URL]
    assert collection.scan_complete is False
    assert collection.listings == ()
    assert collection.errors[0]["stage"] == "robots"


def test_artifacts_keep_individuals_separate_from_commercial_top5(tmp_path: Path):
    lot_url = candidate().url
    individual_url = f"{BASE_URL}/Listing/Details/200002/Jakke-storrelse-XL"
    pages = {
        ROBOTS_URL: ROBOTS,
        PUBLIC_PAGE_SPECS[0][0]: browse_html(
            ("/Listing/Details/200001/Vareparti-med-herreklaer", "Vareparti med 120 herreklær"),
            ("/Listing/Details/200002/Jakke-storrelse-XL", "Jakke størrelse XL"),
        ),
        PUBLIC_PAGE_SPECS[1][0]: browse_html(),
        PUBLIC_PAGE_SPECS[2][0]: browse_html(),
        lot_url: detail_html(),
        individual_url: detail_html(
            title="Jakke størrelse XL",
            description="En jakke størrelse XL.",
            listing_id="200002",
            quantity="1",
            price="500",
        ),
    }
    collection = VareauksjonenPublicCollector(
        fetch_text=lambda url: pages[url],
        sleep_fn=lambda seconds: None,
    ).collect()
    paths = write_vareauksjonen_artifacts(collection, tmp_path)

    top5 = json.loads(paths["commercial_top5"].read_text(encoding="utf-8"))
    individuals = json.loads(paths["individuals"].read_text(encoding="utf-8"))
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    summary = paths["summary"].read_text(encoding="utf-8")

    assert len(top5) == 1
    assert top5[0]["listing_id"] == 200001
    assert top5[0]["top5_eligible"] is True
    assert len(individuals) == 1
    assert individuals[0]["listing_id"] == 200002
    assert report["commercial_top5_count"] == 1
    assert "Valid inventory opportunities: 1" in summary
