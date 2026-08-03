from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from opportunity_engine.discovery.brreg_update_id_cursor import (
    collect_brreg_update_id_cursor_signals,
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
        "dato": "2026-08-03T12:00:00.000Z",
        "organisasjonsnummer": orgnr,
        "endringstype": "Endring",
        "endringer": [{"op": "replace", "path": path, "value": value}],
    }


def _batch(total_elements: int, updates: list[dict], *, size: int = 2) -> dict:
    return {
        "_embedded": {"oppdaterteEnheter": updates},
        "page": {
            "number": 0,
            "size": size,
            "totalPages": max(1, (total_elements + size - 1) // size),
            "totalElements": total_elements,
        },
    }


class CursorJsonGetter:
    def __init__(
        self,
        batches: dict[int | None, object],
        entities: dict[str, object],
    ) -> None:
        self.batches = batches
        self.entities = entities
        self.urls: list[str] = []

    def __call__(self, url: str, timeout: float, headers: dict[str, str]) -> object:
        self.urls.append(url)
        parsed = urlparse(url)
        if parsed.path.endswith("/oppdateringer/enheter"):
            query = parse_qs(parsed.query)
            raw_cursor = query.get("oppdateringsid", [None])[0]
            cursor = int(raw_cursor) if raw_cursor is not None else None
            value = self.batches[cursor]
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


def test_cursor_continues_from_last_update_id_plus_one() -> None:
    getter = CursorJsonGetter(
        batches={
            None: _batch(
                3,
                [_update(10, "111111111"), _update(11, "222222222")],
            ),
            12: _batch(
                1,
                [_update(12, "999999999", path="/konkurs", value=True)],
            ),
        },
        entities={"999999999": _clothing_entity("999999999")},
    )

    report = collect_brreg_update_id_cursor_signals(
        observed_at=NOW,
        batch_size=2,
        max_cursor_records=10,
        max_cursor_batches=5,
        json_get=getter,
    )

    assert report["status"] == "SUCCESS"
    assert report["retrieval_mode"] == "UPDATE_ID_CURSOR"
    assert report["cursor_batches_fetched"] == 2
    assert report["cursor_batch_start_ids"] == [None, 12]
    assert report["cursor_batch_counts"] == [2, 1]
    assert report["retrieved_record_count"] == 3
    assert report["first_update_id"] == 10
    assert report["last_update_id"] == 12
    assert report["retrieval_complete"] is True
    assert report["accepted_signal_count"] == 1
    update_urls = [url for url in getter.urls if "oppdateringer/enheter" in url]
    first_query = parse_qs(urlparse(update_urls[0]).query)
    second_query = parse_qs(urlparse(update_urls[1]).query)
    assert "dato" in first_query
    assert "oppdateringsid" not in first_query
    assert second_query["oppdateringsid"] == ["12"]
    assert "dato" not in second_query
    assert second_query["updatedBefore"] == first_query["updatedBefore"]


def test_cursor_valid_zero_requires_complete_final_batch() -> None:
    getter = CursorJsonGetter(
        batches={
            None: _batch(
                3,
                [_update(20, "111111111"), _update(21, "222222222")],
            ),
            22: _batch(1, [_update(22, "333333333")]),
        },
        entities={},
    )

    report = collect_brreg_update_id_cursor_signals(
        observed_at=NOW,
        batch_size=2,
        max_cursor_records=10,
        max_cursor_batches=5,
        json_get=getter,
    )

    assert report["status"] == "VALID_ZERO"
    assert report["retrieval_complete"] is True
    assert report["completion_reason"] == "INITIAL_TOTAL_ELEMENTS_REACHED"
    assert report["candidate_entity_count"] == 0
    assert report["next_cursor_available"] is False


def test_exact_multiple_uses_empty_terminal_cursor_batch() -> None:
    getter = CursorJsonGetter(
        batches={
            None: _batch(
                4,
                [_update(30, "111111111"), _update(31, "222222222")],
            ),
            32: _batch(
                2,
                [_update(32, "333333333"), _update(33, "444444444")],
            ),
        },
        entities={},
    )

    report = collect_brreg_update_id_cursor_signals(
        observed_at=NOW,
        batch_size=2,
        max_cursor_records=10,
        max_cursor_batches=5,
        json_get=getter,
    )

    assert report["status"] == "VALID_ZERO"
    assert report["cursor_batches_fetched"] == 2
    assert report["retrieved_record_count"] == 4
    assert report["completion_reason"] == "INITIAL_TOTAL_ELEMENTS_REACHED"


def test_cursor_record_cap_reports_partial_with_resume_id() -> None:
    getter = CursorJsonGetter(
        batches={
            None: _batch(
                5,
                [_update(40, "111111111"), _update(41, "222222222")],
            ),
            42: _batch(
                3,
                [_update(42, "333333333"), _update(43, "444444444")],
            ),
        },
        entities={},
    )

    report = collect_brreg_update_id_cursor_signals(
        observed_at=NOW,
        batch_size=2,
        max_cursor_records=3,
        max_cursor_batches=5,
        json_get=getter,
    )

    assert report["status"] == "PARTIAL_RETRIEVAL"
    assert report["retrieved_record_count"] == 3
    assert report["retrieval_complete"] is False
    assert report["completion_reason"] == "MAX_CURSOR_RECORDS_REACHED"
    assert report["next_cursor_available"] is True
    assert report["next_cursor_id"] == 43


def test_later_cursor_failure_preserves_partial_truth() -> None:
    getter = CursorJsonGetter(
        batches={
            None: _batch(
                3,
                [_update(50, "111111111"), _update(51, "222222222")],
            ),
            52: RuntimeError("temporary cursor failure"),
        },
        entities={},
    )

    report = collect_brreg_update_id_cursor_signals(
        observed_at=NOW,
        batch_size=2,
        max_cursor_records=10,
        max_cursor_batches=5,
        json_get=getter,
    )

    assert report["status"] == "PARTIAL_RETRIEVAL"
    assert report["cursor_batches_fetched"] == 1
    assert report["retrieved_record_count"] == 2
    assert report["completion_reason"] == "LATER_BATCH_FAILED"
    assert report["next_cursor_id"] == 52
    assert "temporary cursor failure" in report["errors"][0]


def test_initial_cursor_failure_is_blocked() -> None:
    getter = CursorJsonGetter(
        batches={None: RuntimeError("Brreg unavailable")},
        entities={},
    )

    report = collect_brreg_update_id_cursor_signals(
        observed_at=NOW,
        batch_size=2,
        max_cursor_records=10,
        max_cursor_batches=5,
        json_get=getter,
    )

    assert report["status"] == "BLOCKED_DIRECT_ACCESS"
    assert report["cursor_batches_fetched"] == 0
    assert report["retrieval_complete"] is False
    assert report["signals"] == []


def test_non_monotonic_update_ids_are_not_declared_complete() -> None:
    getter = CursorJsonGetter(
        batches={
            None: _batch(
                2,
                [_update(61, "111111111"), _update(60, "222222222")],
            )
        },
        entities={},
    )

    report = collect_brreg_update_id_cursor_signals(
        observed_at=NOW,
        batch_size=2,
        max_cursor_records=10,
        max_cursor_batches=5,
        json_get=getter,
    )

    assert report["status"] == "BLOCKED_DIRECT_ACCESS"
    assert report["completion_reason"] == "INITIAL_BATCH_FAILED"
    assert "strictly increasing" in report["errors"][0]


def test_candidate_entity_cap_prevents_false_complete_status() -> None:
    getter = CursorJsonGetter(
        batches={
            None: _batch(
                2,
                [
                    _update(70, "111111111", path="/konkurs", value=True),
                    _update(71, "222222222", path="/konkurs", value=True),
                ],
            )
        },
        entities={"111111111": _clothing_entity("111111111")},
    )

    report = collect_brreg_update_id_cursor_signals(
        observed_at=NOW,
        batch_size=2,
        max_cursor_records=10,
        max_cursor_batches=5,
        entity_fetch_limit=1,
        json_get=getter,
    )

    assert report["status"] == "PARTIAL_RETRIEVAL"
    assert report["update_window_complete"] is True
    assert report["candidate_evaluation_complete"] is False
    assert report["candidate_entity_count"] == 2
    assert report["entity_fetch_count"] == 1
    assert report["accepted_signal_count"] == 1
