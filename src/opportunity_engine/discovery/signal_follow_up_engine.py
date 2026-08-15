"""Bounded follow-up of early market signals until commercial evidence appears.

The engine reuses the existing unified market cases and Brave Search adapter. It
never treats a search hit as commercial proof and never promotes a market signal
into an opportunity. Its job is narrower: keep important liquidation/closure
threads alive, run a small number of targeted searches, and expose source URLs
that deserve the project's existing verification gates.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider


SCHEMA_VERSION = "signal-follow-up-engine-1.0"
OUTPUT_FILENAME = "signal-follow-up-engine.json"
DECISION_OWNER = "HUMAN_OPERATOR"
SUPPORTED_MARKETS = {"NO", "SE", "DE"}
FOLLOW_UP_CASE_TYPES = {
    "COMPANY_LIQUIDATION",
    "BRIDAL_LIQUIDATION",
    "MARKET_SIGNAL_WATCH",
}
COMMERCIAL_CASE_TYPES = {
    "DIRECT_OPPORTUNITY",
    "B2B_INVENTORY",
    "AUCTION_INVENTORY",
}
DEFAULT_MAX_CASES = 4
DEFAULT_RESULTS_PER_CASE = 5
MAX_CASES = 6
MAX_RESULTS_PER_CASE = 10

ProviderFactory = Callable[[str, str], SearchProvider]

_MARKET_QUERY_TERMS = {
    "NO": '(restlager OR varelager OR opphørssalg OR avviklingssalg OR auksjon OR "parti klær")',
    "SE": '(restlager OR varulager OR utförsäljning OR avvecklingsförsäljning OR auktion OR "parti kläder")',
    "DE": '(Restposten OR Warenbestand OR Lagerverkauf OR Geschäftsauflösung OR Auktion OR Versteigerung)',
}
_MARKET_CLOTHING_TERMS = {
    "NO": '(klær OR klesbutikk OR tekstil OR bekledning)',
    "SE": '(kläder OR klädbutik OR textil OR mode)',
    "DE": '(Bekleidung OR Modegeschäft OR Kleidung OR Textilien)',
}
_COMMERCIAL_TERMS = {
    "NO": (
        "restlager",
        "varelager",
        "opphørssalg",
        "avviklingssalg",
        "auksjon",
        "parti klær",
        "selges",
    ),
    "SE": (
        "restlager",
        "varulager",
        "utförsäljning",
        "utforsaljning",
        "avvecklingsförsäljning",
        "avvecklingsforsaljning",
        "auktion",
        "parti kläder",
        "parti klader",
        "säljes",
        "saljes",
    ),
    "DE": (
        "restposten",
        "warenbestand",
        "lagerverkauf",
        "geschäftsauflösung",
        "geschaftsauflosung",
        "auktion",
        "versteigerung",
        "lagerauflösung",
        "lageraufloesung",
        "verkauf",
    ),
}
_AUCTION_TERMS = {
    "NO": ("auksjon",),
    "SE": ("auktion",),
    "DE": ("auktion", "versteigerung"),
}
_LOCATION_HINTS = {
    "NO": ("næringsliv", "konkurs", "klesbutikken", "butikk"),
    "SE": ("konkurs", "klädbutik", "butik"),
    "DE": ("insolvenz", "modekette", "modegeschäft", "modegeschaft"),
}
_GENERIC_PREFIXES = {
    "wir hatten ein betrugsproblem",
    "næringsliv",
    "naeringsliv",
    "konkurs",
    "insolvenz",
    "modekette",
    "klesbutikken",
}
_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _fold(value: object) -> str:
    return _compact(value).casefold()


def _now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _canonical_url(raw: object) -> str | None:
    text = _compact(raw)
    if not text:
        return None
    try:
        parsed = urlsplit(text)
    except ValueError:
        return None
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        return None
    filtered = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_")
        and key.casefold() not in _TRACKING_QUERY_KEYS
    ]
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(("https", parsed.netloc.casefold(), path, urlencode(filtered, doseq=True), ""))


def _normalise(value: object) -> str:
    text = _fold(value)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9à-öø-ÿ]+", " ", text)
    return " ".join(text.split())


def _significant_tokens(value: object) -> list[str]:
    stop = {
        "and",
        "co",
        "the",
        "von",
        "der",
        "die",
        "das",
        "mit",
        "for",
        "fra",
        "til",
        "og",
        "ab",
    }
    return [
        token
        for token in _normalise(value).split()
        if len(token) >= 4 and token not in stop
    ][:8]


def _country(case: Mapping[str, Any]) -> str | None:
    countries = case.get("countries")
    if not isinstance(countries, Sequence) or isinstance(countries, (str, bytes)):
        return None
    for value in countries:
        code = _compact(value).upper()
        if code in SUPPORTED_MARKETS:
            return code
    return None


def _sensible_target(value: object) -> str | None:
    text = _compact(value).strip("–—-:|,.; '“”„\"")
    if not 3 <= len(text) <= 90:
        return None
    folded = _normalise(text)
    if not folded or folded in _GENERIC_PREFIXES:
        return None
    if len(_significant_tokens(text)) == 0:
        return None
    return text


def _derive_target(case: Mapping[str, Any], market: str) -> tuple[str | None, str]:
    """Derive a conservative search target from already-published case text."""
    title = _compact(case.get("case_title") or case.get("headline"))
    grouping = _compact(case.get("grouping_basis")).upper()
    if grouping in {"COMPANY", "ORGANISATION"}:
        target = _sensible_target(title)
        if target:
            return target, "EXPLICIT_COMPANY_OR_ORGANISATION"

    if market == "DE":
        # Common news form: "Adenauer & Co.: Modekette meldet Insolvenz ..."
        if ":" in title:
            prefix = _sensible_target(title.split(":", 1)[0])
            if prefix and not prefix.startswith(("„", "\"", "'")):
                return prefix, "TITLE_COMPANY_PREFIX"
        match = re.search(
            r"\b(?:von|bei)\s+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9&.\- ]{2,60}?)\s+(?:meldet|ist|geht|hat)\b",
            title,
        )
        if match:
            target = _sensible_target(match.group(1))
            if target:
                return target, "TITLE_ENTITY_PHRASE"

    if market in {"NO", "SE"} and "|" in title:
        left = _compact(title.split("|", 1)[0])
        if "," in left:
            location = _sensible_target(left.rsplit(",", 1)[-1])
            if location:
                return location, "LOCATION_EVENT_FALLBACK"

    # Conservative fallback: use the shortest non-generic segment only when it
    # still carries at least one useful token. This remains a search target, not
    # an identity assertion.
    segments = [
        _sensible_target(part)
        for part in re.split(r"\s+[|–—]\s+|:\s+", title)
    ]
    segments = [part for part in segments if part]
    if segments:
        return min(segments, key=len), "TITLE_SEARCH_FALLBACK"
    return None, "NO_RELIABLE_TARGET"


def _query(target: str, market: str, target_kind: str) -> str:
    escaped = target.replace('"', "").strip()
    base = f'"{escaped}" {_MARKET_QUERY_TERMS[market]}'
    if target_kind == "LOCATION_EVENT_FALLBACK":
        base += f" {_MARKET_CLOTHING_TERMS[market]}"
    return base


def _case_timestamp(case: Mapping[str, Any]) -> float:
    value = _compact(case.get("last_seen") or case.get("first_seen"))
    if not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return 0.0


def _eligible_cases(cases_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in cases_report.get("cases") or []:
        if not isinstance(raw, Mapping):
            continue
        case = dict(raw)
        if _compact(case.get("case_type")).upper() not in FOLLOW_UP_CASE_TYPES:
            continue
        if _compact(case.get("case_status")).upper() == "HISTORICAL_ONLY":
            continue
        market = _country(case)
        if market is None:
            continue
        target, target_kind = _derive_target(case, market)
        if not target:
            continue
        case["_follow_up_market"] = market
        case["_follow_up_target"] = target
        case["_follow_up_target_kind"] = target_kind
        result.append(case)
    result.sort(
        key=lambda item: (
            -_case_timestamp(item),
            -float(item.get("commercial_strength") or item.get("source_strength") or 0.0),
            _compact(item.get("case_id")),
        )
    )
    return result


def _explicit_commercial_links(
    case: Mapping[str, Any],
    all_cases: Sequence[Mapping[str, Any]],
) -> list[str]:
    basis = _compact(case.get("grouping_basis")).upper()
    key = _compact(case.get("grouping_key"))
    if basis not in {"COMPANY", "ORGANISATION"} or not key:
        return []
    country = _country(case)
    result: list[str] = []
    for other in all_cases:
        if _compact(other.get("case_type")).upper() not in COMMERCIAL_CASE_TYPES:
            continue
        if _compact(other.get("grouping_basis")).upper() != basis:
            continue
        if _compact(other.get("grouping_key")) != key:
            continue
        if country and _country(other) != country:
            continue
        case_id = _compact(other.get("case_id"))
        if case_id:
            result.append(case_id)
    return sorted(set(result))


def _matched_terms(text: str, terms: Sequence[str]) -> list[str]:
    folded = text.casefold()
    return sorted({term for term in terms if term.casefold() in folded})


def _lead_kind(market: str, text: str) -> str:
    if _matched_terms(text, _AUCTION_TERMS[market]):
        return "AUCTION_OR_VERSTEIGERUNG_LEAD"
    return "INVENTORY_OR_LIQUIDATION_SALE_LEAD"


def _lead_from_hit(
    hit: SearchHit,
    *,
    case: Mapping[str, Any],
    rank: int,
) -> dict[str, Any] | None:
    market = str(case["_follow_up_market"])
    target = str(case["_follow_up_target"])
    source_url = _canonical_url(hit.url)
    if not source_url:
        return None
    existing_urls = {
        url
        for url in (_canonical_url(value) for value in (case.get("source_urls") or []))
        if url
    }
    if source_url in existing_urls:
        return None

    title = _compact(hit.title)
    description = _compact(hit.description)
    combined = f"{title} {description}".strip()
    commercial_terms = _matched_terms(combined, _COMMERCIAL_TERMS[market])
    if not commercial_terms:
        return None
    target_tokens = _significant_tokens(target)
    folded = _normalise(combined)
    matched_target_tokens = [token for token in target_tokens if token in folded]
    if target_tokens and not matched_target_tokens:
        return None

    title_terms = _matched_terms(title, _COMMERCIAL_TERMS[market])
    relevance = 50 + min(20, len(matched_target_tokens) * 5) + min(20, len(title_terms) * 5)
    relevance = min(90, relevance)
    return {
        "lead_id": "follow-up-lead:"
        + sha256(f"{case.get('case_id')}|{source_url}".encode("utf-8")).hexdigest()[:24],
        "case_id": case.get("case_id"),
        "lead_kind": _lead_kind(market, combined),
        "title": title,
        "source_url": source_url,
        "provider": _compact(hit.provider) or "Brave Search",
        "search_rank": rank,
        "matched_target_tokens": matched_target_tokens,
        "matched_commercial_terms": commercial_terms,
        "follow_up_relevance_score": relevance,
        "verification_status": "UNVERIFIED_PUBLIC_WEB_SEARCH_HIT",
        "source_page_verification_required": True,
        "commercial_facts_confirmed": False,
        "promotion_to_opportunity_allowed": False,
        "decision_owner": DECISION_OWNER,
    }


def _default_provider_factory(market: str, api_key: str) -> SearchProvider:
    return BraveSearchProvider(
        api_key,
        freshness="pm",
        extra_snippets=True,
        operators=True,
        country=market,
    )


def build_signal_follow_up_plan(
    cases_report: Mapping[str, Any],
    *,
    max_cases: int = DEFAULT_MAX_CASES,
) -> list[dict[str, Any]]:
    """Select and de-duplicate bounded follow-up targets from current cases."""
    bounded = max(0, min(MAX_CASES, int(max_cases)))
    selected: list[dict[str, Any]] = []
    seen_targets: set[tuple[str, str]] = set()
    all_cases = [dict(item) for item in cases_report.get("cases") or [] if isinstance(item, Mapping)]
    for case in _eligible_cases(cases_report):
        market = str(case["_follow_up_market"])
        target = str(case["_follow_up_target"])
        target_key = (market, _normalise(target))
        if target_key in seen_targets:
            continue
        seen_targets.add(target_key)
        selected.append(
            {
                "case_id": case.get("case_id"),
                "case_type": case.get("case_type"),
                "case_title": case.get("case_title"),
                "country": market,
                "target_label": target,
                "target_kind": case["_follow_up_target_kind"],
                "query": _query(target, market, str(case["_follow_up_target_kind"])),
                "last_seen": case.get("last_seen"),
                "source_urls": list(case.get("source_urls") or [])[:10],
                "explicit_linked_commercial_case_ids": _explicit_commercial_links(case, all_cases),
                "_source_case": case,
            }
        )
        if len(selected) >= bounded:
            break
    return selected


def run_signal_follow_up_engine(
    cases_report: Mapping[str, Any],
    *,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory | None = None,
    observed_at: datetime | None = None,
    max_cases: int = DEFAULT_MAX_CASES,
    results_per_case: int = DEFAULT_RESULTS_PER_CASE,
) -> dict[str, Any]:
    """Run bounded targeted searches for current early-signal cases."""
    env = environment if environment is not None else os.environ
    generated_at = _now(observed_at).isoformat()
    planned = build_signal_follow_up_plan(cases_report, max_cases=max_cases)
    bounded_results = max(1, min(MAX_RESULTS_PER_CASE, int(results_per_case)))
    api_key = _compact(env.get("BRAVE_SEARCH_API_KEY"))
    factory = provider_factory or _default_provider_factory

    searched = 0
    errors = 0
    lead_count = 0
    linked_count = 0
    output_cases: list[dict[str, Any]] = []

    for plan in planned:
        source_case = plan.pop("_source_case")
        links = list(plan.get("explicit_linked_commercial_case_ids") or [])
        if links:
            linked_count += 1
        row = dict(plan)
        row["leads"] = []
        row["search_status"] = "PLANNED"
        if not api_key:
            row["search_status"] = "SKIPPED_NO_API_KEY"
        else:
            try:
                provider = factory(str(plan["country"]), api_key)
                hits = provider.search(str(plan["query"]), count=bounded_results)
                searched += 1
                leads: list[dict[str, Any]] = []
                seen: set[str] = set()
                for rank, hit in enumerate(hits, start=1):
                    lead = _lead_from_hit(hit, case=source_case, rank=rank)
                    if lead is None or lead["source_url"] in seen:
                        continue
                    seen.add(str(lead["source_url"]))
                    leads.append(lead)
                leads.sort(
                    key=lambda item: (
                        -int(item.get("follow_up_relevance_score") or 0),
                        int(item.get("search_rank") or 999),
                        str(item.get("source_url") or ""),
                    )
                )
                row["leads"] = leads[:bounded_results]
                lead_count += len(row["leads"])
                row["search_status"] = "SUCCESS"
            except Exception as exc:
                errors += 1
                row["search_status"] = "FAILED"
                row["error_type"] = type(exc).__name__
                row["error"] = _compact(exc)[:500]

        if links:
            row["follow_up_state"] = "EXPLICIT_COMMERCIAL_CASE_LINK_EXISTS"
        elif row["leads"]:
            row["follow_up_state"] = "COMMERCIAL_LEAD_REQUIRES_SOURCE_VERIFICATION"
        else:
            row["follow_up_state"] = "MONITORING"
        row["search_hit_is_not_commercial_proof"] = True
        row["promotion_to_opportunity_allowed"] = False
        row["automatic_contact"] = False
        row["automatic_bid"] = False
        row["automatic_purchase"] = False
        row["automatic_payment"] = False
        output_cases.append(row)

    if not planned:
        status = "VALID_ZERO_NO_FOLLOW_UP_CASES"
    elif not api_key:
        status = "SKIPPED_NO_API_KEY"
    elif errors and searched:
        status = "PARTIAL_SUCCESS"
    elif errors:
        status = "FAILED"
    else:
        status = "SUCCESS"

    top_lead = None
    leads_flat = [lead for row in output_cases for lead in row.get("leads") or []]
    if leads_flat:
        leads_flat.sort(
            key=lambda item: (
                -int(item.get("follow_up_relevance_score") or 0),
                str(item.get("source_url") or ""),
            )
        )
        top_lead = leads_flat[0]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "purpose": "FOLLOW_EARLY_SIGNAL_UNTIL_SOURCE_VERIFIABLE_COMMERCIAL_EVIDENCE_APPEARS",
        "eligible_follow_up_case_count": len(_eligible_cases(cases_report)),
        "selected_case_count": len(planned),
        "search_request_count": searched,
        "search_error_count": errors,
        "commercial_lead_count": lead_count,
        "explicit_commercial_case_link_count": linked_count,
        "top_follow_up_lead": top_lead,
        "cases": output_cases,
        "search_result_is_not_commercial_proof": True,
        "source_page_verification_required": True,
        "promotion_to_opportunity_allowed": False,
        "decision_owner": DECISION_OWNER,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_reservation": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _summary(report: Mapping[str, Any]) -> dict[str, Any]:
    top = report.get("top_follow_up_lead") if isinstance(report.get("top_follow_up_lead"), Mapping) else None
    return {
        "schema_version": report.get("schema_version"),
        "status": report.get("status"),
        "eligible_follow_up_case_count": report.get("eligible_follow_up_case_count", 0),
        "selected_case_count": report.get("selected_case_count", 0),
        "search_request_count": report.get("search_request_count", 0),
        "commercial_lead_count": report.get("commercial_lead_count", 0),
        "explicit_commercial_case_link_count": report.get("explicit_commercial_case_link_count", 0),
        "top_follow_up_lead": dict(top) if top else None,
        "search_result_is_not_commercial_proof": True,
        "promotion_to_opportunity_allowed": False,
        "decision_owner": DECISION_OWNER,
    }


def _attach_to_domain_brief(output_dir: Path, report: Mapping[str, Any]) -> None:
    brief_path = output_dir / "domain-market-intelligence-brief.json"
    brief = _read_json(brief_path)
    if brief is not None:
        brief["signal_follow_up_engine"] = _summary(report)
        _write_json(brief_path, brief)

    text_path = output_dir / "domain-market-intelligence-brief.txt"
    if not text_path.exists():
        return
    marker = "SIGNAL FOLLOW-UP ENGINE V1"
    text = text_path.read_text(encoding="utf-8")
    if marker in text:
        return
    top = report.get("top_follow_up_lead") if isinstance(report.get("top_follow_up_lead"), Mapping) else {}
    with text_path.open("a", encoding="utf-8") as handle:
        handle.write(
            "\nSIGNAL FOLLOW-UP ENGINE V1\n"
            f"status: {report.get('status')}\n"
            f"eligible_cases: {report.get('eligible_follow_up_case_count', 0)}\n"
            f"searched_cases: {report.get('search_request_count', 0)}\n"
            f"commercial_leads_requiring_verification: {report.get('commercial_lead_count', 0)}\n"
            f"explicit_commercial_case_links: {report.get('explicit_commercial_case_link_count', 0)}\n"
            f"top_follow_up_lead: {top.get('title') or 'NONE'}\n"
            f"top_follow_up_url: {top.get('source_url') or 'NONE'}\n"
            "search_hit_is_not_commercial_proof: true\n"
            "promotion_to_opportunity_allowed: false\n"
            "decision_owner: HUMAN_OPERATOR\n"
        )


def write_signal_follow_up_engine(
    output_dir: str | Path,
    *,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory | None = None,
    observed_at: datetime | None = None,
    max_cases: int = DEFAULT_MAX_CASES,
    results_per_case: int = DEFAULT_RESULTS_PER_CASE,
) -> dict[str, Any]:
    """Read the unified cases artifact, run bounded follow-up, and attach summary."""
    directory = Path(output_dir)
    cases = _read_json(directory / "unified-market-cases.json") or {"cases": []}
    report = run_signal_follow_up_engine(
        cases,
        environment=environment,
        provider_factory=provider_factory,
        observed_at=observed_at,
        max_cases=max_cases,
        results_per_case=results_per_case,
    )
    _write_json(directory / OUTPUT_FILENAME, report)
    _attach_to_domain_brief(directory, report)
    return report
