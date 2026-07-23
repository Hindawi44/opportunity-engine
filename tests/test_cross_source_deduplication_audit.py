from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_cross_source_deduplication_audit.py"
SPEC = spec_from_file_location("cross_source_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def item(source: str, record_id: str, title: str, url: str, city: str | None, price: float | None) -> dict:
    return {
        "source": source,
        "lead_id": record_id,
        "title": title,
        "url": url,
        "city": city,
        "asking_price_nok": price,
    }


def test_exact_url_ignores_tracking_and_scheme() -> None:
    left = item("Auksjonen.no", "a-1", "Butikkinnredning", "http://example.no/lot/42?utm_source=x", "Oslo", 10000)
    right = item("Politiet.no", "p-1", "Annen tittel", "https://example.no/lot/42", None, None)
    assert MODULE.classify(left, right) == "EXACT_URL"


def test_strong_fingerprint_requires_city_price_and_high_title_similarity() -> None:
    left = item("Auksjonen.no", "a-1", "Komplett butikkinnredning med hyller", "https://a.no/1", "Trondheim", 10000)
    right = item("Konkurs.app", "k-1", "Komplett butikkinnredning og hyller", "https://k.no/9", "Trondheim", 10200)
    assert MODULE.classify(left, right) == "STRONG_FINGERPRINT"


def test_weak_title_similarity_never_auto_merges_distinct_records() -> None:
    left = item("Auksjonen.no", "a-1", "Butikkinnredning med hyller", "https://a.no/1", "Trondheim", 10000)
    right = item("Konkurs.app", "k-1", "Kontorstoler og skrivebord", "https://k.no/9", "Trondheim", 10000)
    assert MODULE.classify(left, right) is None


def test_possible_duplicate_is_review_only() -> None:
    left = item("Auksjonen.no", "a-1", "Komplett butikkinnredning Kristiansand", "https://a.no/1", "Kristiansand", 10000)
    right = item("Politiet.no", "p-1", "Butikkinnredning fra butikk Kristiansand", "https://p.no/2", "Kristiansand", None)
    payload = MODULE.build_audit([("one", [left]), ("two", [right])])
    assert payload["automatic_merge_pair_count"] == 0
    assert payload["possible_duplicate_review_count"] == 1
    assert payload["matches"][0]["match_type"] == "POSSIBLE_DUPLICATE_REVIEW"
    assert payload["matches"][0]["automatic_merge"] is False


def test_audit_preserves_source_names_and_record_ids() -> None:
    left = item("Auksjonen.no", "a-1", "Butikkinnredning", "https://example.no/lot/42", "Oslo", 10000)
    right = item("Konkurs.app", "k-1", "Butikkinnredning", "https://example.no/lot/42", "Oslo", 10000)
    payload = MODULE.build_audit([("one", [left]), ("two", [right])])
    match = payload["matches"][0]
    assert match["source_names"] == ["Auksjonen.no", "Konkurs.app"]
    assert match["source_record_ids"] == ["a-1", "k-1"]


def test_audit_infers_official_source_from_url_and_excludes_brave_and_unknown() -> None:
    records = [
        item("Brave Search", "a-1", "Auksjon", "https://www.auksjonen.no/auksjon/1", "Oslo", 1000),
        item("Brave Search", "k-1", "Konkurs", "https://konkurs.app/company/1", "Oslo", None),
        item("Politiet.no", "p-1", "Tvangssalg", "https://www.politiet.no/arrangement/1", "Oslo", None),
        item("Brave Search", "b-1", "Irrelevant", "https://example.com/item/1", "Oslo", 1000),
        item("", "u-1", "Unknown", "", "Oslo", 1000),
    ]
    payload = MODULE.build_audit([("mixed", records)])

    assert payload["source_names"] == ["Auksjonen.no", "Konkurs.app", "Politiet.no"]
    assert payload["observed_source_names"] == ["Auksjonen.no", "Konkurs.app", "Politiet.no"]
    assert payload["source_record_counts"] == {
        "Auksjonen.no": 1,
        "Konkurs.app": 1,
        "Politiet.no": 1,
    }
    assert payload["ignored_non_official_record_count"] == 2
    assert "Brave Search" not in payload["source_names"]
    assert "UNKNOWN" not in payload["source_names"]


def test_report_always_contains_all_three_official_sources() -> None:
    payload = MODULE.build_audit([])
    assert payload["source_names"] == list(MODULE.OFFICIAL_SOURCES)
    assert MODULE.validate_official_sources(payload) is True


def test_validation_fails_when_an_official_source_is_missing() -> None:
    payload = {"source_names": ["Auksjonen.no", "Politiet.no"]}
    assert MODULE.validate_official_sources(payload) is False


def test_konkurs_channel_records_reach_audit_and_reconcile_with_funnel() -> None:
    konkurs_records = [
        item("Konkurs.app", "k-1", "ANNA J AS", "https://konkurs.app/konkursbo/1", "Namsos", None),
        item("Konkurs.app", "k-2", "CEBRA AS", "https://konkurs.app/konkursbo/2", "Ullensaker", None),
    ]
    payload = MODULE.build_audit(
        [("bankruptcy_leads", konkurs_records)],
        funnel_counts={"Auksjonen.no": 0, "Konkurs.app": 2, "Politiet.no": 0},
    )
    assert payload["source_record_counts"]["Konkurs.app"] == 2
    assert payload["source_funnel_reconciliation"]["Konkurs.app"] == {
        "fetched_count": 2,
        "audit_record_count": 2,
        "difference": 0,
        "exclusion_reasons": [],
        "status": "RECONCILED",
    }
    assert MODULE.validate_funnel_coverage(payload) is True


def test_fetched_source_cannot_disappear_without_exclusion_reason() -> None:
    payload = MODULE.build_audit(
        [],
        funnel_counts={"Auksjonen.no": 0, "Konkurs.app": 3, "Politiet.no": 0},
    )
    row = payload["source_funnel_reconciliation"]["Konkurs.app"]
    assert row["audit_record_count"] == 0
    assert row["exclusion_reasons"]
    assert MODULE.validate_funnel_coverage(payload) is True

    row["exclusion_reasons"] = []
    assert MODULE.validate_funnel_coverage(payload) is False


def test_duplicate_channel_input_is_counted_once() -> None:
    record = item("Konkurs.app", "k-1", "ANNA J AS", "https://konkurs.app/konkursbo/1", "Namsos", None)
    payload = MODULE.build_audit([
        ("discovery", [record]),
        ("bankruptcy_leads", [record]),
    ])
    assert payload["source_record_counts"]["Konkurs.app"] == 1
