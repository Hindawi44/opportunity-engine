from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from opportunity_engine.discovery.search_provider import SearchHit
from opportunity_engine.discovery.sweden_organisation_discovery_bridge import (
    OUTPUT_FILENAME,
    discover_sweden_artifact_company_names,
    resolve_sweden_artifact_company_identities,
)


NOW = datetime(2026, 8, 4, 8, 0, tzinfo=timezone.utc)


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


def _environment() -> dict[str, str]:
    return {
        "BOLAGSVERKET_CLIENT_ID": "client-id",
        "BOLAGSVERKET_CLIENT_SECRET": "client-secret",
    }


def _token_post(
    token_url: str,
    client_id: str,
    client_secret: str,
    scope: str,
    timeout: float,
) -> Mapping[str, Any]:
    assert client_id == "client-id"
    assert client_secret == "client-secret"
    assert scope == "vardefulla-datamangder:read"
    assert timeout > 0
    return {"access_token": "test-token"}


def _official_row(
    *,
    org_number: str = "5561112222",
    company_name: str = "NORDIC WORKWEAR AB",
    clothing: bool = True,
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
            "beskrivning": (
                "Handel med kläder och arbetskläder"
                if clothing
                else "Handel med cyklar"
            )
        },
        "naringsgrenOrganisation": {
            "sni": [
                {
                    "kod": "47710" if clothing else "47642",
                    "klartext": (
                        "Specialiserad butikshandel med kläder"
                        if clothing
                        else "Specialiserad butikshandel med cyklar"
                    ),
                }
            ]
        },
    }


class _SearchProvider:
    name = "test search"

    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits
        self.queries: list[str] = []

    def search(self, query: str, *, count: int = 10) -> list[SearchHit]:
        self.queries.append(query)
        assert 1 <= count <= 10
        return self.hits[:count]


def test_discovers_only_explicit_company_fields_and_context(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "se-blinto"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "candidates.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "title": "Nordic Workwear AB",
                        "company_name": "Nordic Workwear",
                        "source_url": "https://www.blinto.se/auction/workwear-1",
                    },
                    {
                        "title": "Title Must Not Become Company AB",
                        "description": "Säljare: Väst Mode AB | parti med kläder",
                    },
                    {
                        "seller_name": "Blinto kundtjänst",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    names, diagnostics = discover_sweden_artifact_company_names(
        _manifest(tmp_path),
        root=".",
    )

    assert [item["artifact_company_name"] for item in names] == [
        "Nordic Workwear",
        "Väst Mode AB",
    ]
    assert diagnostics["artifact_company_name_count"] == 2
    assert all(
        item["artifact_company_name"] != "Title Must Not Become Company AB"
        for item in names
    )


def test_resolves_name_through_search_then_official_api_and_persists(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "se-blinto"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "candidate.json").write_text(
        json.dumps(
            {
                "company_name": "Nordic Workwear",
                "source_url": "https://www.blinto.se/auction/workwear-1",
            }
        ),
        encoding="utf-8",
    )
    provider = _SearchProvider(
        [
            SearchHit(
                title="Nordic Workwear AB - organisationsnummer 556111-2222",
                url="https://www.allabolag.se/5561112222/nordic-workwear-ab",
                description="Nordic Workwear AB, org.nr 556111-2222",
                provider="test",
            )
        ]
    )
    calls: list[str] = []

    def api_post(
        url: str,
        body: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> Mapping[str, Any]:
        calls.append(str(body["identitetsbeteckning"]))
        assert headers["Authorization"] == "Bearer test-token"
        assert timeout > 0
        return {"organisationer": [_official_row()]}

    report = resolve_sweden_artifact_company_identities(
        _manifest(tmp_path),
        root=".",
        observed_at=NOW,
        environment=_environment(),
        search_provider=provider,
        token_post=_token_post,
        api_post=api_post,
    )

    assert report["status"] == "SUCCESS"
    assert report["new_resolved_organisation_count"] == 1
    assert report["durable_organisation_count"] == 1
    assert report["resolved_organisations"][0]["organisationsnummer"] == "5561112222"
    assert calls == ["5561112222"]
    assert provider.queries == ['"Nordic Workwear" organisationsnummer']
    output = json.loads((artifact_dir / OUTPUT_FILENAME).read_text(encoding="utf-8"))
    assert output["resolved_organisations"][0]["organisationsnummer"] == "5561112222"
    assert output["automatic_purchase"] is False


def test_durable_identity_is_reused_without_manual_secret_or_current_name(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "se-blinto"
    artifact_dir.mkdir(parents=True)
    candidate_path = artifact_dir / "candidate.json"
    candidate_path.write_text(
        json.dumps({"company_name": "Nordic Workwear"}),
        encoding="utf-8",
    )
    provider = _SearchProvider(
        [
            SearchHit(
                title="Nordic Workwear AB 556111-2222",
                url="https://www.allabolag.se/5561112222/nordic-workwear-ab",
                description="",
                provider="test",
            )
        ]
    )

    def api_post(
        url: str,
        body: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> Mapping[str, Any]:
        return {"organisationer": [_official_row()]}

    first = resolve_sweden_artifact_company_identities(
        _manifest(tmp_path),
        root=".",
        observed_at=NOW,
        environment=_environment(),
        search_provider=provider,
        token_post=_token_post,
        api_post=api_post,
    )
    assert first["durable_organisation_count"] == 1

    candidate_path.unlink()
    second = resolve_sweden_artifact_company_identities(
        _manifest(tmp_path),
        root=".",
        observed_at=NOW,
        environment={},
        search_provider=None,
    )

    assert second["status"] == "VALID_ZERO"
    assert second["artifact_company_name_count"] == 0
    assert second["durable_organisation_count"] == 1
    assert second["resolved_organisations"][0]["organisationsnummer"] == "5561112222"


def test_official_name_mismatch_is_not_persisted(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "se-blinto"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "candidate.json").write_text(
        json.dumps({"seller_name": "Nordic Workwear"}),
        encoding="utf-8",
    )
    provider = _SearchProvider(
        [
            SearchHit(
                title="Other Company AB 556111-2222",
                url="https://www.allabolag.se/5561112222/other-company-ab",
                description="",
                provider="test",
            )
        ]
    )

    def api_post(
        url: str,
        body: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> Mapping[str, Any]:
        return {
            "organisationer": [
                _official_row(company_name="OTHER COMPANY AB")
            ]
        }

    report = resolve_sweden_artifact_company_identities(
        _manifest(tmp_path),
        root=".",
        observed_at=NOW,
        environment=_environment(),
        search_provider=provider,
        token_post=_token_post,
        api_post=api_post,
    )

    assert report["status"] == "VALID_ZERO"
    assert report["durable_organisation_count"] == 0
    assert report["unresolved_company_name_count"] == 1
    assert report["rejected_name_mismatch_count"] == 1


def test_missing_search_configuration_is_truthful_and_hides_secrets(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "se-blinto"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "candidate.json").write_text(
        json.dumps({"company_name": "Nordic Workwear"}),
        encoding="utf-8",
    )

    report = resolve_sweden_artifact_company_identities(
        _manifest(tmp_path),
        root=".",
        observed_at=NOW,
        environment=_environment(),
    )

    assert report["status"] == "BLOCKED_CONFIGURATION"
    assert report["missing_configuration"] == ["BRAVE_SEARCH_API_KEY"]
    assert "client-secret" not in json.dumps(report)
    for key in (
        "automatic_contact",
        "automatic_bid",
        "automatic_purchase",
        "automatic_payment",
    ):
        assert report[key] is False
