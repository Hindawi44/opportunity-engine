"""Bounded Brave follow-up for OpenAI-generated market hunt cases.

OpenAI proposes queries; Brave executes them. Search results are evidence
candidates only. They never create or promote an opportunity and never trigger
contact, bidding, purchasing, reservation, or payment.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from opportunity_engine.discovery.brave_search import BraveSearchProvider
from opportunity_engine.discovery.search_provider import SearchHit, SearchProvider

SCHEMA_VERSION = "hunt-case-targeted-followup-1.0"
SUPPORTED_MARKETS = {"NO", "SE", "DE"}
DEFAULT_MAX_CASES = 2
DEFAULT_MAX_QUERIES_PER_CASE = 3
DEFAULT_RESULTS_PER_QUERY = 5
DEFAULT_MAX_REQUESTS = 6
MAX_QUERY_LENGTH = 320
MAX_HITS_PER_CASE = 12
MAX_EVIDENCE_PER_CASE = 5

_INVENTORY_TERMS: dict[str, tuple[str, ...]] = {
    "NO": (
        "varelager", "lagerbeholdning", "restlager", "parti klær", "parti klaer",
        "arbeidsklær", "arbeidsklaer", "bekledning", "butikkvarer", "butikk inventar",
    ),
    "SE": (
        "varulager", "lagerbestånd", "lagerbestand", "restlager", "parti kläder",
        "parti klader", "arbetskläder", "arbetsklader", "butiksinventarier",
    ),
    "DE": (
        "warenbestand", "lagerbestand", "restposten", "bekleidung", "kleidung",
        "arbeitskleidung", "textilien", "geschäftsinventar", "geschaftsinventar",
    ),
}
_SALE_TERMS: dict[str, tuple[str, ...]] = {
    "NO": (
        "selges", "salg", "auksjon", "opphørssalg", "opphorssalg", "lagersalg",
        "avviklingssalg", "konkursbo", "bobestyrer", "tvangssalg",
    ),
    "SE": (
        "säljes", "saljes", "försäljning", "forsaljning", "auktion", "utförsäljning",
        "utforsaljning", "konkursbo", "rekonstruktör", "rekonstruktor",
    ),
    "DE": (
        "verkauf", "auktion", "versteigerung", "insolvenzverkauf", "lagerverkauf",
        "geschäftsauflösung", "geschaftsauflosung", "insolvenzverwalter", "liquidation",
    ),
}
_EVENT_TERMS: dict[str, tuple[str, ...]] = {
    "NO": ("konkurs", "avvikling", "nedleggelse", "opphør", "opphor", "likvidasjon"),
    "SE": ("konkurs", "avveckling", "butiksstängning", "butiksstangning", "likvidation"),
    "DE": ("insolvenz", "geschäftsaufgabe", "geschaftsaufgabe", "schließung", "schliessung"),
}
_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}

ProviderFactory = Callable[[str], SearchProvider]


class TargetedSearchProvider(Protocol):
    name: str

    def search(self, query: str, *, count: int = 10) -> Sequence[SearchHit]: ...


def _compact(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _normal(value: object) -> str:
    text = _compact(value).casefold()
    for source, target in (
        ("ä", "a"), ("ö", "o"), ("ü", "u"), ("å", "a"),
        ("æ", "ae"), ("ø", "o"), ("ß", "ss"),
    ):
        text = text.replace(source, target)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _digits(value: object) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _env_int(
    environment: Mapping[str, str],
    key: str,
    default: int,
    maximum: int,
) -> int:
    try:
        return max(0, min(maximum, int(_compact(environment.get(key)) or default)))
    except ValueError:
        return default


def _canonical_url(raw_url: object) -> str | None:
    try:
        parsed = urlsplit(_compact(raw_url))
    except ValueError:
        return None
    if parsed.scheme.casefold() != "https" or not parsed.netloc:
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
    return urlunsplit(
        ("https", parsed.netloc.casefold(), path, urlencode(filtered, doseq=True), "")
    )


def _safe_query(value: object) -> str | None:
    query = _compact(value)
    if not query or len(query) > MAX_QUERY_LENGTH:
        return None
    if any(character in query for character in ("\x00", "\r", "\n")):
        return None
    if re.search(r"\b(?:https?|file|ftp)://", query, flags=re.IGNORECASE):
        return None
    return query


def _matched_terms(text: str, terms: Sequence[str]) -> list[str]:
    folded = text.casefold()
    return [term for term in terms if term.casefold() in folded]


def _case_queries(case: Mapping[str, Any], *, maximum: int) -> list[str]:
    deep = _mapping(case.get("deep_analysis"))
    result: list[str] = []
    seen: set[str] = set()
    for value in deep.get("targeted_search_queries") or []:
        query = _safe_query(value)
        marker = query.casefold() if query else ""
        if not query or marker in seen:
            continue
        seen.add(marker)
        result.append(query)
        if len(result) >= maximum:
            break
    return result


def select_targeted_hunt_cases(
    hunt_report: Mapping[str, Any],
    *,
    max_cases: int = DEFAULT_MAX_CASES,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for case in _rows(hunt_report.get("cases")):
        market = _compact(case.get("market_code")).upper()
        if market not in SUPPORTED_MARKETS:
            continue
        if _compact(case.get("deep_analysis_status")).upper() != "SUCCESS":
            continue
        if not _case_queries(case, maximum=DEFAULT_MAX_QUERIES_PER_CASE):
            continue
        selected.append(case)
    selected.sort(
        key=lambda item: (
            -float(item.get("priority_score") or 0),
            _compact(item.get("hunt_case_id")),
        )
    )
    return selected[:max_cases]


def _signal_index(brief: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key in (
        "new_signals_today",
        "changed_signals_since_previous_checkpoint",
        "early_signals_to_watch",
    ):
        for signal in _rows(brief.get(key)):
            signal_id = _compact(signal.get("signal_id"))
            if signal_id:
                result.setdefault(signal_id, signal)
    return result


def _known_urls_for_case(
    case: Mapping[str, Any],
    signal_index: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    urls: set[str] = set()
    for signal_id in case.get("signal_ids") or []:
        signal = signal_index.get(_compact(signal_id))
        if not signal:
            continue
        url = _canonical_url(signal.get("source_url"))
        if url:
            urls.add(url)
    return urls


def _default_provider_factory(api_key: str, market_code: str) -> SearchProvider:
    return BraveSearchProvider(
        api_key,
        country=market_code,
        freshness="py",
        extra_snippets=True,
        operators=True,
        max_retries=2,
    )


def _identity_match(
    case: Mapping[str, Any],
    hit: SearchHit,
) -> tuple[str, bool]:
    searchable = " ".join((hit.title, hit.description, hit.url))
    organisation_number = _digits(case.get("organisation_number"))
    if organisation_number and organisation_number in _digits(searchable):
        return "EXACT_ORGANISATION_NUMBER", True

    company_name = _normal(case.get("normalized_company_name"))
    generic_names = {"unknown", "unidentified", "not known", "غير معروفة"}
    if company_name and len(company_name) >= 4 and company_name not in generic_names:
        if company_name in _normal(searchable):
            return "EXACT_NORMALIZED_COMPANY_NAME", True
    return "NO_EXACT_IDENTITY_MATCH", False


def _evaluate_hit(
    *,
    case: Mapping[str, Any],
    query: str,
    hit: SearchHit,
    known_urls: set[str],
) -> dict[str, Any] | None:
    url = _canonical_url(hit.url)
    if not url:
        return None
    market = _compact(case.get("market_code")).upper()
    text = " ".join((hit.title, hit.description, url))
    identity_method, identity_matched = _identity_match(case, hit)
    inventory_terms = _matched_terms(text, _INVENTORY_TERMS[market])
    sale_terms = _matched_terms(text, _SALE_TERMS[market])
    event_terms = _matched_terms(text, _EVENT_TERMS[market])
    already_known = url in known_urls

    score = 0
    if identity_method == "EXACT_ORGANISATION_NUMBER":
        score += 60
    elif identity_method == "EXACT_NORMALIZED_COMPANY_NAME":
        score += 40
    if inventory_terms:
        score += 20
    if sale_terms:
        score += 15
    if event_terms:
        score += 8
    if already_known:
        score -= 20
    if not identity_matched and not inventory_terms and not sale_terms:
        score -= 20
    score = max(0, min(100, score))

    commercial_terms = bool(inventory_terms or sale_terms)
    if identity_matched and commercial_terms and not already_known:
        evidence_class = "IDENTITY_AND_COMMERCIAL_SIGNAL"
        verification_state = "EVIDENCE_CANDIDATE_REQUIRES_PAGE_VERIFICATION"
    elif identity_matched and not already_known:
        evidence_class = "IDENTITY_CONTEXT_ONLY"
        verification_state = "UNVERIFIED_CONTEXT"
    elif commercial_terms and not already_known:
        evidence_class = "COMMERCIAL_SIGNAL_UNLINKED"
        verification_state = "UNVERIFIED_IDENTITY"
    elif already_known:
        evidence_class = "ALREADY_KNOWN_SOURCE"
        verification_state = "KNOWN_NOT_NEW_EVIDENCE"
    else:
        evidence_class = "LOW_RELEVANCE"
        verification_state = "UNVERIFIED"

    digest = sha256(f"{case.get('hunt_case_id')}:{url}".encode()).hexdigest()[:20]
    return {
        "evidence_candidate_id": f"followup:{digest}",
        "hunt_case_id": case.get("hunt_case_id"),
        "market_code": market,
        "query": query,
        "title": _compact(hit.title)[:500],
        "url": url,
        "description": _compact(hit.description)[:2000],
        "provider": _compact(hit.provider) or "Brave Search",
        "identity_match_method": identity_method,
        "identity_matched": identity_matched,
        "inventory_terms": inventory_terms,
        "sale_terms": sale_terms,
        "event_terms": event_terms,
        "already_known_source_url": already_known,
        "relevance_score": score,
        "evidence_class": evidence_class,
        "verification_state": verification_state,
        "page_fetched": False,
        "page_verified": False,
        "promotion_to_opportunity_allowed": False,
        "analysis_eligible": False,
        "top5_eligible": False,
    }


def _empty_report(
    status: str,
    generated_at: object,
    limits: Mapping[str, int],
    *,
    error: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "limits": dict(limits),
        "selected_case_count": 0,
        "search_request_count": 0,
        "query_success_count": 0,
        "query_failure_count": 0,
        "result_count": 0,
        "new_result_count": 0,
        "evidence_candidate_count": 0,
        "case_followups": [],
        "error": dict(error) if error else None,
        "search_results_are_unverified": True,
        "source_page_verification_required": True,
        "promotion_to_opportunity_allowed": False,
        "analysis_eligible": False,
        "top5_eligible": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def run_hunt_case_targeted_followup(
    hunt_report: Mapping[str, Any],
    brief: Mapping[str, Any],
    *,
    environment: Mapping[str, str] | None = None,
    provider_factory: ProviderFactory | None = None,
) -> dict[str, Any]:
    env = dict(os.environ if environment is None else environment)
    max_cases = _env_int(env, "HUNT_FOLLOWUP_MAX_CASES", DEFAULT_MAX_CASES, 2)
    max_queries = _env_int(
        env,
        "HUNT_FOLLOWUP_MAX_QUERIES_PER_CASE",
        DEFAULT_MAX_QUERIES_PER_CASE,
        3,
    )
    results_per_query = _env_int(
        env,
        "HUNT_FOLLOWUP_RESULTS_PER_QUERY",
        DEFAULT_RESULTS_PER_QUERY,
        5,
    )
    max_requests = _env_int(
        env,
        "HUNT_FOLLOWUP_MAX_REQUESTS",
        DEFAULT_MAX_REQUESTS,
        6,
    )
    limits = {
        "max_cases": max_cases,
        "max_queries_per_case": max_queries,
        "results_per_query": results_per_query,
        "max_requests": max_requests,
    }
    generated_at = hunt_report.get("generated_at") or brief.get("generated_at")

    factory = provider_factory
    if factory is None:
        api_key = _compact(env.get("BRAVE_SEARCH_API_KEY"))
        if not api_key:
            return _empty_report(
                "SKIPPED_NO_BRAVE_KEY", generated_at, limits
            )
        factory = lambda market, key=api_key: _default_provider_factory(key, market)

    selected_cases = select_targeted_hunt_cases(hunt_report, max_cases=max_cases)
    if not selected_cases:
        return _empty_report("NO_ELIGIBLE_CASES", generated_at, limits)

    signal_index = _signal_index(brief)
    providers: dict[str, SearchProvider] = {}
    case_followups: list[dict[str, Any]] = []
    request_count = 0
    query_success_count = 0
    query_failure_count = 0
    total_results = 0
    new_results = 0
    total_evidence = 0

    for case in selected_cases:
        market = _compact(case.get("market_code")).upper()
        queries = _case_queries(case, maximum=max_queries)
        known_urls = _known_urls_for_case(case, signal_index)
        query_rows: list[dict[str, Any]] = []
        hits_by_url: dict[str, dict[str, Any]] = {}

        for query in queries:
            if request_count >= max_requests:
                query_rows.append(
                    {
                        "query": query,
                        "status": "SKIPPED_REQUEST_LIMIT",
                        "result_count": 0,
                        "error": None,
                    }
                )
                continue
            request_count += 1
            try:
                provider = providers.get(market)
                if provider is None:
                    provider = factory(market)
                    providers[market] = provider
                raw_hits = provider.search(query, count=results_per_query)
                query_success_count += 1
                accepted_count = 0
                for hit in raw_hits[:results_per_query]:
                    evaluated = _evaluate_hit(
                        case=case,
                        query=query,
                        hit=hit,
                        known_urls=known_urls,
                    )
                    if evaluated is None:
                        continue
                    accepted_count += 1
                    url = str(evaluated["url"])
                    previous = hits_by_url.get(url)
                    if previous is None or int(evaluated["relevance_score"]) > int(
                        previous["relevance_score"]
                    ):
                        hits_by_url[url] = evaluated
                query_rows.append(
                    {
                        "query": query,
                        "status": "SUCCESS" if accepted_count else "VALID_ZERO",
                        "result_count": accepted_count,
                        "error": None,
                    }
                )
            except Exception as exc:  # source failure remains isolated
                query_failure_count += 1
                query_rows.append(
                    {
                        "query": query,
                        "status": "FAILED",
                        "result_count": 0,
                        "error": {
                            "type": type(exc).__name__,
                            "message": _compact(exc)[:700],
                        },
                    }
                )

        ranked_hits = sorted(
            hits_by_url.values(),
            key=lambda item: (
                -int(item.get("relevance_score") or 0),
                _compact(item.get("url")),
            ),
        )[:MAX_HITS_PER_CASE]
        evidence_candidates = [
            item
            for item in ranked_hits
            if item.get("evidence_class") == "IDENTITY_AND_COMMERCIAL_SIGNAL"
        ][:MAX_EVIDENCE_PER_CASE]
        total_results += len(ranked_hits)
        new_results += sum(
            1 for item in ranked_hits if not item.get("already_known_source_url")
        )
        total_evidence += len(evidence_candidates)

        failed_queries = sum(1 for row in query_rows if row["status"] == "FAILED")
        if evidence_candidates or ranked_hits:
            case_status = "PARTIAL" if failed_queries else "SUCCESS"
        elif failed_queries and failed_queries == len(query_rows):
            case_status = "FAILED"
        elif failed_queries:
            case_status = "PARTIAL"
        else:
            case_status = "VALID_ZERO"

        case_followups.append(
            {
                "hunt_case_id": case.get("hunt_case_id"),
                "case_title": case.get("case_title"),
                "market_code": market,
                "normalized_company_name": case.get("normalized_company_name"),
                "organisation_number": case.get("organisation_number"),
                "status": case_status,
                "queries": query_rows,
                "known_source_urls": sorted(known_urls),
                "result_count": len(ranked_hits),
                "new_result_count": sum(
                    1
                    for item in ranked_hits
                    if not item.get("already_known_source_url")
                ),
                "evidence_candidate_count": len(evidence_candidates),
                "results": ranked_hits,
                "evidence_candidates": evidence_candidates,
                "search_results_are_unverified": True,
                "source_page_verification_required": True,
                "promotion_to_opportunity_allowed": False,
            }
        )

    if query_success_count and query_failure_count:
        status = "PARTIAL"
    elif query_success_count:
        status = "SUCCESS" if total_results else "VALID_ZERO"
    elif query_failure_count:
        status = "FAILED"
    else:
        status = "NO_ELIGIBLE_QUERIES"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "limits": limits,
        "selected_case_count": len(selected_cases),
        "search_request_count": request_count,
        "query_success_count": query_success_count,
        "query_failure_count": query_failure_count,
        "result_count": total_results,
        "new_result_count": new_results,
        "evidence_candidate_count": total_evidence,
        "case_followups": case_followups,
        "error": None,
        "search_results_are_unverified": True,
        "source_page_verification_required": True,
        "promotion_to_opportunity_allowed": False,
        "analysis_eligible": False,
        "top5_eligible": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }


def attach_targeted_followup_intelligence(
    brief: Mapping[str, Any],
    report: Mapping[str, Any],
) -> dict[str, Any]:
    result = deepcopy(dict(brief))
    case_followups = _rows(report.get("case_followups"))
    evidence: list[dict[str, Any]] = []
    for case in case_followups:
        evidence.extend(_rows(case.get("evidence_candidates")))
    evidence.sort(
        key=lambda item: (
            -int(item.get("relevance_score") or 0),
            _compact(item.get("url")),
        )
    )
    result["targeted_followup_intelligence"] = {
        "schema_version": report.get("schema_version"),
        "status": report.get("status"),
        "generated_at": report.get("generated_at"),
        "selected_case_count": report.get("selected_case_count", 0),
        "search_request_count": report.get("search_request_count", 0),
        "result_count": report.get("result_count", 0),
        "new_result_count": report.get("new_result_count", 0),
        "evidence_candidate_count": report.get("evidence_candidate_count", 0),
        "top_evidence_candidates": evidence[:5],
        "search_results_are_unverified": True,
        "source_page_verification_required": True,
        "promotion_to_opportunity_allowed": False,
        "automatic_contact": False,
        "automatic_bid": False,
        "automatic_purchase": False,
        "automatic_payment": False,
    }
    counts = dict(_mapping(result.get("counts")))
    counts.update(
        {
            "targeted_followup_cases": int(report.get("selected_case_count") or 0),
            "targeted_followup_results": int(report.get("result_count") or 0),
            "targeted_evidence_candidates": int(
                report.get("evidence_candidate_count") or 0
            ),
        }
    )
    result["counts"] = counts
    return result


def render_hunt_case_targeted_followup(report: Mapping[str, Any]) -> str:
    cases = _rows(report.get("case_followups"))
    lines = [
        "البحث الموجّه لقضايا مطاردة مخزون الملابس",
        f"الوقت: {report.get('generated_at')}",
        f"الحالة: {report.get('status')}",
        f"القضايا المفحوصة: {report.get('selected_case_count', 0)}",
        f"طلبات Brave: {report.get('search_request_count', 0)}",
        f"الروابط الجديدة: {report.get('new_result_count', 0)}",
        f"مرشحو الأدلة التجارية: {report.get('evidence_candidate_count', 0)}",
        "",
    ]
    if not cases:
        lines.append("لا توجد قضية مؤهلة للبحث الموجّه في هذا التشغيل.")
    for index, case in enumerate(cases, 1):
        lines.append(f"{index}) {case.get('case_title') or 'قضية بلا عنوان'}")
        lines.append(
            "   "
            f"السوق: {case.get('market_code')} | "
            f"الحالة: {case.get('status')} | "
            f"النتائج: {case.get('result_count', 0)} | "
            f"مرشحو الأدلة: {case.get('evidence_candidate_count', 0)}"
        )
        evidence = _rows(case.get("evidence_candidates"))
        if evidence:
            lines.append("   أقوى الروابط التي تحتاج فتح الصفحة والتحقق:")
            for item in evidence[:3]:
                lines.append(
                    f"   - [{item.get('relevance_score')}/100] "
                    f"{item.get('title')}"
                )
                lines.append(f"     الربط: {item.get('identity_match_method')}")
                lines.append(f"     الرابط: {item.get('url')}")
        else:
            lines.append("   لم يظهر رابط يجمع هوية القضية وإشارة بيع/مخزون بعد.")
    lines.extend(
        [
            "",
            "نتائج البحث ليست إثباتًا؛ يجب فتح صفحة المصدر والتحقق منها.",
            "لا ترقية تلقائية إلى فرصة، ولا شراء، ولا مزايدة، ولا اتصال، ولا دفع.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_hunt_case_targeted_followup_artifacts(
    report: Mapping[str, Any],
    *,
    json_path: str | Path,
    text_path: str | Path,
) -> None:
    Path(json_path).write_text(
        json.dumps(dict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path(text_path).write_text(
        render_hunt_case_targeted_followup(report),
        encoding="utf-8",
    )
