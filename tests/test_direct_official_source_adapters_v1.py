from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.direct_official_source_adapters import (
    BRREG_ENTITY_URL,
    DirectTextResponse,
    collect_brreg_direct_signals,
    collect_manifest_direct_official_signals,
    probe_german_insolvency_direct_access,
    probe_poit_direct_access,
)


NOW = datetime(2026, 8, 3, 18, 0, tzinfo=timezone.utc)


def _manifest() -> dict[str, Any]:
    return {
        "sources": [
            {
                "market_code": "NO",
                "source_name": "Auksjonen.no",
                "artifact_dir": "inputs/no-auksjonen",
            },
            {
                "market_code": "SE",
                "source_name": "Blinto",
                "artifact_dir": "inputs/se-blinto",
            },
            {
                "market_code": "DE",
                "source_name": "Riegermann",
                "artifact_dir": "inputs/de-riegermann",
            },
        ]
    }


class FakeBrregJson:
    def __init__(
        self,
        entities: Mapping[str, Mapping[str, Any]],
        *,
        updates: list[dict[str, Any]] | None = None,
        fail_updates: bool = False,
    ) -> None:
        self.entities = {key: dict(value) for key, value in entities.items()}
        self.updates = updates if updates is not None else []
        self.fail_updates = fail_updates
        self.calls: list[str] = []

    def __call__(
        self,
        url: str,
        timeout: float,
        headers: Mapping[str, str],
    ) -> Any:
        self.calls.append(url)
        assert timeout > 0
        assert headers["Accept"].startswith("application/")
        if "/oppdateringer/enheter?" in url:
            if self.fail_updates:
                raise RuntimeError("official API unavailable")
            return {"_embedded": {"oppdaterteEnheter": self.updates}}
        orgnr = url.rsplit("/", 1)[-1]
        return self.entities[orgnr]


def _status_update(orgnr: str, *, update_id: int = 1) -> dict[str, Any]:
    return {
        "oppdateringsid": update_id,
        "organisasjonsnummer": orgnr,
        "endringstype": "Endring",
        "endringer": [
            {"op": "add", "path": "/konkurs", "value": True},
            {"op": "add", "path": "/konkursdato", "value": "2026-08-03"},
        ],
    }


def _clothing_entity(orgnr: str = "999888777") -> dict[str, Any]:
    return {
        "organisasjonsnummer": orgnr,
        "navn": "Nordic Workwear AS",
        "konkurs": True,
        "konkursdato": "2026-08-03",
        "naeringskode1": {
            "kode": "47.710",
            "beskrivelse": "Butikkhandel med klær",
        },
        "forretningsadresse": {
            "adresse": ["Arbeidsveien 4"],
            "postnummer": "7010",
            "poststed": "Trondheim",
        },
    }


def test_brreg_direct_api_emits_verified_signal_only() -> None:
    orgnr = "999888777"
    transport = FakeBrregJson(
        {orgnr: _clothing_entity(orgnr)},
        updates=[_status_update(orgnr)],
    )

    report = collect_brreg_direct_signals(
        observed_at=NOW,
        json_get=transport,
    )

    assert report["status"] == "SUCCESS"
    assert report["access_mode"] == "DIRECT_OFFICIAL_REST_API"
    assert report["retrieved_record_count"] == 1
    assert report["candidate_entity_count"] == 1
    assert report["entity_fetch_count"] == 1
    assert report["accepted_signal_count"] == 1
    signal = report["signals"][0]
    assert signal["signal_type"] == "INSOLVENCY_OR_LIQUIDATION"
    assert signal["company_name"] == "Nordic Workwear AS"
    assert signal["related_opportunity_id"] is None
    assert signal["metadata"]["signal_only"] is True
    assert signal["metadata"]["source_role"] == "DIRECT_OFFICIAL_API"
    assert signal["evidence"][0]["verified"] is True
    assert signal["source_url"] == BRREG_ENTITY_URL.format(orgnr=orgnr)


def test_brreg_direct_api_rejects_non_clothing_entity() -> None:
    orgnr = "888777666"
    entity = {
        "organisasjonsnummer": orgnr,
        "navn": "Bygg og Betong AS",
        "konkurs": True,
        "konkursdato": "2026-08-03",
        "naeringskode1": {
            "kode": "41.200",
            "beskrivelse": "Oppføring av bygninger",
        },
    }
    report = collect_brreg_direct_signals(
        observed_at=NOW,
        json_get=FakeBrregJson(
            {orgnr: entity},
            updates=[_status_update(orgnr)],
        ),
    )

    assert report["status"] == "VALID_ZERO"
    assert report["accepted_signal_count"] == 0
    assert report["rejected_result_count"] == 1
    assert report["signals"] == []


def test_brreg_successful_zero_is_not_retrieval_zero() -> None:
    report = collect_brreg_direct_signals(
        observed_at=NOW,
        json_get=FakeBrregJson({}, updates=[]),
    )

    assert report["status"] == "VALID_ZERO"
    assert report["retrieved_record_count"] == 0
    assert report["errors"] == []


def test_brreg_direct_failure_is_reported_truthfully() -> None:
    report = collect_brreg_direct_signals(
        observed_at=NOW,
        json_get=FakeBrregJson({}, fail_updates=True),
    )

    assert report["status"] == "BLOCKED_DIRECT_ACCESS"
    assert report["signals"] == []
    assert report["errors"]
    assert report["automatic_contact"] is False
    assert report["automatic_bid"] is False
    assert report["automatic_purchase"] is False
    assert report["automatic_payment"] is False


def _text_response(url: str, body: str) -> DirectTextResponse:
    return DirectTextResponse(
        requested_url=url,
        final_url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        response_bytes=len(body.encode("utf-8")),
        text=body,
    )


def test_poit_human_verification_is_blocked_without_bypass() -> None:
    def text_get(
        url: str,
        timeout: float,
        headers: Mapping[str, str],
    ) -> DirectTextResponse:
        return _text_response(
            url,
            "Please enable JavaScript. This question is for testing whether you are a human visitor. Support ID: 123",
        )

    report = probe_poit_direct_access(observed_at=NOW, text_get=text_get)

    assert report["status"] == "BLOCKED_DIRECT_ACCESS"
    assert report["portal_reachable"] is True
    assert report["block_reason"] == "HUMAN_VERIFICATION_CHALLENGE"
    assert report["no_bypass_attempted"] is True
    assert report["signals"] == []


def test_german_jsf_search_is_reported_as_interactive() -> None:
    def text_get(
        url: str,
        timeout: float,
        headers: Mapping[str, str],
    ) -> DirectTextResponse:
        return _text_response(
            url,
            '<html><form><input name="javax.faces.ViewState">Suche nach Veröffentlichungen Firma/Nachname Datum der Veröffentlichung</form></html>',
        )

    report = probe_german_insolvency_direct_access(
        observed_at=NOW,
        text_get=text_get,
    )

    assert report["status"] == "BLOCKED_DIRECT_ACCESS"
    assert report["portal_reachable"] is True
    assert report["interactive_search_detected"] is True
    assert (
        report["block_reason"]
        == "INTERACTIVE_SEARCH_WITHOUT_DOCUMENTED_PUBLIC_API"
    )
    assert report["no_bypass_attempted"] is True


def test_manifest_collection_writes_direct_reports_to_existing_market_paths(
    tmp_path: Path,
) -> None:
    orgnr = "999888777"
    json_get = FakeBrregJson(
        {orgnr: _clothing_entity(orgnr)},
        updates=[_status_update(orgnr)],
    )

    def text_get(
        url: str,
        timeout: float,
        headers: Mapping[str, str],
    ) -> DirectTextResponse:
        if "poit" in url:
            return _text_response(
                url,
                "Please enable JavaScript. Testing whether you are a human visitor. Support ID 12",
            )
        return _text_response(
            url,
            '<html><input name="javax.faces.ViewState">Suche nach Veröffentlichungen Firma/Nachname</html>',
        )

    summary = collect_manifest_direct_official_signals(
        _manifest(),
        root=tmp_path,
        observed_at=NOW,
        json_get=json_get,
        text_get=text_get,
    )

    assert summary["retrieval_transport"] == "DIRECT_OFFICIAL_SOURCE"
    assert summary["market_coverage"] == ["NO", "SE", "DE"]
    assert summary["signal_count"] == 1
    assert summary["status_counts"] == {
        "SUCCESS": 1,
        "BLOCKED_DIRECT_ACCESS": 2,
    }
    expected = (
        "inputs/no-auksjonen/market-signal-report.json",
        "inputs/se-blinto/market-signal-report.json",
        "inputs/de-riegermann/market-signal-report.json",
    )
    for relative in expected:
        payload = json.loads((tmp_path / relative).read_text(encoding="utf-8"))
        assert payload["automatic_contact"] is False
        assert payload["automatic_bid"] is False
        assert payload["automatic_purchase"] is False
        assert payload["automatic_payment"] is False
    norway = json.loads((tmp_path / expected[0]).read_text(encoding="utf-8"))
    assert norway["stored_signal_count"] == 1
    assert len(norway["signals"]) == 1
