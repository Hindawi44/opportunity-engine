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
