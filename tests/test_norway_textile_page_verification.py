import pytest

from opportunity_engine.discovery.clothing_inventory_search import (
    ACTIVE,
    ENDED,
    ITEM_LISTING,
    SOURCE_CHANNEL,
    PageVerification,
)
from opportunity_engine.discovery.norway_textile_page_verification import (
    NORWAY_TEXTILE_PAGE_VERIFICATION_CATEGORIES,
    evaluate_norway_textile_page_verification,
)
from opportunity_engine.discovery.textile_taxonomy import OpportunityCategory


def _verified_page(**overrides: object) -> PageVerification:
    values: dict[str, object] = {
        "url": "https://example.invalid/listing/12345",
        "title": "Industrisymaskiner fra systue selges",
        "text": "Aktiv annonse med industrisymaskiner til salgs.",
        "listing_status": ACTIVE,
        "page_role": ITEM_LISTING,
        "opportunity_identity": "url-id:12345",
        "identity_stable": True,
        "clothing_inventory_evidence": True,
        "sale_evidence": True,
        "verified": True,
    }
    values.update(overrides)
    return PageVerification(**values)


def test_policy_covers_every_textile_taxonomy_category() -> None:
    expected = {category.value for category in OpportunityCategory}
    assert NORWAY_TEXTILE_PAGE_VERIFICATION_CATEGORIES == expected

    for category in expected:
        decision = evaluate_norway_textile_page_verification(
            _verified_page(),
            category=category,
        )
        assert decision.accepted is True
        assert decision.category == category


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"verified": False, "error": "fetch failed"}, "fetch failed"),
        ({"page_role": SOURCE_CHANNEL}, "not a specific item listing"),
        ({"listing_status": ENDED}, "not verified active"),
        ({"identity_stable": False}, "identity is not stable"),
        ({"opportunity_identity": None}, "identity is not stable"),
        ({"clothing_inventory_evidence": False}, "lacks textile or sewing asset evidence"),
        ({"sale_evidence": False}, "lacks public sale evidence"),
    ],
)
def test_policy_fails_closed_when_existing_safety_gate_is_missing(
    overrides: dict[str, object],
    reason: str,
) -> None:
    decision = evaluate_norway_textile_page_verification(
        _verified_page(**overrides),
        category=OpportunityCategory.SEWING_MACHINERY.value,
    )

    assert decision.accepted is False
    assert reason in decision.reason


def test_policy_rejects_unknown_category() -> None:
    decision = evaluate_norway_textile_page_verification(
        _verified_page(),
        category="GENERIC_WAREHOUSE_INVENTORY",
    )

    assert decision.accepted is False
    assert decision.reason == "unsupported textile taxonomy category"
