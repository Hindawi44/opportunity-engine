"""Official Sweden company-status feed using Bolagsverket valuable datasets.

The adapter is intentionally bounded and read-only.  It reuses Swedish company
registration numbers already present in the current market artifacts (plus an
optional explicit environment seed), verifies those companies through the
official OAuth-protected API, and emits standalone ``MarketSignalRecord``
objects only for clothing-domain organisations with an ongoing insolvency,
liquidation, restructuring, or wind-down procedure.

It never bypasses access controls, discovers unrelated companies, contacts a
seller, bids, buys, reserves, pays, or converts a signal into an opportunity.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping, MutableMapping, Sequence
from urllib.parse import urlparse
from uuid import uuid4

import requests

from opportunity_engine.discovery.brreg_update_id_cursor import (
    collect_brreg_update_id_cursor_signals,
)
from opportunity_engine.discovery.direct_official_source_adapters import (
    DEFAULT_MAX_RESPONSE_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    JsonGetter,
    TextGetter,
    _compact,
    _default_json_get,
    _default_text_get,
    _iso_utc,
    _safety_payload,
    _target_spec,
    _write_merged_report,
    probe_german_insolvency_direct_access,
)
from opportunity_engine.market_intelligence import (
    MarketSignalRecord,
    MarketSignalStatus,
    MarketSignalType,
)
from opportunity_engine.unified_models import Evidence


SCHEMA_VERSION = "direct-official-source-adapters-1.3"
BOLAGSVERKET_TOKEN_URL = "https://portal.api.bolagsverket.se/oauth2/token"
BOLAGSVERKET_BASE_URL = (
    "https://gw.api.bolagsverket.se/vardefulla-datamangder/v1"
)
BOLAGSVERKET_SCOPE = "vardefulla-datamangder:read"
DEFAULT_ORGANISATION_LIMIT = 50
DEFAULT_ARTIFACT_FILE_LIMIT = 100
DEFAULT_ARTIFACT_FILE_BYTES = 5_000_000

_ORG_NUMBER_KEYS = {
    "organisationsnummer",
    "organisationsnummer_se",
    "organisation_number",
    "organization_number",
    "company_registration_number",
    "company_number",
    "orgnr",
    "org_nr",
}
_ORG_CONTEXT_RE = re.compile(
    r"(?i)(?:organisationsnummer|org\.?\s*nr|orgnr)\s*[:#-]?\s*"
    r"(?P<number>\d{6}[- ]?\d{4})"
)
_EXACT_ORG_RE = re.compile(r"^\s*(\d{6})[- ]?(\d{4})\s*$")

_CLOTHING_SNI_PREFIXES = (
    "141",   # manufacture of wearing apparel
    "142",   # manufacture of articles of fur
    "143",   # manufacture of knitted/crocheted apparel
    "152",   # manufacture of footwear
    "4642",  # wholesale of clothing and footwear
    "4771",  # retail sale of clothing
)
_CLOTHING_TERMS = (
    "kläder",
    "klader",
    "beklädnad",
    "bekladnad",
    "konfektion",
    "mode",
    "textil",
    "arbetskläder",
    "arbetsklader",
    "workwear",
    "uniform",
    "skor",
    "footwear",
)
_LEGAL_STATUS_TERMS = (
    "konkurs",
    "likvidation",
    "rekonstruktion",
    "avveckling",
    "insolvens",
)
_LEGAL_CODE_KIND = {
    "KK": "KONKURS",
    "LI": "LIKVIDATION",
    "FR": "FORETAGSREKONSTRUKTION",
}

TokenPoster = Callable[
    [str, str, str, str, float],
    Mapping[str, Any],
]
ApiPoster = Callable[
    [str, Mapping[str, Any], Mapping[str, str], float],
    Mapping[str, Any],
]


def _official_https_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold().rstrip(".")
    return parsed.scheme == "https" and (
        host == "bolagsverket.se" or host.endswith(".bolagsverket.se")
    )


def _default_token_post(
    token_url: str,
    client_id: str,
    client_secret: str,
    scope: str,
    timeout: float,
) -> Mapping[str, Any]:
    if not _official_https_url(token_url):
        raise RuntimeError("Bolagsverket token URL must remain on an official HTTPS host")
    response = requests.post(
        token_url,
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials", "scope": scope},
        headers={"Accept": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    raw = bytes(response.content)
    if len(raw) > DEFAULT_MAX_RESPONSE_BYTES:
        raise RuntimeError("Bolagsverket token response exceeded the size limit")
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Bolagsverket token endpoint returned invalid JSON") from exc
    if not isinstance(payload, Mapping):
        raise RuntimeError("Bolagsverket token response must be a JSON object")
    return payload


def _default_api_post(
    url: str,
    body: Mapping[str, Any],
    headers: Mapping[str, str],
    timeout: float,
) -> Mapping[str, Any]:
    if not _official_https_url(url):
        raise RuntimeError("Bolagsverket API URL must remain on an official HTTPS host")
    response = requests.post(
        url,
        json=dict(body),
        headers=dict(headers),
        timeout=timeout,
    )
    response.raise_for_status()
    raw = bytes(response.content)
    if len(raw) > DEFAULT_MAX_RESPONSE_BYTES:
        raise RuntimeError("Bolagsverket organisation response exceeded the size limit")
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Bolagsverket organisation endpoint returned invalid JSON") from exc
    if not isinstance(payload, Mapping):
        raise RuntimeError("Bolagsverket organisation response must be a JSON object")
    return payload


def _normalise_org_number(value: object) -> str | None:
    match = _EXACT_ORG_RE.match(_compact(value))
    if not match:
        return None
    return f"{match.group(1)}{match.group(2)}"


def _org_numbers_from_seed(raw: str | None) -> set[str]:
    if not raw:
        return set()
    result: set[str] = set()
    for part in re.split(r"[,;\s]+", raw):
        number = _normalise_org_number(part)
        if number:
            result.add(number)
    return result


def _walk_org_numbers(value: object, *, key_hint: str = "") -> set[str]:
    result: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            folded_key = _compact(key).casefold()
            if folded_key in _ORG_NUMBER_KEYS:
                if isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
                    for candidate in item:
                        number = _normalise_org_number(candidate)
                        if number:
                            result.add(number)
                else:
                    number = _normalise_org_number(item)
                    if number:
                        result.add(number)
            result.update(_walk_org_numbers(item, key_hint=folded_key))
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            result.update(_walk_org_numbers(item, key_hint=key_hint))
        return result
    if isinstance(value, str):
        if key_hint in _ORG_NUMBER_KEYS:
            number = _normalise_org_number(value)
            if number:
                result.add(number)
        for match in _ORG_CONTEXT_RE.finditer(value):
            number = _normalise_org_number(match.group("number"))
            if number:
                result.add(number)
    return result


def discover_tracked_sweden_organisation_numbers(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    seed: str | None = None,
    file_limit: int = DEFAULT_ARTIFACT_FILE_LIMIT,
    max_file_bytes: int = DEFAULT_ARTIFACT_FILE_BYTES,
) -> tuple[list[str], dict[str, Any]]:
    """Return bounded Swedish organisation numbers already known to the engine."""
    if file_limit < 1 or max_file_bytes < 1:
        raise ValueError("artifact scan bounds must be positive")

    numbers = _org_numbers_from_seed(seed)
    seed_count = len(numbers)
    target = _target_spec(manifest, "SE")
    scanned_files = 0
    skipped_large_files = 0
    invalid_json_files = 0
    artifact_dir: Path | None = None

    if target is not None:
        raw_dir = _compact(target.get("artifact_dir"))
        if raw_dir:
            artifact_dir = Path(root) / raw_dir
            if artifact_dir.exists():
                for path in sorted(artifact_dir.rglob("*.json"))[:file_limit]:
                    try:
                        size = path.stat().st_size
                    except OSError:
                        invalid_json_files += 1
                        continue
                    if size > max_file_bytes:
                        skipped_large_files += 1
                        continue
                    try:
                        payload = json.loads(path.read_text(encoding="utf-8"))
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                        invalid_json_files += 1
                        continue
                    scanned_files += 1
                    numbers.update(_walk_org_numbers(payload))

    ordered = sorted(numbers)
    return ordered, {
        "seed_organisation_count": seed_count,
        "artifact_organisation_count": max(0, len(ordered) - seed_count),
        "tracked_organisation_count": len(ordered),
        "artifact_dir": artifact_dir.as_posix() if artifact_dir else None,
        "artifact_json_files_scanned": scanned_files,
        "artifact_json_files_skipped_large": skipped_large_files,
        "artifact_json_files_invalid": invalid_json_files,
    }


def _organisation_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = payload.get("organisationer")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise RuntimeError("Bolagsverket response omitted organisationer list")
    return [row for row in rows if isinstance(row, Mapping)]


def _company_name(row: Mapping[str, Any]) -> str | None:
    names = row.get("organisationsnamn")
    if not isinstance(names, Mapping):
        return None
    items = names.get("organisationsnamnLista")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return None
    fallback: str | None = None
    for item in items:
        if not isinstance(item, Mapping):
            continue
        name = _compact(item.get("namn"))
        if not name:
            continue
        fallback = fallback or name
        name_type = item.get("organisationsnamntyp")
        code = _compact(name_type.get("kod")) if isinstance(name_type, Mapping) else ""
        if code == "FORETAGSNAMN":
            return name
    return fallback


def _sni_items(row: Mapping[str, Any]) -> list[dict[str, str]]:
    branch = row.get("naringsgrenOrganisation")
    if not isinstance(branch, Mapping):
        return []
    raw_items = branch.get("sni")
    if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
        return []
    result: list[dict[str, str]] = []
    for item in raw_items:
        if not isinstance(item, Mapping):
            continue
        code = re.sub(r"\D", "", _compact(item.get("kod")))
        text = _compact(item.get("klartext"))
        if code or text:
            result.append({"code": code, "text": text})
    return result


def _organisation_text(row: Mapping[str, Any]) -> str:
    values: list[str] = []
    name = _company_name(row)
    if name:
        values.append(name)
    description = row.get("verksamhetsbeskrivning")
    if isinstance(description, Mapping):
        values.append(_compact(description.get("beskrivning")))
    for item in _sni_items(row):
        values.append(item["text"])
    return " ".join(value for value in values if value).casefold()


def _is_clothing_organisation(row: Mapping[str, Any]) -> bool:
    for item in _sni_items(row):
        if any(item["code"].startswith(prefix) for prefix in _CLOTHING_SNI_PREFIXES):
            return True
    text = _organisation_text(row)
    return any(term.casefold() in text for term in _CLOTHING_TERMS)


def _legal_events(row: Mapping[str, Any]) -> list[dict[str, str | None]]:
    branch: object = None
    for key in (
        "pagaendeAvvecklingsEllerOmstruktureringsforfarande",
        "pagandeAvvecklingsEllerOmstruktureringsforfarande",
        "pågåendeAvvecklingsEllerOmstruktureringsförfarande",
    ):
        if key in row:
            branch = row.get(key)
            break
    if not isinstance(branch, Mapping):
        return []

    raw_items: object = None
    for key in (
        "pagaendeAvvecklingsEllerOmstruktureringsforfarandeLista",
        "pagandeAvvecklingsEllerOmstruktureringsforfarandeLista",
        "pågåendeAvvecklingsEllerOmstruktureringsförfarandeLista",
    ):
        if key in branch:
            raw_items = branch.get(key)
            break
    if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
        return []

    result: list[dict[str, str | None]] = []
    for item in raw_items:
        if not isinstance(item, Mapping):
            continue
        code = _compact(item.get("kod")).upper()
        text = _compact(item.get("klartext"))
        folded = text.casefold()
        if not code and not text:
            continue
        if code not in _LEGAL_CODE_KIND and not any(term in folded for term in _LEGAL_STATUS_TERMS):
            continue
        result.append(
            {
                "code": code or "UNKNOWN",
                "text": text or _LEGAL_CODE_KIND.get(code, code),
                "from_date": _compact(item.get("fromDatum")) or None,
            }
        )
    return result


def _parse_event_date(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(f"{text}T00:00:00+00:00")
        except ValueError:
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _signal_for_event(
    row: Mapping[str, Any],
    *,
    requested_org_number: str,
    event: Mapping[str, str | None],
    observed_at: datetime,
    source_url: str,
) -> MarketSignalRecord:
    identity = row.get("organisationsidentitet")
    returned_org_number = (
        _compact(identity.get("identitetsbeteckning"))
        if isinstance(identity, Mapping)
        else ""
    )
    org_number = re.sub(r"\D", "", returned_org_number) or requested_org_number
    company = _company_name(row) or f"Organisation {org_number}"
    code = _compact(event.get("code")).upper() or "UNKNOWN"
    legal_text = _compact(event.get("text")) or code
    from_date = _compact(event.get("from_date")) or "unknown-date"
    digest = sha256(f"SE|{org_number}|{code}|{from_date}".encode("utf-8")).hexdigest()[:24]
    sni = _sni_items(row)
    event_date = _parse_event_date(_compact(event.get("from_date")) or None)
    evidence_value = json.dumps(
        {
            "organisation_number": org_number,
            "company_name": company,
            "legal_status_code": code,
            "legal_status_text": legal_text,
            "from_date": event.get("from_date"),
            "sni": sni,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return MarketSignalRecord(
        signal_id=f"bolagsverket-valued-data:{digest}",
        signal_type=MarketSignalType.INSOLVENCY_OR_LIQUIDATION,
        value=f"{legal_text}: {company}",
        source="Bolagsverket Värdefulla datamängder",
        observed_at=observed_at,
        confidence=1.0,
        source_country="SE",
        source_url=source_url,
        title=f"{company} — {legal_text}",
        company_name=company,
        seller_name=None,
        location=None,
        first_observed_at=observed_at,
        latest_observed_at=observed_at,
        event_date=event_date,
        evidence=[
            Evidence(
                evidence_type="OFFICIAL_SWEDISH_COMPANY_STATUS",
                value=evidence_value,
                source_url=source_url,
                captured_at=observed_at,
                verified=True,
                metadata={
                    "organisation_number": org_number,
                    "legal_status_code": code,
                    "legal_status_text": legal_text,
                    "from_date": event.get("from_date"),
                    "sni_codes": [item["code"] for item in sni],
                },
            )
        ],
        related_opportunity_id=None,
        status=MarketSignalStatus.WATCH,
        metadata={
            "official_register": True,
            "signal_only": True,
            "organisation_number": org_number,
            "requested_organisation_number": requested_org_number,
            "legal_status_code": code,
            "legal_status_text": legal_text,
            "from_date": event.get("from_date"),
            "sni": sni,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        },
    )


def collect_sweden_valuable_dataset_status_signals(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at: datetime,
    environment: Mapping[str, str] | None = None,
    organisation_limit: int = DEFAULT_ORGANISATION_LIMIT,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    token_post: TokenPoster = _default_token_post,
    api_post: ApiPoster = _default_api_post,
) -> dict[str, Any]:
    """Verify tracked Swedish companies against the official valuable-data API."""
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    observed_at = observed_at.astimezone(timezone.utc)
    if not 1 <= organisation_limit <= 50:
        raise ValueError("organisation_limit must be between 1 and 50")

    env: Mapping[str, str] = environment if environment is not None else os.environ
    token_url = _compact(env.get("BOLAGSVERKET_TOKEN_URL")) or BOLAGSVERKET_TOKEN_URL
    base_url = _compact(env.get("BOLAGSVERKET_BASE_URL")) or BOLAGSVERKET_BASE_URL
    source_url = f"{base_url.rstrip('/')}/organisationer"
    tracked, discovery = discover_tracked_sweden_organisation_numbers(
        manifest,
        root=root,
        seed=env.get("BOLAGSVERKET_SE_ORGANISATION_NUMBERS"),
    )
    client_id = _compact(env.get("BOLAGSVERKET_CLIENT_ID"))
    client_secret = _compact(env.get("BOLAGSVERKET_CLIENT_SECRET"))
    missing_configuration: list[str] = []
    if not client_id:
        missing_configuration.append("BOLAGSVERKET_CLIENT_ID")
    if not client_secret:
        missing_configuration.append("BOLAGSVERKET_CLIENT_SECRET")
    if not tracked:
        missing_configuration.append(
            "BOLAGSVERKET_SE_ORGANISATION_NUMBERS_OR_ARTIFACT_ORG_NUMBERS"
        )

    common: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_key": "BOLAGSVERKET_VALUABLE_DATASETS_STATUS",
        "source_name": "Bolagsverket Värdefulla datamängder",
        "source_country": "SE",
        "generated_at": _iso_utc(observed_at),
        "access_mode": "OFFICIAL_OAUTH_REST_API",
        "api_endpoint": source_url,
        "token_endpoint_host": urlparse(token_url).hostname,
        "oauth_scope": BOLAGSVERKET_SCOPE,
        "organisation_limit": organisation_limit,
        "credentials_configured": bool(client_id and client_secret),
        **discovery,
        **_safety_payload(),
    }

    if missing_configuration:
        return {
            **common,
            "status": "BLOCKED_CONFIGURATION",
            "block_reason": "MISSING_REQUIRED_CONFIGURATION",
            "missing_configuration": missing_configuration,
            "checked_organisation_count": 0,
            "retrieved_record_count": 0,
            "candidate_entity_count": 0,
            "accepted_signal_count": 0,
            "rejected_result_count": 0,
            "non_clothing_count": 0,
            "no_legal_status_count": 0,
            "errors": [],
            "signals": [],
        }

    if not _official_https_url(token_url) or not _official_https_url(source_url):
        return {
            **common,
            "status": "BLOCKED_CONFIGURATION",
            "block_reason": "NON_OFFICIAL_API_URL",
            "missing_configuration": [],
            "checked_organisation_count": 0,
            "retrieved_record_count": 0,
            "candidate_entity_count": 0,
            "accepted_signal_count": 0,
            "rejected_result_count": 0,
            "non_clothing_count": 0,
            "no_legal_status_count": 0,
            "errors": ["Bolagsverket URLs must remain on official HTTPS hosts."],
            "signals": [],
        }

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
        return {
            **common,
            "status": "BLOCKED_AUTHENTICATION",
            "block_reason": "OAUTH_TOKEN_REQUEST_FAILED",
            "missing_configuration": [],
            "checked_organisation_count": 0,
            "retrieved_record_count": 0,
            "candidate_entity_count": 0,
            "accepted_signal_count": 0,
            "rejected_result_count": 0,
            "non_clothing_count": 0,
            "no_legal_status_count": 0,
            "errors": [f"{type(exc).__name__}: {exc}"],
            "signals": [],
        }

    selected = tracked[:organisation_limit]
    truncated = len(tracked) > len(selected)
    signals: MutableMapping[str, dict[str, Any]] = {}
    api_errors: list[str] = []
    retrieved_rows = 0
    checked = 0
    legal_candidates = 0
    rejected = 0
    non_clothing = 0
    no_legal_status = 0

    for org_number in selected:
        checked += 1
        request_id = str(uuid4())
        try:
            payload = api_post(
                source_url,
                {"identitetsbeteckning": org_number},
                {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                    "X-Request-Id": request_id,
                    "User-Agent": (
                        "opportunity-engine/sweden-valuable-datasets-status-feed "
                        "(+https://github.com/Hindawi44/opportunity-engine)"
                    ),
                },
                timeout,
            )
            rows = _organisation_rows(payload)
        except Exception as exc:
            api_errors.append(f"{org_number}: {type(exc).__name__}: {exc}")
            continue

        retrieved_rows += len(rows)
        for row in rows:
            events = _legal_events(row)
            if not events:
                no_legal_status += 1
                rejected += 1
                continue
            legal_candidates += 1
            if not _is_clothing_organisation(row):
                non_clothing += 1
                rejected += 1
                continue
            for event in events:
                signal = _signal_for_event(
                    row,
                    requested_org_number=org_number,
                    event=event,
                    observed_at=observed_at,
                    source_url=source_url,
                )
                signals[signal.signal_id] = signal.model_dump(mode="json")

    complete = not truncated and not api_errors
    if not complete:
        status = "PARTIAL_RETRIEVAL" if checked else "BLOCKED_DIRECT_ACCESS"
    else:
        status = "SUCCESS" if signals else "VALID_ZERO"

    return {
        **common,
        "status": status,
        "block_reason": None,
        "missing_configuration": [],
        "tracked_organisation_numbers": tracked,
        "checked_organisation_numbers": selected,
        "checked_organisation_count": checked,
        "retrieval_complete": complete,
        "organisation_limit_reached": truncated,
        "remaining_organisation_count": max(0, len(tracked) - len(selected)),
        "retrieved_record_count": retrieved_rows,
        "candidate_entity_count": legal_candidates,
        "accepted_signal_count": len(signals),
        "rejected_result_count": rejected,
        "non_clothing_count": non_clothing,
        "no_legal_status_count": no_legal_status,
        "errors": api_errors,
        "signals": [signals[key] for key in sorted(signals)],
    }


def collect_manifest_official_signals_with_sweden_status(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at: datetime | None = None,
    environment: Mapping[str, str] | None = None,
    json_get: JsonGetter = _default_json_get,
    text_get: TextGetter = _default_text_get,
    token_post: TokenPoster = _default_token_post,
    api_post: ApiPoster = _default_api_post,
) -> dict[str, Any]:
    """Collect Norway, Sweden, and Germany with the official Sweden API adapter."""
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    reports = [
        collect_brreg_update_id_cursor_signals(observed_at=now, json_get=json_get),
        collect_sweden_valuable_dataset_status_signals(
            manifest,
            root=root,
            observed_at=now,
            environment=environment,
            token_post=token_post,
            api_post=api_post,
        ),
        probe_german_insolvency_direct_access(observed_at=now, text_get=text_get),
    ]
    root_path = Path(root)
    for report in reports:
        report["schema_version"] = SCHEMA_VERSION
        market_code = _compact(report.get("source_country")).upper()
        target = _target_spec(manifest, market_code)
        if target is None:
            report["status"] = "BLOCKED_CONFIGURATION"
            report.setdefault("errors", []).append(
                "No checkpoint artifact directory exists for this market."
            )
            continue
        artifact_dir = root_path / _compact(target.get("artifact_dir"))
        report_path = artifact_dir / _compact(
            target.get("market_signal_report_file")
            or "market-signal-report.json"
        )
        report["stored_signal_count"] = _write_merged_report(report_path, report)
        report["artifact_path"] = report_path.relative_to(root_path).as_posix()

    status_counts: dict[str, int] = {}
    for report in reports:
        status = _compact(report.get("status")).upper() or "UNKNOWN"
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "retrieval_transport": "DIRECT_OFFICIAL_SOURCE",
        "market_coverage": ["NO", "SE", "DE"],
        "source_count": len(reports),
        "status_counts": status_counts,
        "sources": reports,
        "signal_count": sum(
            int(report.get("accepted_signal_count") or 0)
            for report in reports
        ),
        **_safety_payload(),
    }
