from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.sweden_valuable_datasets_status_feed import (
    BOLAGSVERKET_BASE_URL,
    BOLAGSVERKET_SCOPE,
    collect_sweden_valuable_dataset_status_signals,
    discover_tracked_sweden_organisation_numbers,
)


NOW = datetime(2026, 8, 3, 19, 0, tzinfo=timezone.utc)


def _manifest(tmp_path: Path) -> dict[str, Any]:
    return {
        "sources": [
            {
                "market_code": "SE",
                "source_name": "Blinto",
                "artifact_dir": str(tmp_path / "se-blinto"),
            }
        ]
    }


def _environment(*, seed: str = "556111-2222") -> dict[str, str]:
    return {
        "BOLAGSVERKET_CLIENT_ID": "client-id",
        "BOLAGSVERKET_CLIENT_SECRET": "client-secret",
        "BOLAGSVERKET_SE_ORGANISATION_NUMBERS": seed,
    }


def _token_post(
    token_url: str,
    client_id: str,
    client_secret: str,
    scope: str,
    timeout: float,
) -> Mapping[str, Any]:
    assert token_url.endswith("/oauth2/token")
    assert client_id == "client-id"
    assert client_secret == "client-secret"
    assert scope == BOLAGSVERKET_SCOPE
    assert timeout > 0
    return {"access_token": "test-token", "token_type": "Bearer"}


def _organisation(
    *,
    org_number: str = "5561112222",
    company_name: str = "NORDIC WORKWEAR AB",
    sni_code: str = "47710",
    sni_text: str = "Specialiserad butikshandel med kläder",
    legal_events: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "organisationsidentitet": {"identitetsbeteckning": org_number},
        "organisationsnamn": {
            "organisationsnamnLista": [
                {
                    "namn": company_name,
                    "organisationsnamntyp": {"kod": "FORETAGSNAMN"},
                }
            ]
        },
        "verksamhetsbeskrivning": {
            "beskrivning": "Handel med kläder och arbetskläder"
        },
        "naringsgrenOrganisation": {
            "sni": [{"kod": sni_code, "klartext": sni_text}]
        },
        "pagandeAvvecklingsEllerOmstruktureringsforfarande": {
            "pagandeAvvecklingsEllerOmstruktureringsforfarandeLista": (
                legal_events or []
            )
        },
    }


def test_missing_credentials_is_truthful_and_does_not_call_network(tmp_path: Path) -> None:
    calls: list[str] = []

    def token_post(*args: object) -> Mapping[str, Any]:
        calls.append("token")
        raise AssertionError("network must not be called")

    report = collect_sweden_valuable_dataset_status_signals(
        _manifest(tmp_path),
        root=".",
        observed_at=NOW,
        environment={"BOLAGSVERKET_SE_ORGANISATION_NUMBERS": "556111-2222"},
        token_post=token_post,
    )

    assert report["status"] == "BLOCKED_CONFIGURATION"
    assert report["block_reason"] == "MISSING_REQUIRED_CONFIGURATION"
    assert set(report["missing_configuration"]) == {
        "BOLAGSVERKET_CLIENT_ID",
        "BOLAGSVERKET_CLIENT_SECRET",
    }
    assert calls == []
    assert report["signals"] == []


def test_discovers_contextual_artifact_and_seed_org_numbers(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "se-blinto"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "candidate.json").write_text(
        json.dumps(
            {
                "seller": {
                    "organisationsnummer": "556333-4444",
                    "description": "Organisationsnummer: 556555-6666",
                },
                "random_listing_id": "5567778888",
            }
        ),
        encoding="utf-8",
    )

    numbers, diagnostics = discover_tracked_sweden_organisation_numbers(
        _manifest(tmp_path),
        root=".",
        seed="556111-2222, 5563334444",
    )

    assert numbers == ["5561112222", "5563334444", "5565556666"]
    assert "5567778888" not in numbers
    assert diagnostics["artifact_json_files_scanned"] == 1
    assert diagnostics["tracked_organisation_count"] == 3


def test_official_clothing_bankruptcy_emits_signal_only(tmp_path: Path) -> None:
    api_calls: list[tuple[str, Mapping[str, Any], Mapping[str, str]]] = []

    def api_post(
        url: str,
        body: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> Mapping[str, Any]:
        api_calls.append((url, body, headers))
        assert timeout > 0
        return {
            "organisationer": [
                _organisation(
                    legal_events=[
                        {
                            "kod": "KK",
                            "klartext": "Konkurs",
                            "fromDatum": "2026-08-02",
                        }
                    ]
                )
            ]
        }

    report = collect_sweden_valuable_dataset_status_signals(
        _manifest(tmp_path),
        root=".",
        observed_at=NOW,
        environment=_environment(),
        token_post=_token_post,
        api_post=api_post,
    )

    assert report["status"] == "SUCCESS"
    assert report["retrieval_complete"] is True
    assert report["checked_organisation_count"] == 1
    assert report["candidate_entity_count"] == 1
    assert report["accepted_signal_count"] == 1
    signal = report["signals"][0]
    assert signal["signal_type"] == "INSOLVENCY_OR_LIQUIDATION"
    assert signal["source_country"] == "SE"
    assert signal["company_name"] == "NORDIC WORKWEAR AB"
    assert signal["related_opportunity_id"] is None
    assert signal["metadata"]["signal_only"] is True
    assert signal["metadata"]["legal_status_code"] == "KK"
    assert signal["metadata"]["automatic_purchase"] is False
    assert len(api_calls) == 1
    url, body, headers = api_calls[0]
    assert url == f"{BOLAGSVERKET_BASE_URL}/organisationer"
    assert body == {"identitetsbeteckning": "5561112222"}
    assert headers["Authorization"] == "Bearer test-token"
    assert headers["X-Request-Id"]


def test_non_clothing_legal_status_is_rejected_as_valid_zero(tmp_path: Path) -> None:
    def api_post(
        url: str,
        body: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> Mapping[str, Any]:
        row = _organisation(
            company_name="CYKELHANDEL AB",
            sni_code="47642",
            sni_text="Specialiserad butikshandel med cyklar",
            legal_events=[
                {
                    "kod": "LI",
                    "klartext": "Likvidation",
                    "fromDatum": "2026-08-01",
                }
            ],
        )
        row["verksamhetsbeskrivning"] = {"beskrivning": "Handel med cyklar"}
        return {"organisationer": [row]}

    report = collect_sweden_valuable_dataset_status_signals(
        _manifest(tmp_path),
        root=".",
        observed_at=NOW,
        environment=_environment(),
        token_post=_token_post,
        api_post=api_post,
    )

    assert report["status"] == "VALID_ZERO"
    assert report["candidate_entity_count"] == 1
    assert report["non_clothing_count"] == 1
    assert report["accepted_signal_count"] == 0


def test_clothing_company_without_legal_status_is_valid_zero(tmp_path: Path) -> None:
    def api_post(
        url: str,
        body: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> Mapping[str, Any]:
        return {"organisationer": [_organisation(legal_events=[])]}

    report = collect_sweden_valuable_dataset_status_signals(
        _manifest(tmp_path),
        root=".",
        observed_at=NOW,
        environment=_environment(),
        token_post=_token_post,
        api_post=api_post,
    )

    assert report["status"] == "VALID_ZERO"
    assert report["candidate_entity_count"] == 0
    assert report["no_legal_status_count"] == 1
    assert report["signals"] == []


def test_organisation_limit_is_partial_not_valid_zero(tmp_path: Path) -> None:
    def api_post(
        url: str,
        body: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> Mapping[str, Any]:
        org = str(body["identitetsbeteckning"])
        return {"organisationer": [_organisation(org_number=org, legal_events=[])]}

    report = collect_sweden_valuable_dataset_status_signals(
        _manifest(tmp_path),
        root=".",
        observed_at=NOW,
        environment=_environment(seed="556111-2222,556333-4444"),
        organisation_limit=1,
        token_post=_token_post,
        api_post=api_post,
    )

    assert report["status"] == "PARTIAL_RETRIEVAL"
    assert report["retrieval_complete"] is False
    assert report["organisation_limit_reached"] is True
    assert report["remaining_organisation_count"] == 1
    assert report["checked_organisation_count"] == 1


def test_one_company_failure_preserves_partial_truth(tmp_path: Path) -> None:
    def api_post(
        url: str,
        body: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> Mapping[str, Any]:
        org = str(body["identitetsbeteckning"])
        if org == "5563334444":
            raise RuntimeError("temporary organisation failure")
        return {"organisationer": [_organisation(org_number=org, legal_events=[])]}

    report = collect_sweden_valuable_dataset_status_signals(
        _manifest(tmp_path),
        root=".",
        observed_at=NOW,
        environment=_environment(seed="556111-2222,556333-4444"),
        token_post=_token_post,
        api_post=api_post,
    )

    assert report["status"] == "PARTIAL_RETRIEVAL"
    assert report["retrieval_complete"] is False
    assert report["checked_organisation_count"] == 2
    assert len(report["errors"]) == 1
    assert "temporary organisation failure" in report["errors"][0]


def test_oauth_failure_is_blocked_authentication(tmp_path: Path) -> None:
    def token_post(*args: object) -> Mapping[str, Any]:
        raise RuntimeError("invalid client")

    report = collect_sweden_valuable_dataset_status_signals(
        _manifest(tmp_path),
        root=".",
        observed_at=NOW,
        environment=_environment(),
        token_post=token_post,
    )

    assert report["status"] == "BLOCKED_AUTHENTICATION"
    assert report["block_reason"] == "OAUTH_TOKEN_REQUEST_FAILED"
    assert report["checked_organisation_count"] == 0
    assert "client-secret" not in json.dumps(report)


def test_no_tracked_companies_is_blocked_configuration(tmp_path: Path) -> None:
    report = collect_sweden_valuable_dataset_status_signals(
        _manifest(tmp_path),
        root=".",
        observed_at=NOW,
        environment={
            "BOLAGSVERKET_CLIENT_ID": "client-id",
            "BOLAGSVERKET_CLIENT_SECRET": "client-secret",
        },
        token_post=_token_post,
    )

    assert report["status"] == "BLOCKED_CONFIGURATION"
    assert (
        "BOLAGSVERKET_SE_ORGANISATION_NUMBERS_OR_ARTIFACT_ORG_NUMBERS"
        in report["missing_configuration"]
    )
    assert report["tracked_organisation_count"] == 0


def test_all_automatic_actions_remain_disabled(tmp_path: Path) -> None:
    report = collect_sweden_valuable_dataset_status_signals(
        _manifest(tmp_path),
        root=".",
        observed_at=NOW,
        environment={},
    )

    for key in (
        "automatic_contact",
        "automatic_bid",
        "automatic_purchase",
        "automatic_payment",
    ):
        assert report[key] is False
