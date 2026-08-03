from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from opportunity_engine.discovery.brreg_complete_update_window import (
    collect_brreg_complete_window_signals,
)


NOW = datetime(2026, 8, 3, 18, 0, tzinfo=timezone.utc)


def _update(
    update_id: int,
    orgnr: str,
    *,
    path: str = "/navn",
    value: object = "changed",
) -> dict:
    return {
        "oppdateringsid": update_id,
        "dato": f"2026-08-03T12:00:{update_id:02d}.000Z",
        "organisasjonsnummer": orgnr,
        "endringstype": "Endring",
        "endringer": [{"op": "replace", "path": path, "value": value}],
    }


def _page(
    number: int,
    total_pages: int,
    total_elements: int,
    updates: list[dict],
) -> dict:
    return {
        "_embedded": {"oppdaterteEnheter": updates},
        "page": {
            "number": number,
            "size": 2,
            "totalPages": total_pages,
            "totalElements": total_elements,
        },
    }


class FakeJsonGetter:
    def __init__(self, pages: dict[int, object], entities: dict[str, object]) -> None:
        self.pages = pages
        self.entities = entities
        self.urls: list[str] = []

    def __call__(self, url: str, timeout: float, headers: dict[str, str]) -> object:
        self.urls.append(url)
        parsed = urlparse(url)
        if parsed.path.endswith("/oppdateringer/enheter"):
            page = int(parse_qs(parsed.query).get("page", ["0"])[0])
            value = self.pages[page]
        else:
            orgnr = parsed.path.rsplit("/", 1)[-1]
            value = self.entities[orgnr]
        if isinstance(value, Exception):
            raise value
        return value


def _clothing_entity(orgnr: str) -> dict:
    return {
        "organisasjonsnummer": orgnr,
        "navn": "NORDIC WORKWEAR AS",
        "konkurs": True,
        "konkursdato": "2026-08-03",
        "naeringskode1": {
            "kode": "47.710",
            "beskrivelse": "Butikkhandel med klær",
        },
        "forretningsadresse": {
            "adresse": ["Arbeidsveien 1"],
            "postnummer": "7010",
            "poststed": "TRONDHEIM",
        },
    }


def test_complete_window_follows_all_pages_before_accepting_signal() -> None:
    getter = FakeJsonGetter(
        pages={
            0: _page(
                0,
                2,
                3,
                [_update(1, "111111111"), _update(2, "222222222")],
            ),
            1: _page(
                1,
                2,
                3,
                [_update(3, "999999999", path="/konkurs", value=True)],
            ),
        },
        entities={"999999999": _clothing_entity("999999999")},
    )

    report = collect_brreg_complete_window_signals(
        observed_at=NOW,
        page_size=2,
        max_pages=5,
        max_update_records=10,
        json_get=getter,
    )

    assert report["status"] == "SUCCESS"
    assert report["pages_fetched"] == 2
    assert report["retrieved_record_count"] == 3
    assert report["total_elements"] == 3
    assert report["retrieval_complete"] is True
    assert report["update_window_complete"] is True
    assert report["candidate_evaluation_complete"] is True
    assert report["next_page_available"] is False
    assert report["candidate_entity_count"] == 1
    assert report["accepted_signal_count"] == 1
    assert report["signals"][0]["related_opportunity_id"] is None
    assert "/konkurs" in report["observed_change_paths"]
    page_urls = [url for url in getter.urls if "oppdateringer/enheter" in url]
    assert "page=0" in page_urls[0]
    assert "page=1" in page_urls[1]
    assert "sort=id%2CASC" in page_urls[0]


def test_valid_zero_requires_complete_update_window() -> None:
    getter = FakeJsonGetter(
        pages={
            0: _page(
                0,
                2,
                3,
                [_update(1, "111111111"), _update(2, "222222222")],
            ),
            1: _page(1, 2, 3, [_update(3, "333333333")]),
        },
        entities={},
    )

    report = collect_brreg_complete_window_signals(
        observed_at=NOW,
        page_size=2,
        max_pages=5,
        max_update_records=10,
        json_get=getter,
    )

    assert report["status"] == "VALID_ZERO"
    assert report["retrieval_complete"] is True
    assert report["candidate_entity_count"] == 0
    assert report["entity_fetch_count"] == 0
    assert report["pages_fetched"] == 2


def test_update_record_cap_reports_partial_retrieval_not_valid_zero() -> None:
    getter = FakeJsonGetter(
        pages={
            0: _page(
                0,
                3,
                5,
                [_update(1, "111111111"), _update(2, "222222222")],
            )
        },
        entities={},
    )

    report = collect_brreg_complete_window_signals(
        observed_at=NOW,
        page_size=2,
        max_pages=5,
        max_update_records=2,
        json_get=getter,
    )

    assert report["status"] == "PARTIAL_RETRIEVAL"
    assert report["retrieved_record_count"] == 2
    assert report["retrieval_complete"] is False
    assert report["update_window_complete"] is False
    assert report["next_page_available"] is True
    assert report["completion_reason"] == "MAX_UPDATE_RECORDS_REACHED"


def test_later_page_failure_preserves_partial_truth() -> None:
    getter = FakeJsonGetter(
        pages={
            0: _page(
                0,
                2,
                3,
                [_update(1, "111111111"), _update(2, "222222222")],
            ),
            1: RuntimeError("temporary page failure"),
        },
        entities={},
    )

    report = collect_brreg_complete_window_signals(
        observed_at=NOW,
        page_size=2,
        max_pages=5,
        max_update_records=10,
        json_get=getter,
    )

    assert report["status"] == "PARTIAL_RETRIEVAL"
    assert report["pages_fetched"] == 1
    assert report["retrieval_complete"] is False
    assert report["completion_reason"] == "LATER_PAGE_FAILED"
    assert "temporary page failure" in report["errors"][0]


def test_initial_page_failure_is_blocked_direct_access() -> None:
    getter = FakeJsonGetter(
        pages={0: RuntimeError("Brreg unavailable")},
        entities={},
    )

    report = collect_brreg_complete_window_signals(
        observed_at=NOW,
        page_size=2,
        max_pages=5,
        max_update_records=10,
        json_get=getter,
    )

    assert report["status"] == "BLOCKED_DIRECT_ACCESS"
    assert report["pages_fetched"] == 0
    assert report["retrieval_complete"] is False
    assert report["signals"] == []


def test_candidate_entity_cap_prevents_false_complete_status() -> None:
    getter = FakeJsonGetter(
        pages={
            0: _page(
                0,
                1,
                2,
                [
                    _update(1, "111111111", path="/konkurs", value=True),
                    _update(2, "222222222", path="/konkurs", value=True),
                ],
            )
        },
        entities={"111111111": _clothing_entity("111111111")},
    )

    report = collect_brreg_complete_window_signals(
        observed_at=NOW,
        page_size=2,
        max_pages=5,
        max_update_records=10,
        entity_fetch_limit=1,
        json_get=getter,
    )

    assert report["status"] == "PARTIAL_RETRIEVAL"
    assert report["update_window_complete"] is True
    assert report["candidate_evaluation_complete"] is False
    assert report["candidate_entity_count"] == 2
    assert report["entity_fetch_count"] == 1
    assert report["accepted_signal_count"] == 1
