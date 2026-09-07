from opportunity_engine.discovery.finn_email_intake import FinnEmailMessage
from opportunity_engine.discovery.gmail_opportunity_classification import (
    CATEGORIES,
    classify_gmail_message,
    classify_gmail_messages,
    write_gmail_classification_artifacts,
)


def _message(subject: str, body: str, sender: str = "source@example.test") -> FinnEmailMessage:
    return FinnEmailMessage(
        sender=sender,
        subject=subject,
        body=body,
        received_at="2026-09-07T08:00:00Z",
        message_id="<private-id@example.test>",
    )


def test_classifies_all_project_categories() -> None:
    fixtures = {
        "FINN_OPPORTUNITY": _message("Nye annonser", "https://www.finn.no/123", "FINN <agent@finn.no>"),
        "AUCTION_LIQUIDATION": _message("Konkursauksjon", "Klær selges samlet"),
        "SUPPLIER_STOCK": _message("Restlager", "Vareparti klær 1000 stk"),
        "PRICE_STATUS_CHANGE": _message("Solgt", "Partiet er solgt for 200 NOK"),
        "SHIPPING_LOGISTICS": _message("Frakt", "Mybring delivery quote"),
        "NEEDS_REVIEW": _message("Mulig parti", "Klær https://example.test/item"),
        "IRRELEVANT": _message("Møte", "Vanlig personlig melding"),
    }

    for expected, message in fixtures.items():
        assert classify_gmail_message(message)["category"] == expected
    assert set(fixtures) == set(CATEGORIES)


def test_extracts_only_bounded_structured_evidence() -> None:
    row = classify_gmail_message(
        _message("Restlager Norge", "1200 stk klær, 6.90 EUR https://example.test/lot")
    )

    assert row["country"] == "NO"
    assert row["advertised_quantity"] == 1200
    assert row["advertised_price"] == {"amount": 690, "currency": "EUR", "verified": False}
    assert row["urls"] == ["https://example.test/lot"]
    assert row["raw_body_stored"] is False
    assert row["message_id_stored"] is False


def test_report_deduplicates_and_never_mutates_gmail(tmp_path) -> None:
    message = _message("Restlager", "Vareparti klær")
    report = classify_gmail_messages([message, message])
    paths = write_gmail_classification_artifacts(report, tmp_path)

    assert report["message_count"] == 1
    assert report["gmail_mutations_made"] == 0
    assert report["automatic_reply"] is False
    text = paths["gmail_classification"].read_text(encoding="utf-8")
    assert "private-id" not in text
    assert "Vareparti klær" not in text
