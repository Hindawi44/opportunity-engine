"""Official Swedish clothing-liquidation company anchors from weekly bulk files.

This adapter joins SCB's primary SNI (Ng1) to Bolagsverket's current bankruptcy
or liquidation status. The result is a bounded company-name signal feed only.
It never creates an opportunity, changes Exa query budget, or bypasses the
existing Verification -> Multi-Hop -> Exact-Lot qualification path.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, Mapping
from urllib.parse import urlparse
import zipfile

import requests

from opportunity_engine.discovery.direct_official_source_adapters import (
    _compact,
    _iso_utc,
    _safety_payload,
    _target_spec,
    _write_merged_report,
)
from opportunity_engine.market_intelligence import (
    MarketSignalRecord,
    MarketSignalStatus,
    MarketSignalType,
)
from opportunity_engine.unified_models import Evidence


SCHEMA_VERSION = "sweden-official-clothing-liquidation-anchor-1.0"
SOURCE_NAME = "Bolagsverket Värdefulla datamängder"
BOLAGSVERKET_BULK_URL = (
    "https://vardefulla-datamangder.bolagsverket.se/bolagsverket/bolagsverket_bulkfil.zip"
)
SCB_BULK_URL = (
    "https://vardefulla-datamangder.bolagsverket.se/scb/scb_bulkfil.zip"
)
OFFICIAL_BULK_HOST = "vardefulla-datamangder.bolagsverket.se"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_DOWNLOAD_BYTES = 1_500_000_000
DEFAULT_MAX_UNCOMPRESSED_BYTES = 5_000_000_000
DEFAULT_SIGNAL_LIMIT = 20

# SNI 2025. Ng1 is the primary business activity in the official SCB bulk file.
# Keep V1 narrow: apparel manufacture, footwear manufacture, clothing/footwear
# wholesale and clothing retail. Textile/fabric codes are intentionally excluded
# because this bridge feeds CLOTHING_INVENTORY only.
CLOTHING_SNI_PREFIXES = ("14", "152", "4642", "4771")
CURRENT_LIQUIDATION_CODES = {
    "KK-AVOMFO": ("KK", "Konkurs"),
    "LI-AVOMFO": ("LI", "Likvidation"),
}

FileDownloader = Callable[[str, Path, float, int], int]


def _official_bulk_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname or "").casefold() == OFFICIAL_BULK_HOST


def _default_file_downloader(url: str, destination: Path, timeout: float, max_bytes: int) -> int:
    if not _official_bulk_url(url):
        raise RuntimeError("Swedish bulk URL must remain on the official Bolagsverket HTTPS host")
    with requests.get(
        url,
        stream=True,
        timeout=timeout,
        allow_redirects=True,
        headers={
            "Accept": "application/zip,application/octet-stream",
            "User-Agent": (
                "opportunity-engine/sweden-official-clothing-liquidation-anchor "
                "(+https://github.com/Hindawi44/opportunity-engine)"
            ),
        },
    ) as response:
        response.raise_for_status()
        final_url = str(response.url)
        if not _official_bulk_url(final_url):
            raise RuntimeError("Swedish bulk download redirected outside the official host")
        raw_length = _compact(response.headers.get("content-length"))
        if raw_length:
            try:
                content_length = int(raw_length)
            except ValueError:
                content_length = 0
            if content_length > max_bytes:
                raise RuntimeError("Swedish bulk download exceeded the bounded size limit")
        total = 0
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise RuntimeError("Swedish bulk download exceeded the bounded size limit")
                handle.write(chunk)
    return total


def _zip_text_reader(
    zip_path: Path,
    *,
    encoding: str,
    max_uncompressed_bytes: int,
) -> tuple[zipfile.ZipFile, io.TextIOWrapper]:
    archive = zipfile.ZipFile(zip_path)
    members = [
        item
        for item in archive.infolist()
        if not item.is_dir() and item.filename.casefold().endswith(".txt")
    ]
    if len(members) != 1:
        archive.close()
        raise RuntimeError("Official Swedish bulk ZIP must contain exactly one .txt data file")
    member = members[0]
    if member.file_size > max_uncompressed_bytes:
        archive.close()
        raise RuntimeError("Official Swedish bulk TXT exceeded the bounded uncompressed size limit")
    text = io.TextIOWrapper(archive.open(member, "r"), encoding=encoding, newline="")
    return archive, text


def _normalise_sni(value: object) -> str:
    return re.sub(r"\D", "", _compact(value))


def _scb_organisation_number(value: object) -> str | None:
    digits = re.sub(r"\D", "", _compact(value))
    if len(digits) != 12 or not digits.startswith("16"):
        return None
    organisation_number = digits[2:]
    return organisation_number if len(organisation_number) == 10 else None


def _bolagsverket_organisation_number(value: object) -> str | None:
    text = _compact(value)
    if not text:
        return None
    parts = text.split("$")
    digits = re.sub(r"\D", "", parts[0])
    if len(digits) != 10:
        return None
    if len(parts) > 1 and _compact(parts[1]).upper() not in {"", "ORGNR-IDORG"}:
        return None
    return digits


def _company_name(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    fallback: str | None = None
    for raw_item in text.split("|"):
        fields = raw_item.split("$")
        candidate = _compact(fields[0] if fields else "")
        if not candidate:
            continue
        fallback = fallback or candidate
        name_type = _compact(fields[1]).upper() if len(fields) > 1 else ""
        if name_type == "FORETAGSNAMN-ORGNAM":
            return candidate
    return fallback


def _liquidation_events(value: object) -> list[dict[str, str | None]]:
    text = str(value or "").strip()
    if not text:
        return []
    events: list[dict[str, str | None]] = []
    for raw_item in text.split("|"):
        fields = raw_item.split("$")
        code = _compact(fields[0]).upper() if fields else ""
        if code not in CURRENT_LIQUIDATION_CODES:
            continue
        short_code, default_text = CURRENT_LIQUIDATION_CODES[code]
        legal_text = _compact(fields[1]) if len(fields) > 1 else ""
        from_date = _compact(fields[2]) if len(fields) > 2 else ""
        events.append(
            {
                "source_code": code,
                "code": short_code,
                "text": legal_text or default_text,
                "from_date": from_date or None,
            }
        )
    return events


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


def _sni_rank(code: str) -> int:
    if code.startswith("4642"):
        return 0
    if code.startswith("4771"):
        return 1
    if code.startswith("14"):
        return 2
    if code.startswith("152"):
        return 3
    return 9


def _candidate_sort_key(item: Mapping[str, Any]) -> tuple[int, int, int, str, str]:
    event = item.get("event") or {}
    code = _compact(event.get("code")).upper() if isinstance(event, Mapping) else ""
    from_date = _compact(event.get("from_date")) if isinstance(event, Mapping) else ""
    try:
        date_key = -int(from_date.replace("-", "")[:8]) if from_date else 0
    except ValueError:
        date_key = 0
    return (
        0 if code == "KK" else 1,
        _sni_rank(_compact(item.get("sni_code"))),
        date_key,
        _compact(item.get("company_name")).casefold(),
        _compact(item.get("organisation_number")),
    )


def _collect_scb_clothing_companies(
    zip_path: Path,
    *,
    max_uncompressed_bytes: int,
) -> tuple[dict[str, dict[str, str]], dict[str, int]]:
    csv.field_size_limit(10_000_000)
    archive, text = _zip_text_reader(
        zip_path,
        encoding="iso-8859-1",
        max_uncompressed_bytes=max_uncompressed_bytes,
    )
    scanned = 0
    clothing: dict[str, dict[str, str]] = {}
    try:
        reader = csv.DictReader(text, delimiter="\t")
        headers = set(reader.fieldnames or [])
        missing = {"PeOrgNr", "Ng1"} - headers
        if missing:
            raise RuntimeError(f"SCB bulk file omitted required fields: {sorted(missing)}")
        for row in reader:
            scanned += 1
            org_number = _scb_organisation_number(row.get("PeOrgNr"))
            sni_code = _normalise_sni(row.get("Ng1"))
            if not org_number or not sni_code:
                continue
            if not any(sni_code.startswith(prefix) for prefix in CLOTHING_SNI_PREFIXES):
                continue
            clothing[org_number] = {
                "sni_code": sni_code,
                "scb_name": _compact(row.get("Namn") or row.get("Foretagsnamn")),
                "company_status": _compact(row.get("Ftgstat")),
            }
    finally:
        text.close()
        archive.close()
    return clothing, {
        "scb_rows_scanned": scanned,
        "scb_clothing_company_count": len(clothing),
    }


def _collect_bolagsverket_candidates(
    zip_path: Path,
    *,
    clothing_companies: Mapping[str, Mapping[str, str]],
    max_uncompressed_bytes: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    csv.field_size_limit(10_000_000)
    archive, text = _zip_text_reader(
        zip_path,
        encoding="utf-8-sig",
        max_uncompressed_bytes=max_uncompressed_bytes,
    )
    scanned = 0
    matched_rows = 0
    candidates: list[dict[str, Any]] = []
    try:
        reader = csv.DictReader(
            text,
            delimiter=";",
            quotechar='"',
            escapechar="\\",
        )
        headers = set(reader.fieldnames or [])
        required = {
            "organisationsidentitet",
            "organisationsnamn",
            "pagandeAvvecklingsEllerOmstruktureringsforfarande",
        }
        missing = required - headers
        if missing:
            raise RuntimeError(
                f"Bolagsverket bulk file omitted required fields: {sorted(missing)}"
            )
        for row in reader:
            scanned += 1
            org_number = _bolagsverket_organisation_number(row.get("organisationsidentitet"))
            if not org_number or org_number not in clothing_companies:
                continue
            events = _liquidation_events(
                row.get("pagandeAvvecklingsEllerOmstruktureringsforfarande")
            )
            if not events:
                continue
            company = _company_name(row.get("organisationsnamn"))
            if not company:
                continue
            matched_rows += 1
            scb = clothing_companies[org_number]
            for event in events:
                candidates.append(
                    {
                        "organisation_number": org_number,
                        "company_name": company,
                        "sni_code": _compact(scb.get("sni_code")),
                        "scb_name": _compact(scb.get("scb_name")),
                        "event": event,
                    }
                )
    finally:
        text.close()
        archive.close()
    return candidates, {
        "bolagsverket_rows_scanned": scanned,
        "bolagsverket_clothing_liquidation_row_count": matched_rows,
        "bolagsverket_clothing_liquidation_event_count": len(candidates),
    }


def _signal_from_candidate(
    candidate: Mapping[str, Any],
    *,
    observed_at: datetime,
) -> MarketSignalRecord:
    org_number = _compact(candidate.get("organisation_number"))
    company = _compact(candidate.get("company_name"))
    sni_code = _compact(candidate.get("sni_code"))
    event = candidate.get("event") or {}
    if not isinstance(event, Mapping):
        raise RuntimeError("Swedish bulk candidate omitted legal event")
    code = _compact(event.get("code")).upper()
    legal_text = _compact(event.get("text")) or code
    from_date = _compact(event.get("from_date")) or "unknown-date"
    digest = sha256(f"SE|BULK|{org_number}|{code}|{from_date}".encode("utf-8")).hexdigest()[:24]
    evidence_value = json.dumps(
        {
            "organisation_number": org_number,
            "company_name": company,
            "legal_status_code": code,
            "legal_status_text": legal_text,
            "from_date": event.get("from_date"),
            "sni": [{"code": sni_code, "source": "SCB Ng1 SNI 2025"}],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return MarketSignalRecord(
        signal_id=f"bolagsverket-bulk-clothing-anchor:{digest}",
        signal_type=MarketSignalType.INSOLVENCY_OR_LIQUIDATION,
        value=f"{legal_text}: {company}",
        source=SOURCE_NAME,
        observed_at=observed_at,
        confidence=1.0,
        source_country="SE",
        source_url=BOLAGSVERKET_BULK_URL,
        title=f"{company} — {legal_text}",
        company_name=company,
        seller_name=None,
        location=None,
        first_observed_at=observed_at,
        latest_observed_at=observed_at,
        event_date=_parse_event_date(_compact(event.get("from_date")) or None),
        evidence=[
            Evidence(
                evidence_type="OFFICIAL_SWEDISH_COMPANY_STATUS",
                value=evidence_value,
                source_url=BOLAGSVERKET_BULK_URL,
                captured_at=observed_at,
                verified=True,
                metadata={
                    "organisation_number": org_number,
                    "legal_status_code": code,
                    "legal_status_text": legal_text,
                    "from_date": event.get("from_date"),
                    "sni_code": sni_code,
                    "sni_source": "SCB Ng1 SNI 2025",
                    "bulk_join": True,
                },
            )
        ],
        related_opportunity_id=None,
        status=MarketSignalStatus.WATCH,
        metadata={
            "official_register": True,
            "signal_only": True,
            "anchor_only": True,
            "official_bulk_anchor_v1": True,
            "organisation_number": org_number,
            "legal_status_code": code,
            "legal_status_text": legal_text,
            "from_date": event.get("from_date"),
            "sni": [{"code": sni_code, "source": "SCB Ng1 SNI 2025"}],
            "scb_name": _compact(candidate.get("scb_name")) or None,
            "promotion_to_opportunity_allowed": False,
            "anchor_is_qualification_evidence": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase": False,
            "automatic_payment": False,
        },
    )


def collect_sweden_official_clothing_liquidation_anchors(
    *,
    observed_at: datetime | None = None,
    signal_limit: int = DEFAULT_SIGNAL_LIMIT,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    max_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES,
    downloader: FileDownloader = _default_file_downloader,
) -> dict[str, Any]:
    """Join weekly SCB/Bolagsverket bulk data into bounded company-anchor signals."""
    if not 1 <= signal_limit <= DEFAULT_SIGNAL_LIMIT:
        raise ValueError(f"signal_limit must be between 1 and {DEFAULT_SIGNAL_LIMIT}")
    if max_download_bytes < 1 or max_uncompressed_bytes < 1:
        raise ValueError("bulk size limits must be positive")
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    common: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_key": "OFFICIAL_SWEDISH_CLOTHING_LIQUIDATION_BULK_ANCHOR_V1",
        "source_name": SOURCE_NAME,
        "source_country": "SE",
        "generated_at": _iso_utc(now),
        "access_mode": "OFFICIAL_WEEKLY_BULK_FILE_JOIN",
        "bolagsverket_bulk_url": BOLAGSVERKET_BULK_URL,
        "scb_bulk_url": SCB_BULK_URL,
        "sni_basis": "SCB_NG1_SNI_2025",
        "clothing_sni_prefixes": list(CLOTHING_SNI_PREFIXES),
        "legal_status_codes": sorted(CURRENT_LIQUIDATION_CODES),
        "signal_limit": signal_limit,
        "signal_only": True,
        "anchor_only": True,
        "anchor_is_qualification_evidence": False,
        "promotion_to_opportunity_allowed": False,
        "new_runtime_created": False,
        "search_requests_made": 0,
        "exa_query_budget_delta": 0,
        **_safety_payload(),
    }

    try:
        with tempfile.TemporaryDirectory(prefix="sweden-official-bulk-") as temp_dir:
            temp = Path(temp_dir)
            scb_path = temp / "scb_bulkfil.zip"
            bolags_path = temp / "bolagsverket_bulkfil.zip"
            scb_download_bytes = downloader(SCB_BULK_URL, scb_path, timeout, max_download_bytes)
            clothing, scb_stats = _collect_scb_clothing_companies(
                scb_path,
                max_uncompressed_bytes=max_uncompressed_bytes,
            )
            bolags_download_bytes = downloader(
                BOLAGSVERKET_BULK_URL,
                bolags_path,
                timeout,
                max_download_bytes,
            )
            candidates, bolags_stats = _collect_bolagsverket_candidates(
                bolags_path,
                clothing_companies=clothing,
                max_uncompressed_bytes=max_uncompressed_bytes,
            )
    except Exception as exc:
        return {
            **common,
            "status": "FAILED_RETRIEVAL",
            "retrieval_complete": False,
            "accepted_signal_count": 0,
            "candidate_anchor_count": 0,
            "signals": [],
            "errors": [f"{type(exc).__name__}: {exc}"],
        }

    ordered = sorted(candidates, key=_candidate_sort_key)
    selected = ordered[:signal_limit]
    signals: dict[str, dict[str, Any]] = {}
    for candidate in selected:
        signal = _signal_from_candidate(candidate, observed_at=now)
        signals[signal.signal_id] = signal.model_dump(mode="json")

    status = "SUCCESS" if signals else "VALID_ZERO"
    return {
        **common,
        "status": status,
        "retrieval_complete": True,
        "scb_download_bytes": scb_download_bytes,
        "bolagsverket_download_bytes": bolags_download_bytes,
        **scb_stats,
        **bolags_stats,
        "candidate_anchor_count": len(ordered),
        "candidate_limit_reached": len(ordered) > len(selected),
        "accepted_signal_count": len(signals),
        "signals": [signals[key] for key in sorted(signals)],
        "errors": [],
    }


def collect_and_store_sweden_official_clothing_liquidation_anchors(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at: datetime | None = None,
    signal_limit: int = DEFAULT_SIGNAL_LIMIT,
    downloader: FileDownloader = _default_file_downloader,
) -> dict[str, Any]:
    """Collect the bulk anchors and merge them into the existing Swedish signal artifact."""
    report = collect_sweden_official_clothing_liquidation_anchors(
        observed_at=observed_at,
        signal_limit=signal_limit,
        downloader=downloader,
    )
    target = _target_spec(manifest, "SE")
    if target is None:
        report["status"] = "BLOCKED_CONFIGURATION"
        report["retrieval_complete"] = False
        report.setdefault("errors", []).append(
            "No checkpoint artifact directory exists for Sweden."
        )
        return report

    root_path = Path(root)
    artifact_dir = root_path / _compact(target.get("artifact_dir"))
    report_path = artifact_dir / _compact(
        target.get("market_signal_report_file") or "market-signal-report.json"
    )
    report["stored_signal_count"] = _write_merged_report(report_path, report)
    try:
        report["artifact_path"] = report_path.relative_to(root_path).as_posix()
    except ValueError:
        report["artifact_path"] = report_path.as_posix()
    return report
