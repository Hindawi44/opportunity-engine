"""Direct official-source adapters for early clothing-market signals.

Norway uses the documented Brønnøysundregistrene open-data REST API. Sweden
and Germany use bounded direct-access probes against their official portals and
report interactive access controls truthfully; this module never bypasses a
challenge, reverse engineers a private API, contacts a company, bids, buys,
reserves, pays, or converts a signal into an opportunity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlencode, urlparse

import requests

from opportunity_engine.market_intelligence import (
    MarketSignalRecord,
    MarketSignalStatus,
    MarketSignalType,
)
from opportunity_engine.unified_models import Evidence


SCHEMA_VERSION = "direct-official-source-adapters-1.0"
DEFAULT_TIMEOUT_SECONDS = 25.0
DEFAULT_LOOKBACK_DAYS = 3
DEFAULT_UPDATE_LIMIT = 500
DEFAULT_ENTITY_FETCH_LIMIT = 80
DEFAULT_MAX_RESPONSE_BYTES = 5_000_000

BRREG_UPDATES_URL = (
    "https://data.brreg.no/enhetsregisteret/api/oppdateringer/enheter"
)
BRREG_ENTITY_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}"
POIT_PORTAL_URL = "https://poit.bolagsverket.se/poit-app/"
GERMAN_INSOLVENCY_SEARCH_URL = (
    "https://neu.insolvenzbekanntmachungen.de/ap/suche.jsf"
)

TARGET_SOURCE_BY_MARKET = {
    "NO": "Auksjonen.no",
    "SE": "Blinto",
    "DE": "Riegermann",
}

_BRREG_STATUS_PATH_MARKERS = (
    "/konkurs",
    "/konkursdato",
    "/underkonkursbehandling",
    "/underavvikling",
    "/underavviklingdato",
    "/undertvangsavviklingellertvangsopplosning",
    "/tvangsavviklet",
    "/tvangsopplost",
)
_BRREG_CLOTHING_NACE_PREFIXES = ("14", "46.42", "47.71")
_BRREG_CLOTHING_TERMS = (
    "klær",
    "klesbutikk",
    "kleshandel",
    "bekledning",
    "tekstil",
    "mote",
    "arbeidstøy",
    "arbeidsklær",
    "uniform",
    "konfeksjon",
)
_BRREG_EVENT_DATE_FIELDS = (
    "konkursdato",
    "underAvviklingDato",
    "tvangsavvikletPgaManglendeSlettingDato",
    "tvangsopplostPgaManglendeDagligLederDato",
    "tvangsopplostPgaManglendeRevisorDato",
    "tvangsopplostPgaManglendeRegnskapDato",
    "tvangsopplostPgaMangelfulltStyreDato",
)
_POIT_CHALLENGE_MARKERS = (
    "please enable javascript",
    "testing whether you are a human visitor",
    "support id",
    "what code is in the image",
    "captcha",
)
_GERMAN_INTERACTIVE_MARKERS = (
    "javax.faces.viewstate",
    "suche nach veröffentlichungen",
    "firma/nachname",
    "datum der veröffentlichung",
)

JsonGetter = Callable[[str, float, Mapping[str, str]], Any]
TextGetter = Callable[[str, float, Mapping[str, str]], "DirectTextResponse"]


@dataclass(frozen=True, slots=True)
class DirectTextResponse:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str | None
    response_bytes: int
    text: str


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _fold(value: object) -> str:
    text = _compact(value).casefold()
    return text.translate(
        str.maketrans(
            {
                "å": "a",
                "ä": "a",
                "æ": "ae",
                "ö": "o",
                "ø": "o",
                "ü": "u",
                "é": "e",
                "è": "e",
                "ß": "ss",
            }
        )
    )


def _host_is(url: str, expected_domain: str) -> bool:
    host = (urlparse(url).hostname or "").casefold().rstrip(".")
    domain = expected_domain.casefold().rstrip(".")
    return host == domain or host.endswith(f".{domain}")


def _default_json_get(
    url: str,
    timeout: float,
    headers: Mapping[str, str],
) -> Any:
    response = requests.get(
        url,
        timeout=timeout,
        headers=dict(headers),
        allow_redirects=True,
    )
    response.raise_for_status()
    if not _host_is(str(response.url), "brreg.no"):
        raise RuntimeError("Brreg API redirected outside the official domain")
    raw = bytes(response.content)
    if len(raw) > DEFAULT_MAX_RESPONSE_BYTES:
        raise RuntimeError("Brreg API response exceeded the bounded size limit")
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("Brreg API returned invalid JSON") from exc


def _default_text_get(
    url: str,
    timeout: float,
    headers: Mapping[str, str],
) -> DirectTextResponse:
    response = requests.get(
        url,
        timeout=timeout,
        headers=dict(headers),
        allow_redirects=True,
    )
    response.raise_for_status()
    raw = bytes(response.content)
    if len(raw) > DEFAULT_MAX_RESPONSE_BYTES:
        raise RuntimeError("Official portal response exceeded the bounded size limit")
    encoding = response.encoding or "utf-8"
    return DirectTextResponse(
        requested_url=url,
        final_url=str(response.url),
        status_code=int(response.status_code),
        content_type=_compact(response.headers.get("content-type")) or None,
        response_bytes=len(raw),
        text=raw.decode(encoding, errors="replace"),
    )


def _safety_payload() -> dict[str, bool]:
    return {
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _iso_utc(value: datetime) -> str:
    normalized = value
    if normalized.tzinfo is None or normalized.utcoffset() is None:
        normalized = normalized.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).isoformat()


def _brreg_updates(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        raise RuntimeError("Brreg updates response must be a JSON object")
    embedded = payload.get("_embedded")
    if not isinstance(embedded, Mapping):
        return []
    for key in ("oppdaterteEnheter", "oppdateringer", "enheter"):
        value = embedded.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _truthy_change_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = _fold(value)
    return text not in {"", "false", "0", "null", "none"}


def _update_has_relevant_status_change(update: Mapping[str, Any]) -> bool:
    changes = update.get("endringer")
    if not isinstance(changes, Sequence) or isinstance(changes, (str, bytes)):
        return False
    for change in changes:
        if not isinstance(change, Mapping):
            continue
        path = _fold(change.get("path"))
        if not any(marker in path for marker in _BRREG_STATUS_PATH_MARKERS):
            continue
        operation = _fold(change.get("op"))
        if operation == "remove":
            continue
        if _truthy_change_value(change.get("value")):
            return True
    return False


def _brreg_entity_text(entity: Mapping[str, Any]) -> str:
    values: list[str] = [_compact(entity.get("navn"))]
    for field in ("aktivitet", "vedtektsfestetFormaal"):
        raw = entity.get(field)
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            values.extend(_compact(item) for item in raw)
        elif raw:
            values.append(_compact(raw))
    for field in ("naeringskode1", "naeringskode2", "naeringskode3"):
        raw = entity.get(field)
        if isinstance(raw, Mapping):
            values.append(_compact(raw.get("beskrivelse")))
    return " ".join(value for value in values if value)


def _brreg_nace_codes(entity: Mapping[str, Any]) -> tuple[str, ...]:
    result: list[str] = []
    for field in ("naeringskode1", "naeringskode2", "naeringskode3"):
        raw = entity.get(field)
        if not isinstance(raw, Mapping):
            continue
        code = _compact(raw.get("kode"))
        if code and code not in result:
            result.append(code)
    return tuple(result)


def _brreg_entity_is_clothing(entity: Mapping[str, Any]) -> bool:
    for code in _brreg_nace_codes(entity):
        normalized = code.replace(",", ".")
        if any(normalized.startswith(prefix) for prefix in _BRREG_CLOTHING_NACE_PREFIXES):
            return True
    text = _fold(_brreg_entity_text(entity))
    return any(_fold(term) in text for term in _BRREG_CLOTHING_TERMS)


def _brreg_event_kind(entity: Mapping[str, Any]) -> str | None:
    if (
        entity.get("konkurs") is True
        or entity.get("underKonkursbehandling") is True
        or _compact(entity.get("konkursdato"))
    ):
        return "KONKURS"
    if entity.get("underTvangsavviklingEllerTvangsopplosning") is True or any(
        _compact(entity.get(field))
        for field in _BRREG_EVENT_DATE_FIELDS
        if field.startswith("tvangs")
    ):
        return "TVANGSAVVIKLING_ELLER_TVANGSOPPLOSNING"
    if entity.get("underAvvikling") is True or _compact(
        entity.get("underAvviklingDato")
    ):
        return "AVVIKLING"
    return None


def _parse_event_date(value: object) -> datetime | None:
    text = _compact(value)
    if not text:
        return None
    try:
        parsed_date = date.fromisoformat(text[:10])
    except ValueError:
        return None
    return datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)


def _brreg_event_date(entity: Mapping[str, Any]) -> datetime | None:
    candidates = [
        parsed
        for parsed in (_parse_event_date(entity.get(field)) for field in _BRREG_EVENT_DATE_FIELDS)
        if parsed is not None
    ]
    return max(candidates) if candidates else None


def _address_text(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    address = value.get("adresse")
    parts: list[str] = []
    if isinstance(address, Sequence) and not isinstance(address, (str, bytes)):
        parts.extend(_compact(item) for item in address if _compact(item))
    elif address:
        parts.append(_compact(address))
    for field in ("postnummer", "poststed", "kommune"):
        item = _compact(value.get(field))
        if item:
            parts.append(item)
    return ", ".join(parts) or None


def _brreg_signal(
    entity: Mapping[str, Any],
    *,
    observed_at: datetime,
    update: Mapping[str, Any],
) -> MarketSignalRecord | None:
    event_kind = _brreg_event_kind(entity)
    orgnr = _compact(entity.get("organisasjonsnummer"))
    name = _compact(entity.get("navn"))
    if not event_kind or not orgnr or not name or not _brreg_entity_is_clothing(entity):
        return None

    labels = {
        "KONKURS": "Konkurs",
        "AVVIKLING": "Avvikling",
        "TVANGSAVVIKLING_ELLER_TVANGSOPPLOSNING": (
            "Tvangsavvikling eller tvangsoppløsning"
        ),
    }
    label = labels[event_kind]
    source_url = BRREG_ENTITY_URL.format(orgnr=orgnr)
    event_date = _brreg_event_date(entity)
    nace_codes = list(_brreg_nace_codes(entity))
    evidence_value = f"{name} ({orgnr}) — {label}"
    evidence = Evidence(
        evidence_type="OFFICIAL_REGISTER_STATUS",
        value=evidence_value,
        source_url=source_url,
        captured_at=observed_at,
        verified=True,
        metadata={
            "official_api": "Brønnøysundregistrene Enhetsregisteret",
            "event_kind": event_kind,
            "update_id": update.get("oppdateringsid"),
            "nace_codes": nace_codes,
        },
    )
    return MarketSignalRecord(
        signal_id=(
            f"official-notice:no:brreg:{orgnr}:{event_kind.casefold()}"
        ),
        signal_type=MarketSignalType.INSOLVENCY_OR_LIQUIDATION,
        value=evidence_value[:500],
        source="Brønnøysundregistrene Enhetsregisteret API",
        observed_at=observed_at,
        confidence=0.96,
        source_country="NO",
        source_url=source_url,
        title=f"{label}: {name}",
        company_name=name,
        seller_name=None,
        location=(
            _address_text(entity.get("forretningsadresse"))
            or _address_text(entity.get("postadresse"))
        ),
        first_observed_at=observed_at,
        latest_observed_at=observed_at,
        event_date=event_date,
        evidence=[evidence],
        related_opportunity_id=None,
        status=MarketSignalStatus.WATCH,
        metadata={
            "signal_only": True,
            "source_role": "DIRECT_OFFICIAL_API",
            "official_source_key": "BRREG_ENHETSREGISTERET_API",
            "organisation_number": orgnr,
            "event_kind": event_kind,
            "nace_codes": nace_codes,
            "update_id": update.get("oppdateringsid"),
        },
    )


def collect_brreg_direct_signals(
    *,
    observed_at: datetime,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    update_limit: int = DEFAULT_UPDATE_LIMIT,
    entity_fetch_limit: int = DEFAULT_ENTITY_FETCH_LIMIT,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    json_get: JsonGetter = _default_json_get,
) -> dict[str, Any]:
    if lookback_days < 1:
        raise ValueError("lookback_days must be at least 1")
    if not 1 <= update_limit <= 10_000:
        raise ValueError("update_limit must be between 1 and 10000")
    if entity_fetch_limit < 1:
        raise ValueError("entity_fetch_limit must be positive")

    cutoff = observed_at.astimezone(timezone.utc) - timedelta(days=lookback_days)
    params = urlencode(
        {
            "dato": cutoff.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "updatedBefore": observed_at.astimezone(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.000Z"
            ),
            "includeChanges": "true",
            "page": "0",
            "size": str(update_limit),
            "sort": "id,DESC",
        }
    )
    updates_url = f"{BRREG_UPDATES_URL}?{params}"
    headers = {
        "Accept": "application/vnd.brreg.enhetsregisteret.oppdatering.enhet.v1+json",
        "User-Agent": (
            "opportunity-engine/direct-official-source-adapters "
            "(+https://github.com/Hindawi44/opportunity-engine)"
        ),
    }

    try:
        payload = json_get(updates_url, timeout, headers)
        updates = _brreg_updates(payload)
    except Exception as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "source_key": "BRREG_ENHETSREGISTERET_API",
            "source_name": "Brønnøysundregistrene Enhetsregisteret API",
            "source_country": "NO",
            "generated_at": _iso_utc(observed_at),
            "status": "BLOCKED_DIRECT_ACCESS",
            "access_mode": "DIRECT_OFFICIAL_REST_API",
            "errors": [f"{type(exc).__name__}: {exc}"],
            "signals": [],
            "retrieved_record_count": 0,
            "candidate_entity_count": 0,
            "entity_fetch_count": 0,
            "accepted_signal_count": 0,
            "rejected_result_count": 0,
            **_safety_payload(),
        }

    candidates: dict[str, dict[str, Any]] = {}
    for update in updates:
        orgnr = _compact(update.get("organisasjonsnummer"))
        if orgnr and _update_has_relevant_status_change(update):
            candidates.setdefault(orgnr, update)

    signals: dict[str, dict[str, Any]] = {}
    rejected = 0
    entity_fetch_count = 0
    entity_errors: list[str] = []
    entity_headers = {
        "Accept": "application/vnd.brreg.enhetsregisteret.enhet.v2+json",
        "User-Agent": headers["User-Agent"],
    }
    for orgnr, update in list(candidates.items())[:entity_fetch_limit]:
        entity_fetch_count += 1
        try:
            entity = json_get(
                BRREG_ENTITY_URL.format(orgnr=orgnr),
                timeout,
                entity_headers,
            )
            if not isinstance(entity, Mapping):
                raise RuntimeError("Brreg entity response must be a JSON object")
        except Exception as exc:
            entity_errors.append(f"{orgnr}: {type(exc).__name__}: {exc}")
            continue
        signal = _brreg_signal(entity, observed_at=observed_at, update=update)
        if signal is None:
            rejected += 1
            continue
        signals[signal.signal_id] = signal.model_dump(mode="json")

    status = "SUCCESS" if signals else "VALID_ZERO"
    if candidates and entity_fetch_count and entity_errors and not signals:
        status = "BLOCKED_DIRECT_ACCESS"
    return {
        "schema_version": SCHEMA_VERSION,
        "source_key": "BRREG_ENHETSREGISTERET_API",
        "source_name": "Brønnøysundregistrene Enhetsregisteret API",
        "source_country": "NO",
        "generated_at": _iso_utc(observed_at),
        "status": status,
        "access_mode": "DIRECT_OFFICIAL_REST_API",
        "updates_url": updates_url,
        "lookback_days": lookback_days,
        "retrieved_record_count": len(updates),
        "candidate_entity_count": len(candidates),
        "entity_fetch_count": entity_fetch_count,
        "accepted_signal_count": len(signals),
        "rejected_result_count": rejected,
        "errors": entity_errors,
        "signals": [signals[key] for key in sorted(signals)],
        **_safety_payload(),
    }


def _probe_direct_portal(
    *,
    source_key: str,
    source_name: str,
    source_country: str,
    url: str,
    expected_domain: str,
    observed_at: datetime,
    challenge_markers: Sequence[str],
    interactive_markers: Sequence[str],
    text_get: TextGetter,
    timeout: float,
) -> dict[str, Any]:
    try:
        response = text_get(
            url,
            timeout,
            {
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": (
                    "opportunity-engine/direct-official-source-adapters "
                    "(+https://github.com/Hindawi44/opportunity-engine)"
                ),
            },
        )
        if not _host_is(response.final_url, expected_domain):
            raise RuntimeError("official portal redirected outside its official domain")
    except Exception as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "source_key": source_key,
            "source_name": source_name,
            "source_country": source_country,
            "generated_at": _iso_utc(observed_at),
            "status": "BLOCKED_DIRECT_ACCESS",
            "access_mode": "DIRECT_OFFICIAL_PORTAL_PROBE",
            "portal_url": url,
            "portal_reachable": False,
            "block_reason": "DIRECT_REQUEST_FAILED",
            "errors": [f"{type(exc).__name__}: {exc}"],
            "signals": [],
            "accepted_signal_count": 0,
            "retrieved_record_count": 0,
            **_safety_payload(),
        }

    folded = _fold(response.text)
    challenge = next(
        (marker for marker in challenge_markers if _fold(marker) in folded),
        None,
    )
    interactive = any(_fold(marker) in folded for marker in interactive_markers)
    reason = (
        "HUMAN_VERIFICATION_CHALLENGE"
        if challenge
        else "INTERACTIVE_SEARCH_WITHOUT_DOCUMENTED_PUBLIC_API"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "source_key": source_key,
        "source_name": source_name,
        "source_country": source_country,
        "generated_at": _iso_utc(observed_at),
        "status": "BLOCKED_DIRECT_ACCESS",
        "access_mode": "DIRECT_OFFICIAL_PORTAL_PROBE",
        "portal_url": url,
        "portal_reachable": True,
        "final_url": response.final_url,
        "http_status": response.status_code,
        "content_type": response.content_type,
        "response_bytes": response.response_bytes,
        "interactive_search_detected": interactive,
        "block_reason": reason,
        "challenge_marker": challenge,
        "errors": [],
        "signals": [],
        "accepted_signal_count": 0,
        "retrieved_record_count": 0,
        "no_bypass_attempted": True,
        **_safety_payload(),
    }


def probe_poit_direct_access(
    *,
    observed_at: datetime,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    text_get: TextGetter = _default_text_get,
) -> dict[str, Any]:
    return _probe_direct_portal(
        source_key="POIT_DIRECT_PORTAL",
        source_name="Post- och Inrikes Tidningar",
        source_country="SE",
        url=POIT_PORTAL_URL,
        expected_domain="poit.bolagsverket.se",
        observed_at=observed_at,
        challenge_markers=_POIT_CHALLENGE_MARKERS,
        interactive_markers=("post- och inrikes tidningar", "poit"),
        text_get=text_get,
        timeout=timeout,
    )


def probe_german_insolvency_direct_access(
    *,
    observed_at: datetime,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    text_get: TextGetter = _default_text_get,
) -> dict[str, Any]:
    return _probe_direct_portal(
        source_key="DE_INSOLVENZ_DIRECT_PORTAL",
        source_name="Insolvenzbekanntmachungen",
        source_country="DE",
        url=GERMAN_INSOLVENCY_SEARCH_URL,
        expected_domain="insolvenzbekanntmachungen.de",
        observed_at=observed_at,
        challenge_markers=("captcha", "human verification"),
        interactive_markers=_GERMAN_INTERACTIVE_MARKERS,
        text_get=text_get,
        timeout=timeout,
    )


def _target_spec(
    manifest: Mapping[str, Any], market_code: str
) -> Mapping[str, Any] | None:
    candidates = [
        item
        for item in manifest.get("sources") or []
        if isinstance(item, Mapping)
        and _compact(item.get("market_code")).upper() == market_code
    ]
    preferred = TARGET_SOURCE_BY_MARKET.get(market_code)
    if preferred:
        for item in candidates:
            if _compact(item.get("source_name") or item.get("source")) == preferred:
                return item
    return candidates[0] if candidates else None


def _load_existing_signals(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    raw = payload if isinstance(payload, list) else payload.get("signals", [])
    if not isinstance(raw, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        try:
            signal = MarketSignalRecord.model_validate(item)
        except Exception:
            continue
        result[signal.signal_id] = signal.model_dump(mode="json")
    return result


def _write_merged_report(path: Path, report: Mapping[str, Any]) -> int:
    signals = _load_existing_signals(path)
    for item in report.get("signals") or []:
        if not isinstance(item, Mapping):
            continue
        signal = MarketSignalRecord.model_validate(item)
        signals[signal.signal_id] = signal.model_dump(mode="json")
    payload = dict(report)
    payload["signals"] = [signals[key] for key in sorted(signals)]
    payload["stored_signal_count"] = len(payload["signals"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return len(payload["signals"])


def collect_manifest_direct_official_signals(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at: datetime | None = None,
    json_get: JsonGetter = _default_json_get,
    text_get: TextGetter = _default_text_get,
) -> dict[str, Any]:
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    reports = [
        collect_brreg_direct_signals(observed_at=now, json_get=json_get),
        probe_poit_direct_access(observed_at=now, text_get=text_get),
        probe_german_insolvency_direct_access(
            observed_at=now,
            text_get=text_get,
        ),
    ]
    root_path = Path(root)
    for report in reports:
        market_code = _compact(report.get("source_country")).upper()
        target = _target_spec(manifest, market_code)
        if target is None:
            report["status"] = "BLOCKED_DIRECT_ACCESS"
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
