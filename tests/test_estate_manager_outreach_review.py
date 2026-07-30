import json
from pathlib import Path

import pytest

from opportunity_engine.discovery.estate_manager_outreach_review import (
    CONTACT_STATUS,
    DRAFT_STATUS,
    OUTREACH_SCHEMA_VERSION,
    build_outreach_review,
    write_outreach_review_artifacts,
)
from opportunity_engine.discovery.pre_market_case_tracker import REGISTRY_SCHEMA_VERSION


def _registry() -> dict:
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "captured_at": "2026-07-30T12:00:00+00:00",
        "cases": [
            {
                "case_id": "estate:938018014",
                "estate_orgnr": "938018014",
                "estate_name": "MENSWEAR NORGE AS KONKURSBO",
                "debtor_orgnr": "986425284",
                "debtor_name": "MENSWEAR NORGE AS",
                "opened_date": "2026-07-01",
                "municipality": "OSLO",
                "estate_manager_name": "Adv. Henrik Schumann Sager",
                "estate_manager_identified": True,
                "state": "NO_PUBLIC_SALE_CHANNEL_FOUND",
                "first_seen_at": "2026-07-30T12:00:00+00:00",
                "last_checked_at": "2026-07-30T12:00:00+00:00",
                "last_changed_at": "2026-07-30T12:00:00+00:00",
                "scan_complete": True,
                "sale_listing_candidate_urls": [],
                "liquidation_channel_candidate_urls": [],
                "public_sale_found": False,
                "inventory_sale_verified": False,
                "liquidation_channel_verified": False,
                "source_reports": [],
            },
            {
                "case_id": "estate:938022038",
                "estate_orgnr": "938022038",
                "estate_name": "KEEPFIT AS KONKURSBO",
                "debtor_orgnr": "913318625",
                "debtor_name": "KEEPFIT AS",
                "opened_date": "2026-07-01",
                "municipality": "BJØRNAFJORDEN",
                "estate_manager_name": "Adv. Rune Stavenes",
                "estate_manager_identified": True,
                "state": "SALE_LISTING_CANDIDATE_REQUIRES_PAGE_VERIFICATION",
                "first_seen_at": "2026-07-30T12:00:00+00:00",
                "last_checked_at": "2026-07-30T12:00:00+00:00",
                "last_changed_at": "2026-07-30T12:00:00+00:00",
                "scan_complete": True,
                "sale_listing_candidate_urls": ["https://example.test/sale"],
                "liquidation_channel_candidate_urls": [],
                "public_sale_found": False,
                "inventory_sale_verified": False,
                "liquidation_channel_verified": False,
                "source_reports": [],
            },
        ],
    }


def _actions() -> list[dict]:
    return [
        {
            "case_id": "estate:938018014",
            "debtor_name": "MENSWEAR NORGE AS",
            "state": "NO_PUBLIC_SALE_CHANNEL_FOUND",
            "recommended_action": "ASK_ESTATE_MANAGER_FOR_SALE_CHANNEL",
            "reason": "No public channel found.",
            "priority": "MEDIUM",
            "human_approval_required": True,
            "automatic_email": False,
        },
        {
            "case_id": "estate:938022038",
            "debtor_name": "KEEPFIT AS",
            "state": "SALE_LISTING_CANDIDATE_REQUIRES_PAGE_VERIFICATION",
            "recommended_action": "VERIFY_PUBLIC_SALE_PAGE",
            "reason": "Candidate requires verification.",
            "priority": "HIGH",
        },
    ]


def test_builds_only_human_review_packet_for_eligible_action() -> None:
    result = build_outreach_review(
        _registry(),
        _actions(),
        captured_at="2026-07-30T13:00:00+00:00",
    )

    assert result.eligible_action_count == 1
    assert len(result.packets) == 1
    packet = result.packets[0].to_dict()
    assert packet["packet_id"] == "outreach:938018014"
    assert packet["draft_status"] == DRAFT_STATUS
    assert packet["recipient_status"] == CONTACT_STATUS
    assert packet["recipient_email"] is None
    assert "MENSWEAR NORGE AS" in packet["subject_nb"]
    assert "986425284" in packet["body_nb"]
    assert "938018014" in packet["body_nb"]
    assert "Namsos Skredderhus" in packet["body_nb"]
    assert packet["binding_offer"] is False
    assert packet["human_approval_required"] is True
    assert packet["automatic_contact_lookup"] is False
    assert packet["automatic_email"] is False
    assert packet["automatic_contact"] is False


def test_same_inputs_produce_stable_packet_identity() -> None:
    first = build_outreach_review(
        _registry(),
        _actions(),
        captured_at="2026-07-30T13:00:00+00:00",
    )
    second = build_outreach_review(
        _registry(),
        _actions(),
        captured_at="2026-07-31T13:00:00+00:00",
    )

    assert first.packets[0].packet_id == second.packets[0].packet_id
    assert first.packets[0].to_dict()["subject_nb"] == second.packets[0].to_dict()[
        "subject_nb"
    ]
    assert first.packets[0].to_dict()["body_nb"] == second.packets[0].to_dict()[
        "body_nb"
    ]


def test_skips_action_when_case_state_is_not_eligible() -> None:
    actions = [
        {
            "case_id": "estate:938022038",
            "recommended_action": "ASK_ESTATE_MANAGER_FOR_SALE_CHANNEL",
            "priority": "MEDIUM",
        }
    ]
    result = build_outreach_review(_registry(), actions)

    assert result.eligible_action_count == 1
    assert result.packets == ()
    assert result.skipped == (
        {
            "case_id": "estate:938022038",
            "reason": "CASE_STATE_NOT_ELIGIBLE",
        },
    )


def test_skips_missing_case_without_guessing_identity() -> None:
    actions = [
        {
            "case_id": "estate:999999999",
            "recommended_action": "ASK_ESTATE_MANAGER_FOR_SALE_CHANNEL",
            "priority": "MEDIUM",
        }
    ]
    result = build_outreach_review(_registry(), actions)

    assert result.packets == ()
    assert result.skipped[0]["reason"] == "CASE_NOT_FOUND"


def test_rejects_wrong_registry_schema() -> None:
    registry = _registry()
    registry["schema_version"] = "unknown"
    with pytest.raises(ValueError, match="unsupported"):
        build_outreach_review(registry, _actions())


def test_writes_queue_drafts_and_summary(tmp_path: Path) -> None:
    result = build_outreach_review(
        _registry(),
        _actions(),
        captured_at="2026-07-30T13:00:00+00:00",
    )
    paths = write_outreach_review_artifacts(result, tmp_path)

    payload = json.loads(paths["queue"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == OUTREACH_SCHEMA_VERSION
    assert payload["packet_count"] == 1
    assert payload["automatic_email"] is False
    drafts = paths["drafts"].read_text(encoding="utf-8")
    assert "Human review is required" in drafts
    assert "Forespørsel om varelager" in drafts
    summary = paths["summary"].read_text(encoding="utf-8")
    assert "Draft packets created: 1" in summary
    assert "Automatic contact lookup/email/contact: false" in summary
