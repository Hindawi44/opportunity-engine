"""Collect bounded official early signals for the existing domain bulletin.

The collector reuses the repository's existing Brave client only as a discovery
transport. A result is accepted only when its final URL belongs to the official
announcement domain and its title/snippet contain both a legal-event term and a
clothing-domain term. Accepted records remain MarketSignalRecord objects with no
opportunity identity.

This module never contacts a company, bids, buys, reserves, pays, or converts a
signal into an opportunity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.parse import urlparse, urlunparse

from opportunity_engine.market_intelligence import (
    MarketSignalRecord,
    MarketSignalStatus,
    MarketSignalType,
)
from opportunity_engine.ods.brave_search import BraveSearchClient
from opportunity_engine.unified_models import Evidence


SCHEMA_VERSION = "official-early-signal-source-coverage-1.0"
DEFAULT_FRESHNESS = "pd"
DEFAULT_RESULTS_PER_SOURCE = 15
TARGET_SOURCE_BY_MARKET = {
    "NO": "Auksjonen.no",
    "SE": "Blinto",
    "DE": "Riegermann",
}


class SearchClient(Protocol):
    def search(
        self,
        query: str,
        *,
        count: int,
        country: str,
        search_lang: str,
        freshness: str | None,
        use_cache: bool = True,
    ) -> list[dict[str, object]]: ...


@dataclass(frozen=True)
class OfficialSourceSpec:
    key: str
    market_code: str
    source_name: str
    official_domains: tuple[str, ...]
    country: str
    search_lang: str
    query: str
    event_terms: tuple[str, ...]
    clothing_terms: tuple[str, ...]
    generic_titles: tuple[str, ...] = ()


SOURCE_SPECS: tuple[OfficialSourceSpec, ...] = (
    OfficialSourceSpec(
        key="BRREG_KUNNGJORINGER",
        market_code="NO",
        source_name="Brønnøysundregistrene Kunngjøringer",
        official_domains=("brreg.no",),
        country="NO",
        search_lang="nb",
        query=(
            "site:brreg.no/registersok/kunngjoringer "
            "(konkurs OR tvangsavvikling OR oppløsning) "
            "(klær OR klesbutikk OR tekstil OR mote OR arbeidstøy)"
        ),
        event_terms=(
            "konkurs",
            "tvangsavvikling",
            "tvangsoppløsning",
            "oppløsning",
            "avvikling",
            "gjeldsforhandling",
        ),
        clothing_terms=(
            "klær",
            "klesbutikk",
            "bekledning",
            "tekstil",
            "mote",
            "arbeidstøy",
            "arbeidsklær",
            "varelager",
        ),
        generic_titles=("kunngjøringer", "registersøk"),
    ),
    OfficialSourceSpec(
        key="POIT",
        market_code="SE",
        source_name="Post- och Inrikes Tidningar",
        official_domains=("poit.bolagsverket.se",),
        country="SE",
        search_lang="sv",
        query=(
            "site:poit.bolagsverket.se "
            "(konkurs OR likvidation OR avveckling) "
            "(kläder OR klädbutik OR textil OR mode OR arbetskläder)"
        ),
        event_terms=("konkurs", "likvidation", "avveckling", "företagsrekonstruktion"),
        clothing_terms=(
            "kläder",
            "klädbutik",
            "beklädnad",
            "textil",
            "mode",
            "arbetskläder",
            "varulager",
        ),
        generic_titles=("post- och inrikes tidningar", "poit"),
    ),
    OfficialSourceSpec(
        key="DE_INSOLVENZBEKANNTMACHUNGEN",
        market_code="DE",
        source_name="Insolvenzbekanntmachungen",
        official_domains=("insolvenzbekanntmachungen.de",),
        country="DE",
        search_lang="de",
        query=(
            "site:insolvenzbekanntmachungen.de "
            "(Insolvenz OR Liquidation OR Insolvenzverfahren) "
            "(Bekleidung OR Mode OR Textilien OR Arbeitskleidung)"
        ),
        event_terms=(
            "insolvenz",
            "insolvenzverfahren",
            "liquidation",
            "eröffnungsverfahren",
            "vorläufige insolvenzverwaltung",
        ),
        clothing_terms=(
            "bekleidung",
            "mode",
            "textil",
            "textilien",
            "arbeitskleidung",
            "warenbestand",
            "lagerbestand",
        ),
        generic_titles=("insolvenzbekanntmachungen",),
    ),
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _fold(value: object) -> str:
    text = _compact(value).casefold()
    replacements = str.maketrans(
        {"å": "a", "ä": "a", "æ": "ae", "ö": "o", "ø": "o", "ü": "u", "é": "e", "è": "e", "ß": "ss"}
    )
    return text.translate(replacements)


def _contains_term(text: str, terms: Sequence[str]) -> bool:
    folded = _fold(text)
    return any(_fold(term) in folded for term in terms)


def _canonical_url(value: object) -> str | None:
    text = _compact(value)
    if not text.startswith("https://"):
        return None
    parsed = urlparse(text)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if not host:
        return None
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    return urlunparse(("https", host, path, "", parsed.query, ""))


def _is_official_url(url: str, spec: OfficialSourceSpec) -> bool:
    host = (urlparse(url).hostname or "").casefold().rstrip(".")
    return any(host == domain or host.endswith(f".{domain}") for domain in spec.official_domains)


def _result_text(item: Mapping[str, object]) -> str:
    extra = item.get("extra_snippets")
    values = extra if isinstance(extra, Sequence) and not isinstance(extra, (str, bytes)) else []
    extra_text = " ".join(_compact(value) for value in values if _compact(value))
    return " ".join(value for value in (_compact(item.get("title")), _compact(item.get("snippet")), extra_text) if value)


def _looks_generic(item: Mapping[str, object], spec: OfficialSourceSpec) -> bool:
    title = _fold(item.get("title"))
    snippet = _compact(item.get("snippet"))
    return title in {_fold(value) for value in spec.generic_titles} and not _contains_term(snippet, spec.clothing_terms)


def _parse_datetime(value: object) -> datetime | None:
    text = _compact(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _extract_company_name(title: object, spec: OfficialSourceSpec) -> str | None:
    text = _compact(title)
    if not text:
        return None
    cleaned = re.sub(r"\s*[|–—-]\s*(?:Brønnøysundregistrene|Bolagsverket|PoIT|Insolvenzbekanntmachungen).*$", "", text, flags=re.IGNORECASE)
    event_pattern = "|".join(re.escape(term) for term in sorted(spec.event_terms, key=len, reverse=True))
    cleaned = re.sub(rf"^\s*(?:{event_pattern})\s*[:|–—-]*\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(rf"\s*[:|–—-]\s*(?:{event_pattern}).*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = _compact(cleaned).strip(" -–—|:")
    if not cleaned or _fold(cleaned) in {_fold(value) for value in spec.generic_titles}:
        return None
    if len(cleaned) < 3 or len(cleaned) > 300:
        return None
    return cleaned


def _candidate_to_signal(item: Mapping[str, object], spec: OfficialSourceSpec, *, observed_at: datetime) -> MarketSignalRecord | None:
    url = _canonical_url(item.get("url"))
    if not url or not _is_official_url(url, spec) or _looks_generic(item, spec):
        return None
    combined = _result_text(item)
    if not _contains_term(combined, spec.event_terms) or not _contains_term(combined, spec.clothing_terms):
        return None
    title = _compact(item.get("title"))
    if not title:
        return None
    snippet = _compact(item.get("snippet"))
    value = snippet or title
    company_name = _extract_company_name(title, spec)
    published_at = _parse_datetime(item.get("published_at"))
    signal_id = f"official-notice:{spec.market_code.lower()}:{sha256(url.encode('utf-8')).hexdigest()[:24]}"
    evidence = Evidence(
        evidence_type="OFFICIAL_NOTICE_REFERENCE",
        value=value,
        source_url=url,
        captured_at=observed_at,
        verified=False,
        metadata={"discovery_provider": "Brave Search", "official_domain_verified": True, "search_rank": item.get("source_rank")},
    )
    return MarketSignalRecord(
        signal_id=signal_id,
        signal_type=MarketSignalType.INSOLVENCY_OR_LIQUIDATION,
        value=value[:500],
        source=spec.source_name,
        observed_at=observed_at,
        confidence=0.82 if company_name else 0.72,
        source_country=spec.market_code,
        source_url=url,
        title=title[:1000],
        company_name=company_name,
        seller_name=None,
        location=None,
        first_observed_at=observed_at,
        latest_observed_at=observed_at,
        event_date=published_at,
        evidence=[evidence],
        related_opportunity_id=None,
        status=MarketSignalStatus.WATCH,
        metadata={"signal_only": True, "source_role": "OFFICIAL_EARLY_SIGNAL", "official_source_key": spec.key, "discovery_provider": "Brave Search", "published_at_raw": item.get("published_at"), "query": spec.query},
    )


def collect_source_signals(client: SearchClient, spec: OfficialSourceSpec, *, observed_at: datetime, freshness: str = DEFAULT_FRESHNESS, count: int = DEFAULT_RESULTS_PER_SOURCE) -> dict[str, Any]:
    errors: list[str] = []
    try:
        results = client.search(spec.query, count=count, country=spec.country, search_lang=spec.search_lang, freshness=freshness, use_cache=True)
    except Exception as exc:
        results = []
        errors.append(f"{type(exc).__name__}: {exc}")
    signals: dict[str, dict[str, Any]] = {}
    rejected = 0
    for item in results:
        if not isinstance(item, Mapping):
            rejected += 1
            continue
        signal = _candidate_to_signal(item, spec, observed_at=observed_at)
        if signal is None:
            rejected += 1
            continue
        signals[signal.signal_id] = signal.model_dump(mode="json")
    status = "BLOCKED" if errors else ("SUCCESS" if signals else "VALID_ZERO")
    return {
        "schema_version": SCHEMA_VERSION,
        "source_key": spec.key,
        "source_name": spec.source_name,
        "source_country": spec.market_code,
        "generated_at": observed_at.isoformat(),
        "status": status,
        "query": spec.query,
        "freshness": freshness,
        "result_count": len(results),
        "accepted_signal_count": len(signals),
        "rejected_result_count": rejected,
        "errors": errors,
        "signals": [signals[key] for key in sorted(signals)],
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


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


def _write_merged_report(path: Path, report: Mapping[str, Any]) -> None:
    signals = _load_existing_signals(path)
    for item in report.get("signals") or []:
        if isinstance(item, Mapping):
            signal = MarketSignalRecord.model_validate(item)
            signals[signal.signal_id] = signal.model_dump(mode="json")
    payload = dict(report)
    payload["signals"] = [signals[key] for key in sorted(signals)]
    payload["accepted_signal_count"] = len(payload["signals"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _target_spec(manifest: Mapping[str, Any], market_code: str) -> Mapping[str, Any] | None:
    candidates = [item for item in manifest.get("sources") or [] if isinstance(item, Mapping) and _compact(item.get("market_code")).upper() == market_code]
    preferred = TARGET_SOURCE_BY_MARKET.get(market_code)
    if preferred:
        for item in candidates:
            if _compact(item.get("source_name") or item.get("source")) == preferred:
                return item
    return candidates[0] if candidates else None


def collect_manifest_official_early_signals(manifest: Mapping[str, Any], *, root: str | Path = ".", client: SearchClient | None = None, client_factory: Callable[[], SearchClient] = BraveSearchClient.from_environment, observed_at: datetime | None = None, freshness: str = DEFAULT_FRESHNESS) -> dict[str, Any]:
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    root_path = Path(root)
    reports: list[dict[str, Any]] = []
    active_client = client
    client_error: str | None = None
    if active_client is None:
        try:
            active_client = client_factory()
        except Exception as exc:
            client_error = f"{type(exc).__name__}: {exc}"
    for spec in SOURCE_SPECS:
        target = _target_spec(manifest, spec.market_code)
        if target is None:
            reports.append({"schema_version": SCHEMA_VERSION, "source_key": spec.key, "source_name": spec.source_name, "source_country": spec.market_code, "generated_at": now.isoformat(), "status": "BLOCKED", "errors": ["No checkpoint artifact directory exists for this market."], "signals": []})
            continue
        artifact_dir = root_path / _compact(target.get("artifact_dir"))
        report_path = artifact_dir / _compact(target.get("market_signal_report_file") or "market-signal-report.json")
        if active_client is None:
            report = {"schema_version": SCHEMA_VERSION, "source_key": spec.key, "source_name": spec.source_name, "source_country": spec.market_code, "generated_at": now.isoformat(), "status": "BLOCKED", "query": spec.query, "freshness": freshness, "result_count": 0, "accepted_signal_count": 0, "rejected_result_count": 0, "errors": [client_error or "Official discovery client is unavailable."], "signals": [], "automatic_contact": False, "automatic_bid": False, "automatic_purchase": False, "automatic_payment": False}
        else:
            report = collect_source_signals(active_client, spec, observed_at=now, freshness=freshness)
        _write_merged_report(report_path, report)
        report["artifact_path"] = report_path.relative_to(root_path).as_posix()
        reports.append(report)
    counts: dict[str, int] = {}
    for report in reports:
        status = _compact(report.get("status")).upper() or "UNKNOWN"
        counts[status] = counts.get(status, 0) + 1
    return {"schema_version": SCHEMA_VERSION, "generated_at": now.isoformat(), "market_coverage": ["NO", "SE", "DE"], "source_count": len(reports), "status_counts": counts, "sources": reports, "signal_count": sum(int(report.get("accepted_signal_count") or 0) for report in reports), "automatic_contact": False, "automatic_bid": False, "automatic_purchase": False, "automatic_payment": False}
