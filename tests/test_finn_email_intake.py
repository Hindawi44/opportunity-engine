import json

import pytest

from opportunity_engine.discovery.finn_email_intake import (
    FinnEmailMessage,
    collect_finn_saved_search_messages,
    message_from_rfc822,
    parse_finn_saved_search_message,
    run_finn_email_intake,
    write_finn_email_intake_artifacts,
)

NOW = "2026-07-28T12:00:00+00:00"
TRACKING_URL = (
    "https://click.mailsvc.finn.no/CL0/"
    "https:%2F%2Fwww.finn.no%2F468124077%3FfinnMail=agent"
    "%26aur_so=aurora%26aur_me=email%26aur_ca=search-emailsender"
    "%26stored-id=12345678/2/example/message/signature"
)
DIRECT_URL = (
    "https://www.finn.no/468124077?finnMail=agent"
    "&aur_so=aurora&aur_me=email&stored-id=12345678"
)


def alert_message(body, **overrides):
    values = {
        "sender": "FINN <agent@finn.no>",
        "subject": "Nye annonser: restlager klær og klesparti selges",
        "body": body,
        "received_at": NOW,
        "message_id": "<sanitized-finn-alert@example.test>",
    }
    values.update(overrides)
    return FinnEmailMessage(**values)


def test_parses_tracking_and_direct_links_without_following_controls():
    message = alert_message(
        "Hei!\n\n"
        f"[Restlager fra norsk klesmerke – ca. 1000 plagg]({TRACKING_URL})\n\n"
        "1 kr Mysen\n\nSend melding\n\n"
        f"Flere detaljer: {DIRECT_URL}\n\n"
        "[Stopp e-postvarsling]"
        "(https://click.mailsvc.finn.no/CL0/"
        "https:%2F%2Fwww.finn.no%2Fsearch%2FremoveEmailNotifications"
        "%3Fhash=secret/1/example)"
    )

    leads = parse_finn_saved_search_message(message)

    assert len(leads) == 1
    assert leads[0].listing_id == "468124077"
    assert leads[0].url == "https://www.finn.no/468124077"
    assert leads[0].title.startswith("Restlager fra norsk klesmerke")
    assert leads[0].advertised_price_nok == 1
    assert leads[0].advertised_location == "Mysen"
    assert leads[0].symbolic_price_detected is True


def test_rejects_non_finn_sender_and_non_alert_subject():
    with pytest.raises(ValueError, match="sender"):
        parse_finn_saved_search_message(alert_message(
            f"[Klesparti]({DIRECT_URL})",
            sender="attacker@example.test",
        ))
    with pytest.raises(ValueError, match="subject"):
        parse_finn_saved_search_message(alert_message(
            f"[Klesparti]({DIRECT_URL})",
            subject="Kvittering fra FINN",
        ))
    with pytest.raises(ValueError, match="no stable FINN advert"):
        parse_finn_saved_search_message(alert_message(
            "[Endre søket](https://www.finn.no/saved-searches?edit=123)"
        ))


def test_rfc822_plain_text_message_is_decoded_and_parsed():
    raw = (
        "From: FINN <agent@finn.no>\n"
        "To: operator@example.test\n"
        "Subject: Nye annonser: restlager klær selges\n"
        "Date: Tue, 28 Jul 2026 12:00:00 +0000\n"
        "Message-ID: <fixture@example.test>\n"
        "Content-Type: text/plain; charset=UTF-8\n\n"
        "Restlager fra norsk klesmerke\n"
        "Privat, Mysen    50 000 kr\n"
        f"Flere detaljer: {DIRECT_URL}\n"
    ).encode()

    message = message_from_rfc822(raw)
    leads = parse_finn_saved_search_message(message)

    assert leads[0].title == "Restlager fra norsk klesmerke"
    assert leads[0].advertised_price_nok == 50000
    assert leads[0].advertised_location == "Mysen"


def test_email_lead_stays_unverified_and_analysis_blocked():
    collection = collect_finn_saved_search_messages(
        [alert_message(
            f"[Restlager klær – 1000 plagg selges samlet]({TRACKING_URL})\n\n"
            "1 kr Mysen\n\nSend melding"
        )],
        ingested_at=NOW,
    )

    result = run_finn_email_intake(collection)

    report = result["search_run_report"]
    assert report["collection_mode"] == "FINN_SAVED_SEARCH_EMAIL"
    assert report["network_pages_visited"] == 0
    assert report["links_followed"] == 0
    assert report["email_leads_extracted"] == 1
    assert report["analysis_eligible_count"] == 0

    candidate = result["discovery_top5"][0]
    assert candidate["opportunity_state"] == "STRONG_LEAD_REQUIRES_VERIFICATION"
    assert candidate["listing_status"] == "UNKNOWN"
    assert candidate["analysis_eligible"] is False
    assert candidate["price_nok"] is None
    assert candidate["location"] is None
    assert candidate["source_capture"][0]["advertised_price_nok"] == 1
    assert candidate["source_capture"][0]["advertised_location"] == "Mysen"
    assert candidate["source_capture"][0]["commercial_values_verified"] is False
    assert candidate["source_capture"][0]["page_opened"] is False


def test_non_clothing_saved_search_does_not_create_top_opportunity():
    car_url = (
        "https://click.mailsvc.finn.no/CL0/"
        "https:%2F%2Fwww.finn.no%2F471074354%3FfinnMail=agent"
        "%26stored-id=59614174/2/example"
    )
    collection = collect_finn_saved_search_messages([
        alert_message(
            f"[Toyota Yaris]({car_url})\n\n66 942 kr Orkanger\n\nPrivat",
            subject=(
                "Nye annonser: Biler til salgs - Bruktbil til salgs, "
                "Opptil 181 000 km"
            ),
        )
    ])

    result = run_finn_email_intake(collection)

    assert result["search_run_report"]["email_leads_extracted"] == 1
    assert result["search_run_report"]["top5_count"] == 0
    assert result["search_run_report"]["analysis_eligible_count"] == 0
    assert result["discovery_top5"] == []


def test_digest_associates_each_advert_with_its_nearest_price():
    second_url = (
        "https://click.mailsvc.finn.no/CL0/"
        "https:%2F%2Fwww.finn.no%2F468124078%3FfinnMail=agent"
        "%26stored-id=12345678/2/example"
    )
    leads = parse_finn_saved_search_message(alert_message(
        f"[Første restlager klær selges]({TRACKING_URL})\n\n"
        "10 000 kr Oslo\n\n"
        f"[Andre klesparti selges samlet]({second_url})\n\n"
        "25 000 kr Bergen"
    ))

    assert [lead.advertised_price_nok for lead in leads] == [10000, 25000]
    assert [lead.advertised_location for lead in leads] == ["Oslo", "Bergen"]


def test_collection_deduplicates_ids_and_records_rejected_messages():
    valid = alert_message(f"[Restlager klær selges]({DIRECT_URL})")
    duplicate = alert_message(
        f"[Samme annonse]({TRACKING_URL})",
        message_id="<duplicate@example.test>",
    )
    rejected = alert_message(
        f"[Restlager klær]({DIRECT_URL})",
        sender="not-finn@example.test",
        message_id="<rejected@example.test>",
    )

    collection = collect_finn_saved_search_messages([
        valid,
        duplicate,
        rejected,
    ])

    assert collection.messages_received == 3
    assert collection.messages_accepted == 2
    assert len(collection.leads) == 1
    assert len(collection.rejected_messages) == 1
    assert "message_fingerprint" in collection.rejected_messages[0]


def test_artifact_is_sanitized_and_preserves_existing_discovery_outputs(tmp_path):
    secret_message_id = "<private-mailbox-id@example.test>"
    private_body_marker = "PRIVATE-BODY-MARKER"
    collection = collect_finn_saved_search_messages([
        alert_message(
            f"[Restlager klær selges]({DIRECT_URL}) {private_body_marker}",
            message_id=secret_message_id,
        )
    ])
    result = run_finn_email_intake(collection)

    paths = write_finn_email_intake_artifacts(result, collection, tmp_path)
    raw_text = paths["finn_email_intake"].read_text()
    raw = json.loads(raw_text)

    assert raw["network_pages_visited"] == 0
    assert raw["links_followed"] == 0
    assert secret_message_id not in raw_text
    assert private_body_marker not in raw_text
    assert paths["search_run_report"].exists()
    assert paths["all_discovered_candidates"].exists()
    assert paths["discovery_top5"].exists()
    assert paths["operator_summary"].exists()
