"""Resolve Swedish auction-company names into durable official organisation identities.

This bridge is bounded and read-only. It discovers explicit company or seller names
already present in Swedish market artifacts, uses Brave only to discover candidate
organisation numbers, verifies every candidate through Bolagsverket's official
OAuth API, and persists only exact-name clothing-company matches.

It never treats a search result as verified, never converts an identity into an
opportunity or market signal, and never contacts, bids, buys, reserves, or pays.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, MutableMapping, Sequence
import unicodedata
from urllib.parse import urlparse

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.direct_official_source_adapters import (
    DEFAULT_TIMEOUT_SECONDS,
    _compact,
    _iso_utc,
    _safety_payload,
    _target_spec,
)
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider
from opportunity_engine.discovery.sweden_valuable_datasets_status_feed import (
    BOLAGSVERKET_BASE_URL,
    BOLAGSVERKET_SCOPE,
    BOLAGSVERKET_TOKEN_URL,
    ApiPoster,
    TokenPoster,
    _company_name,
    _default_api_post,
    _default_token_post,
    _is_clothing_organisation,
    _organisation_rows,
)
from opportunity_engine.persistence.database import (
    create_database_engine,
    create_session_factory,
    session_scope,
    upgrade_database,
)
from opportunity_engine.persistence.sweden_organisation_watchlist_repository import (
    SwedenOrganisationIdentity,
    SwedenOrganisationWatchlistRepository,
)


SCHEMA_VERSION = "sweden-organisation-discovery-bridge-1.0"
OUTPUT_FILENAME = "sweden-resolved-organisation-identities.json"
DEFAULT_COMPANY_NAME_LIMIT = 10
DEFAULT_SEARCH_RESULT_LIMIT = 5
DEFAULT_OFFICIAL_REQUEST_LIMIT = 10
DEFAULT_ARTIFACT_FILE_LIMIT = 100
DEFAULT_ARTIFACT_FILE_BYTES = 5_000_000

_COMPANY_NAME_KEYS = {
    "company_name",
    "company",
    "companyname",
    "seller_name",
    "seller",
    "seller_company",
    "seller_company_name",
    "organisation_name",
    "organization_name",
    "organisationsnamn",
    "legal_name",
    "business_name",
}
_URL_KEYS = {
    "url",
    "source_url",
    "canonical_url",
    "listing_url",
    "auction_url",
}
_CONTEXT_NAME_RE = re.compile(
    r"(?i)(?:företagsnamn|foretagsnamn|bolagsnamn|organisationsnamn|"
    r"säljare|saljare|på uppdrag av|pa uppdrag av|konkursboet efter)"
    r"\s*[:#-]\s*(?P<name>[^\n|;,]{2,200})"
)
_ANY_ORG_RE = re.compile(r"(?<!\d)(?P<a>\d{6})[- ]?(?P<b>\d{4})(?!\d)")
_TRUSTED_DISCOVERY_HOSTS = {
    "allabolag.se",
    "bolagsfakta.se",
    "proff.se",
    "foretagsinfo.bolagsverket.se",
}
_GENERIC_NAMES = {
    "blinto",
    "blinto kundtjänst",
    "blinto kundtjanst",
    "privatperson",
    "näringsidkare",
    "naringsidkare",
    "momspliktig organisation",
    "annan momspliktig organisation",
    "okänd",
    "okand",
    "unknown",
    "seller",
    "säljare",
    "saljare",
}
_LEGAL_SUFFIXES = {
    "ab",
    "aktiebolag",
    "hb",
    "handelsbolag",
    "kb",
    "kommanditbolag",
}


def _normalise_company_candidate(value: object) -> str | None:
    text = " ".join(str(value or "").split()).strip(" \t\r\n:;,-")
    if not text or len(text) < 2 or len(text) > 200:
        return None
    folded = text.casefold()
    if folded in _GENERIC_NAMES or "@" in text or "://" in text:
        return None
    if not any(character.isalpha() for character in text):
        return None
    if folded.startswith(("http ", "www.", "blinto kund")):
        return None
    return text


def _company_match_key(value: object) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    tokens = re.findall(r"[a-z0-9]+", ascii_text)
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _official_company_names(row: Mapping[str, Any]) -> list[str]:
    names: list[str] = []
    branch = row.get("organisationsnamn")
    raw = branch.get("organisationsnamnLista") if isinstance(branch, Mapping) else None
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            candidate = _normalise_company_candidate(item.get("namn"))
            if candidate and candidate not in names:
                names.append(candidate)
    fallback = _company_name(row)
    if fallback and fallback not in names:
        names.append(fallback)
    return names


def _mapping_source_urls(value: Mapping[str, Any]) -> list[str]:
    urls: list[str] = []
    for key, item in value.items():
        folded = _compact(key).casefold()
        if folded in _URL_KEYS:
            candidates: Sequence[object]
            if isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
                candidates = item
            else:
                candidates = (item,)
            for candidate in candidates:
                text = _compact(candidate)
                if text.startswith("https://") and text not in urls:
                    urls.append(text)
        elif folded == "source_urls" and isinstance(item, Sequence) and not isinstance(
            item, (str, bytes)
        ):
            for candidate in item:
                text = _compact(candidate)
                if text.startswith("https://") and text not in urls:
                    urls.append(text)
    return urls[:5]


def _walk_company_names(
    value: object,
    *,
    artifact_path: str,
    key_hint: str = "",
    parent: Mapping[str, Any] | None = None,
    result: MutableMapping[str, dict[str, Any]],
) -> None:
    if isinstance(value, Mapping):
        urls = _mapping_source_urls(value)
        for key, item in value.items():
            folded_key = _compact(key).casefold()
            if folded_key in _COMPANY_NAME_KEYS and not isinstance(item, (Mapping, list, tuple)):
                candidate = _normalise_company_candidate(item)
                if candidate:
                    marker = _company_match_key(candidate)
                    if marker:
                        record = result.setdefault(
                            marker,
                            {
                                "artifact_company_name": candidate,
                                "artifact_paths": [],
                                "source_urls": [],
                            },
                        )
                        if artifact_path not in record["artifact_paths"]:
                            record["artifact_paths"].append(artifact_path)
                        for url in urls:
                            if url not in record["source_urls"]:
                                record["source_urls"].append(url)
            _walk_company_names(
                item,
                artifact_path=artifact_path,
                key_hint=folded_key,
                parent=value,
                result=result,
            )
        return

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            _walk_company_names(
                item,
                artifact_path=artifact_path,
                key_hint=key_hint,
                parent=parent,
                result=result,
            )
        return

    if isinstance(value, str):
        if key_hint in _COMPANY_NAME_KEYS:
            candidate = _normalise_company_candidate(value)
            if candidate:
                marker = _company_match_key(candidate)
                if marker:
                    record = result.setdefault(
                        marker,
                        {
                            "artifact_company_name": candidate,
                            "artifact_paths": [],
                            "source_urls": [],
                        },
                    )
                    if artifact_path not in record["artifact_paths"]:
                        record["artifact_paths"].append(artifact_path)
        for match in _CONTEXT_NAME_RE.finditer(value):
            candidate = _normalise_company_candidate(match.group("name"))
            if not candidate:
                continue
            marker = _company_match_key(candidate)
            if not marker:
                continue
            record = result.setdefault(
                marker,
                {
                    "artifact_company_name": candidate,
                    "artifact_paths": [],
                    "source_urls": [],
                },
            )
            if artifact_path not in record["artifact_paths"]:
                record["artifact_paths"].append(artifact_path)


def discover_sweden_artifact_company_names(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    file_limit: int = DEFAULT_ARTIFACT_FILE_LIMIT,
    max_file_bytes: int = DEFAULT_ARTIFACT_FILE_BYTES,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return explicit bounded company-name candidates from Swedish artifacts."""
    if file_limit < 1 or max_file_bytes < 1:
        raise ValueError("artifact scan bounds must be positive")

    target = _target_spec(manifest, "SE")
    result: dict[str, dict[str, Any]] = {}
    scanned = 0
    skipped_large = 0
    invalid = 0
    artifact_dir: Path | None = None

    if target is not None:
        raw_dir = _compact(target.get("artifact_dir"))
        if raw_dir:
            artifact_dir = Path(root) / raw_dir
            if artifact_dir.exists():
                paths = [
                    path
                    for path in sorted(artifact_dir.rglob("*.json"))
                    if path.name != OUTPUT_FILENAME
                ][:file_limit]
                for path in paths:
                    try:
                        size = path.stat().st_size
                    except OSError:
                        invalid += 1
                        continue
                    if size > max_file_bytes:
                        skipped_large += 1
                        continue
                    try:
                        payload = json.loads(path.read_text(encoding="utf-8"))
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                        invalid += 1
                        continue
                    scanned += 1
                    _walk_company_names(
                        payload,
                        artifact_path=path.as_posix(),
                        result=result,
                    )

    names = [result[key] for key in sorted(result)]
    return names, {
        "artifact_dir": artifact_dir.as_posix() if artifact_dir else None,
        "artifact_company_name_count": len(names),
        "artifact_json_files_scanned": scanned,
        "artifact_json_files_skipped_large": skipped_large,
        "artifact_json_files_invalid": invalid,
    }


def _trusted_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").casefold().removeprefix("www.")
    return host in _TRUSTED_DISCOVERY_HOSTS


def _candidate_org_numbers(hit: SearchHit) -> list[str]:
    if not _trusted_host(hit.url):
        return []
    combined = f"{hit.url} {hit.title} {hit.description}"
    numbers: list[str] = []
    for match in _ANY_ORG_RE.finditer(combined):
        number = f"{match.group('a')}{match.group('b')}"
        if number not in numbers:
            numbers.append(number)
    return numbers[:3]


def _artifact_display_path(path: Path, root: str | Path) -> str:
    try:
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _identity_output(
    identities: Sequence[SwedenOrganisationIdentity],
) -> list[dict[str, Any]]:
    return [
        {
            "organisationsnummer": item.organisation_number,
            "company_name": item.company_name,
            "artifact_company_name": item.artifact_company_name,
            "source_provider": item.source_provider,
            "source_url": item.source_url,
            "first_seen_at": _iso_utc(item.first_seen_at),
            "last_seen_at": _iso_utc(item.last_seen_at),
            "verified_at": _iso_utc(item.verified_at),
        }
        for item in identities
    ]


def resolve_sweden_artifact_company_identities(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    config_path: str | Path = "alembic.ini",
    company_name_limit: int = DEFAULT_COMPANY_NAME_LIMIT,
    search_result_limit: int = DEFAULT_SEARCH_RESULT_LIMIT,
    official_request_limit: int = DEFAULT_OFFICIAL_REQUEST_LIMIT,
    search_provider: SearchProvider | None = None,
    token_post: TokenPoster = _default_token_post,
    api_post: ApiPoster = _default_api_post,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Resolve artifact names and persist exact official clothing-company matches."""
    if not 1 <= company_name_limit <= 25:
        raise ValueError("company_name_limit must be between 1 and 25")
    if not 1 <= search_result_limit <= 10:
        raise ValueError("search_result_limit must be between 1 and 10")
    if not 1 <= official_request_limit <= 10:
        raise ValueError("official_request_limit must be between 1 and 10")

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    env = environment if environment is not None else os.environ

    names, discovery = discover_sweden_artifact_company_names(manifest, root=root)
    target = _target_spec(manifest, "SE")
    raw_dir = _compact(target.get("artifact_dir")) if target else ""
    artifact_dir = Path(root) / raw_dir if raw_dir else None
    output_path = artifact_dir / OUTPUT_FILENAME if artifact_dir else None
    database_url = (
        f"sqlite:///{(artifact_dir / 'opportunity_engine.db').as_posix()}"
        if artifact_dir
        else ""
    )

    common = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "source_country": "SE",
        "bridge_mode": "BRAVE_DISCOVERY_OFFICIAL_BOLAGSVERKET_VERIFICATION",
        "company_name_limit": company_name_limit,
        "search_result_limit": search_result_limit,
        "official_request_limit": official_request_limit,
        **discovery,
        **_safety_payload(),
    }

    if artifact_dir is None:
        return {
            **common,
            "status": "BLOCKED_CONFIGURATION",
            "block_reason": "MISSING_SWEDEN_ARTIFACT_DIRECTORY",
            "errors": [],
            "resolved_organisations": [],
        }

    artifact_dir.mkdir(parents=True, exist_ok=True)
    upgrade_database(database_url, config_path=config_path)
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)

    with session_scope(factory) as session:
        repository = SwedenOrganisationWatchlistRepository(session)
        existing = repository.list_identities(limit=50)

    if not names:
        payload = {
            **common,
            "status": "VALID_ZERO",
            "block_reason": None,
            "company_name_query_count": 0,
            "official_candidate_check_count": 0,
            "new_resolved_organisation_count": 0,
            "durable_organisation_count": len(existing),
            "unresolved_company_name_count": 0,
            "errors": [],
            "resolved_organisations": _identity_output(existing),
        }
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["artifact_path"] = _artifact_display_path(output_path, root)
        return payload

    selected_names = names[:company_name_limit]
    name_limit_reached = len(names) > len(selected_names)
    client_id = _compact(env.get("BOLAGSVERKET_CLIENT_ID"))
    client_secret = _compact(env.get("BOLAGSVERKET_CLIENT_SECRET"))
    brave_key = _compact(env.get("BRAVE_SEARCH_API_KEY"))
    missing: list[str] = []
    if not client_id:
        missing.append("BOLAGSVERKET_CLIENT_ID")
    if not client_secret:
        missing.append("BOLAGSVERKET_CLIENT_SECRET")
    if search_provider is None and not brave_key:
        missing.append("BRAVE_SEARCH_API_KEY")

    if missing:
        payload = {
            **common,
            "status": "BLOCKED_CONFIGURATION",
            "block_reason": "MISSING_IDENTITY_RESOLUTION_CONFIGURATION",
            "missing_configuration": missing,
            "company_name_query_count": 0,
            "official_candidate_check_count": 0,
            "new_resolved_organisation_count": 0,
            "durable_organisation_count": len(existing),
            "unresolved_company_name_count": len(selected_names),
            "company_name_limit_reached": name_limit_reached,
            "errors": [],
            "resolved_organisations": _identity_output(existing),
        }
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["artifact_path"] = _artifact_display_path(output_path, root)
        return payload

    provider = search_provider or BraveSearchProvider(
        brave_key,
        country="SE",
        freshness=None,
        extra_snippets=True,
    )
    token_url = _compact(env.get("BOLAGSVERKET_TOKEN_URL")) or BOLAGSVERKET_TOKEN_URL
    base_url = _compact(env.get("BOLAGSVERKET_BASE_URL")) or BOLAGSVERKET_BASE_URL
    source_url = f"{base_url.rstrip('/')}/organisationer"

    errors: list[str] = []
    try:
        token_payload = token_post(
            token_url,
            client_id,
            client_secret,
            BOLAGSVERKET_SCOPE,
            timeout,
        )
        access_token = _compact(token_payload.get("access_token"))
        if not access_token:
            raise RuntimeError("OAuth response omitted access_token")
    except Exception as exc:
        payload = {
            **common,
            "status": "BLOCKED_AUTHENTICATION",
            "block_reason": "OAUTH_TOKEN_REQUEST_FAILED",
            "missing_configuration": [],
            "company_name_query_count": 0,
            "official_candidate_check_count": 0,
            "new_resolved_organisation_count": 0,
            "durable_organisation_count": len(existing),
            "unresolved_company_name_count": len(selected_names),
            "company_name_limit_reached": name_limit_reached,
            "errors": [f"{type(exc).__name__}: {exc}"],
            "resolved_organisations": _identity_output(existing),
        }
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["artifact_path"] = _artifact_display_path(output_path, root)
        return payload

    existing_by_number = {item.organisation_number: item for item in existing}
    resolved_by_name: dict[str, SwedenOrganisationIdentity] = {}
    newly_persisted_numbers: set[str] = set()
    queried = 0
    official_checks = 0
    candidate_numbers_seen: set[str] = set()
    name_mismatch_count = 0
    non_clothing_count = 0

    for candidate in selected_names:
        artifact_name = str(candidate["artifact_company_name"])
        artifact_key = _company_match_key(artifact_name)
        if any(
            _company_match_key(item.artifact_company_name) == artifact_key
            or _company_match_key(item.company_name) == artifact_key
            for item in existing
        ):
            continue
        try:
            hits = provider.search(
                f'"{artifact_name}" organisationsnummer',
                count=search_result_limit,
            )
            queried += 1
        except Exception as exc:
            errors.append(f"{artifact_name}: {type(exc).__name__}: {exc}")
            continue

        matched = False
        for hit in hits:
            for org_number in _candidate_org_numbers(hit):
                if org_number in candidate_numbers_seen:
                    continue
                candidate_numbers_seen.add(org_number)
                if org_number in existing_by_number:
                    resolved_by_name[artifact_key] = existing_by_number[org_number]
                    matched = True
                    break
                if official_checks >= official_request_limit:
                    break
                official_checks += 1
                try:
                    response = api_post(
                        source_url,
                        {"identitetsbeteckning": org_number},
                        {
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {access_token}",
                            "X-Request-Id": f"identity-bridge-{official_checks}",
                            "User-Agent": (
                                "opportunity-engine/sweden-organisation-discovery-bridge "
                                "(+https://github.com/Hindawi44/opportunity-engine)"
                            ),
                        },
                        timeout,
                    )
                    rows = _organisation_rows(response)
                except Exception as exc:
                    errors.append(
                        f"{artifact_name}/{org_number}: {type(exc).__name__}: {exc}"
                    )
                    continue

                for row in rows:
                    official_names = _official_company_names(row)
                    if artifact_key not in {
                        _company_match_key(name) for name in official_names
                    }:
                        name_mismatch_count += 1
                        continue
                    if not _is_clothing_organisation(row):
                        non_clothing_count += 1
                        continue
                    official_name = _company_name(row) or official_names[0]
                    identity = SwedenOrganisationIdentity(
                        organisation_number=org_number,
                        company_name=official_name,
                        artifact_company_name=artifact_name,
                        source_provider="Brave Search discovery + Bolagsverket verification",
                        source_url=hit.url,
                        first_seen_at=now,
                        last_seen_at=now,
                        verified_at=now,
                        payload={
                            "artifact_paths": candidate.get("artifact_paths") or [],
                            "source_urls": candidate.get("source_urls") or [],
                            "discovery_result_url": hit.url,
                            "official_endpoint": source_url,
                        },
                    )
                    with session_scope(factory) as session:
                        repository = SwedenOrganisationWatchlistRepository(session)
                        identity = repository.upsert(identity)
                    existing_by_number[org_number] = identity
                    resolved_by_name[artifact_key] = identity
                    newly_persisted_numbers.add(org_number)
                    matched = True
                    break
                if matched:
                    break
            if matched or official_checks >= official_request_limit:
                break
        if official_checks >= official_request_limit:
            break

    with session_scope(factory) as session:
        repository = SwedenOrganisationWatchlistRepository(session)
        durable = repository.list_identities(limit=50)

    unresolved = sum(
        1
        for candidate in selected_names
        if _company_match_key(candidate["artifact_company_name"]) not in resolved_by_name
        and not any(
            _company_match_key(item.artifact_company_name)
            == _company_match_key(candidate["artifact_company_name"])
            or _company_match_key(item.company_name)
            == _company_match_key(candidate["artifact_company_name"])
            for item in durable
        )
    )
    request_limit_reached = official_checks >= official_request_limit
    incomplete = bool(errors or name_limit_reached or request_limit_reached)
    status = (
        "PARTIAL_RETRIEVAL"
        if incomplete
        else "SUCCESS"
        if newly_persisted_numbers
        else "VALID_ZERO"
    )
    payload = {
        **common,
        "status": status,
        "block_reason": None,
        "missing_configuration": [],
        "company_name_query_count": queried,
        "company_name_limit_reached": name_limit_reached,
        "official_candidate_check_count": official_checks,
        "official_request_limit_reached": request_limit_reached,
        "candidate_organisation_number_count": len(candidate_numbers_seen),
        "new_resolved_organisation_count": len(newly_persisted_numbers),
        "durable_organisation_count": len(durable),
        "unresolved_company_name_count": unresolved,
        "rejected_name_mismatch_count": name_mismatch_count,
        "rejected_non_clothing_count": non_clothing_count,
        "errors": errors,
        "resolved_organisations": _identity_output(durable),
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["artifact_path"] = _artifact_display_path(output_path, root)
    return payload
