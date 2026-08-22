from __future__ import annotations

from opportunity_engine.stocklear_access_stability import (
    classify_access_sample,
    summarize_access_stability,
)


def test_public_lot_page_with_login_wall_is_usable_partial_access() -> None:
    sample = classify_access_sample(
        url="https://joblot.stocklear.eu/auction/21746/",
        status_code=200,
        final_url="https://joblot.stocklear.eu/auction/21746/",
        body="""
        Lot of 699 units of assorted products
        Number of pallets Equivalent to 5 standard pallets
        Quality Functional customer returns
        Last bid 1 400,00 EUR
        Log in or register to find out the number of pallets, location and important information about this lot.
        """,
    )

    assert sample["access_status"] == "PUBLIC_PARTIAL_LOGIN_WALL"
    assert sample["public_opportunity_markers"] is True
    assert sample["login_wall_present"] is True
    assert sample["blocked"] is False
    assert sample["rate_limited"] is False
    assert sample["challenge_detected"] is False


def test_403_is_classified_as_blocked() -> None:
    sample = classify_access_sample(
        url="https://joblot.stocklear.eu/auction/21746/",
        status_code=403,
        final_url="https://joblot.stocklear.eu/auction/21746/",
        body="Forbidden",
    )
    assert sample["access_status"] == "BLOCKED_403"
    assert sample["blocked"] is True


def test_429_is_classified_as_rate_limited() -> None:
    sample = classify_access_sample(
        url="https://joblot.stocklear.eu/auction/21746/",
        status_code=429,
        final_url="https://joblot.stocklear.eu/auction/21746/",
        body="Too many requests",
    )
    assert sample["access_status"] == "RATE_LIMITED_429"
    assert sample["rate_limited"] is True


def test_challenge_page_is_not_accepted_as_public_access() -> None:
    sample = classify_access_sample(
        url="https://joblot.stocklear.eu/auction/21746/",
        status_code=200,
        final_url="https://joblot.stocklear.eu/auction/21746/",
        body="Checking your browser before accessing. Verify you are human. cf-chl-captcha",
    )
    assert sample["access_status"] == "CHALLENGE_PAGE"
    assert sample["challenge_detected"] is True
    assert sample["public_opportunity_markers"] is False


def test_same_domain_login_redirect_is_login_required_not_stable_public() -> None:
    sample = classify_access_sample(
        url="https://joblot.stocklear.eu/auction/21746/",
        status_code=200,
        final_url="https://joblot.stocklear.eu/login",
        body="Log in to your Stocklear account",
    )
    assert sample["access_status"] == "LOGIN_REDIRECT"
    assert sample["login_redirect"] is True


def test_html_drift_is_visible_when_200_page_loses_opportunity_markers() -> None:
    sample = classify_access_sample(
        url="https://joblot.stocklear.eu/auction/21746/",
        status_code=200,
        final_url="https://joblot.stocklear.eu/auction/21746/",
        body="Welcome to our marketplace",
    )
    assert sample["access_status"] == "HTML_DRIFT_OR_EMPTY_PUBLIC_DATA"
    assert sample["html_drift_suspected"] is True


def test_stability_summary_passes_when_all_samples_are_public_and_no_blocks() -> None:
    samples = [
        classify_access_sample(
            url=f"https://joblot.stocklear.eu/auction/{21740 + index}/",
            status_code=200,
            final_url=f"https://joblot.stocklear.eu/auction/{21740 + index}/",
            body="Lot of 500 units Number of pallets 5 Quality Functional customer returns Starting price 1000 EUR Log in or register",
        )
        for index in range(5)
    ]
    report = summarize_access_stability(samples)

    assert report["sample_count"] == 5
    assert report["usable_public_sample_count"] == 5
    assert report["usable_public_ratio"] == 1.0
    assert report["blocked_count"] == 0
    assert report["rate_limited_count"] == 0
    assert report["challenge_count"] == 0
    assert report["verdict"] == "PUBLIC_ACCESS_STABLE_PARTIAL"
    assert report["production_promotion_recommended"] is False


def test_any_block_or_challenge_prevents_stable_verdict() -> None:
    good = classify_access_sample(
        url="https://joblot.stocklear.eu/auction/21746/",
        status_code=200,
        final_url="https://joblot.stocklear.eu/auction/21746/",
        body="Lot of 699 units Number of pallets 5 Quality Functional customer returns Last bid 1400 EUR",
    )
    blocked = classify_access_sample(
        url="https://joblot.stocklear.eu/auction/21747/",
        status_code=403,
        final_url="https://joblot.stocklear.eu/auction/21747/",
        body="Forbidden",
    )
    report = summarize_access_stability([good, blocked])

    assert report["verdict"] == "ACCESS_UNSTABLE_OR_PROTECTED"
    assert report["production_promotion_recommended"] is False


def test_access_test_never_authorizes_production_or_bypass_behavior() -> None:
    report = summarize_access_stability([])
    assert report["production_mutation"] is False
    assert report["automatic_promotion"] is False
    assert report["authentication_attempted"] is False
    assert report["captcha_bypass_attempted"] is False
    assert report["proxy_rotation_attempted"] is False
