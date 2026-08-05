"""Bounded OpenAI enrichment for market-intelligence hunt cases.

The model output is advisory only. Source evidence remains authoritative and no
opportunity is created, promoted, contacted, bid on, purchased, reserved or paid.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Protocol, Sequence

import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError

SCHEMA_VERSION = "openai-hunt-case-enrichment-1.0"
SUPPORTED_MARKETS = {"NO", "SE", "DE"}
ACTIVE_STATES = {"ACTIVE", "WATCH"}
EARLY_TYPES = {
    "AUCTION_EVENT", "BUSINESS_CLOSURE", "INSOLVENCY_OR_LIQUIDATION",
    "WAREHOUSE_SURPLUS", "REPEATED_SELLER_ACTIVITY", "RELATED_INVENTORY_ACTIVITY",
}
PRIORITY = {
    "INSOLVENCY_OR_LIQUIDATION": 60, "BUSINESS_CLOSURE": 50,
    "WAREHOUSE_SURPLUS": 45, "REPEATED_SELLER_ACTIVITY": 35,
    "RELATED_INVENTORY_ACTIVITY": 32, "AUCTION_EVENT": 25,
}
PRICES = {
    "gpt-5.6-luna": (1.0, 6.0),
    "gpt-5.6-terra": (2.5, 15.0),
}
ACTIONS = (
    "FIND_COMPANY_IDENTITY", "FIND_LIQUIDATOR", "FIND_SALE_CHANNEL",
    "VERIFY_INVENTORY", "MONITOR", "NO_ACTION",
)


class OpenAIHuntCaseError(RuntimeError):
    """Raised for bounded OpenAI transport or output failures."""


class TriageCase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    case_title: str = Field(min_length=1, max_length=300)
    market_code: str = Field(min_length=2, max_length=7)
    normalized_company_name: str = Field(default="", max_length=500)
    organisation_number: str = Field(default="", max_length=100)
    signal_ids: list[str] = Field(min_length=1, max_length=10)
    connection_basis: list[str] = Field(default_factory=list, max_length=6)
    inventory_likelihood: str = Field(pattern="^(LOW|MEDIUM|HIGH)$")
    sale_channel_likelihood: str = Field(pattern="^(LOW|MEDIUM|HIGH)$")
    missing_information: list[str] = Field(default_factory=list, max_length=10)
    next_hunt_action: str = Field(pattern="^(" + "|".join(ACTIONS) + ")$")
    reason: str = Field(min_length=1, max_length=1200)
    confidence: float = Field(ge=0, le=1)


class TriageOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cases: list[TriageCase] = Field(default_factory=list, max_length=10)
    unassigned_signal_ids: list[str] = Field(default_factory=list, max_length=10)


class DeepOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    case_summary: str = Field(min_length=1, max_length=1600)
    inventory_hypothesis: str = Field(min_length=1, max_length=1200)
    likely_sale_channels: list[str] = Field(default_factory=list, max_length=8)
    targeted_search_queries: list[str] = Field(default_factory=list, max_length=5)
    missing_information: list[str] = Field(default_factory=list, max_length=10)
    recommended_next_action: str = Field(pattern="^(" + "|".join(ACTIONS) + ")$")
    reasoning_summary: str = Field(min_length=1, max_length=1600)
    confidence: float = Field(ge=0, le=1)
    requires_external_verification: bool


class StructuredClient(Protocol):
    def create_structured_response(
        self, *, model: str, instructions: str, input_text: str,
        schema_name: str, schema: Mapping[str, Any], reasoning_effort: str,
        max_output_tokens: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]: ...


@dataclass(slots=True)
class OpenAIResponsesHTTPClient:
    api_key: str
    timeout_seconds: float = 60.0
    endpoint: str = "https://api.openai.com/v1/responses"
    session: requests.Session | None = None

    def create_structured_response(
        self, *, model: str, instructions: str, input_text: str,
        schema_name: str, schema: Mapping[str, Any], reasoning_effort: str,
        max_output_tokens: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = {
            "model": model,
            "store": False,
            "instructions": instructions,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": input_text}]}],
            "reasoning": {"effort": reasoning_effort},
            "text": {"verbosity": "low", "format": {
                "type": "json_schema", "name": schema_name, "strict": True,
                "schema": dict(schema),
            }},
            "max_output_tokens": max_output_tokens,
        }
        response = (self.session or requests).post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout_seconds,
        )
        try:
            response.raise_for_status()
            raw = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise OpenAIHuntCaseError(f"OpenAI request failed: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise OpenAIHuntCaseError("OpenAI response must be an object")
        text = raw.get("output_text")
        if not isinstance(text, str):
            text = ""
            for item in raw.get("output") or []:
                if not isinstance(item, Mapping) or item.get("type") != "message":
                    continue
                for content in item.get("content") or []:
                    if isinstance(content, Mapping) and content.get("type") == "output_text":
                        text = str(content.get("text") or "")
                        break
        if not text:
            raise OpenAIHuntCaseError("OpenAI response had no output text")
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise OpenAIHuntCaseError("OpenAI structured output was invalid JSON") from exc
        if not isinstance(value, dict):
            raise OpenAIHuntCaseError("OpenAI structured output must be an object")
        usage = raw.get("usage") if isinstance(raw.get("usage"), Mapping) else {}
        return value, dict(usage)


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
    for a, b in (("ä", "a"), ("ö", "o"), ("ü", "u"), ("å", "a"), ("æ", "ae"), ("ø", "o")):
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _env_int(env: Mapping[str, str], key: str, default: int, maximum: int) -> int:
    try:
        return max(0, min(maximum, int(_compact(env.get(key)) or default)))
    except ValueError:
        return default


def _env_float(env: Mapping[str, str], key: str, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(_compact(env.get(key)) or default)))
    except ValueError:
        return default


def _orgs(signal: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    keys = ("organisation_number", "organization_number", "orgnr", "org_number")
    for source in (signal, _mapping(signal.get("metadata"))):
        for key in keys:
            raw = source.get(key)
            values = raw if isinstance(raw, list) else [raw]
            for item in values:
                digits = re.sub(r"\D", "", str(item or ""))
                if 8 <= len(digits) <= 14:
                    result.add(digits)
    return result


def select_hunt_signals(brief: Mapping[str, Any], *, max_signals: int) -> list[dict[str, Any]]:
    new_ids = {_compact(x.get("signal_id")) for x in _rows(brief.get("new_signals_today"))}
    changed_ids = {_compact(x.get("signal_id")) for x in _rows(brief.get("changed_signals_since_previous_checkpoint"))}
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for signal in _rows(brief.get("early_signals_to_watch")):
        sid = _compact(signal.get("signal_id"))
        market = _compact(signal.get("source_country")).upper()
        signal_type = _compact(signal.get("signal_type")).upper()
        state = _compact(signal.get("status")).upper()
        if not sid or sid in seen or market not in SUPPORTED_MARKETS:
            continue
        if signal_type not in EARLY_TYPES or state not in ACTIVE_STATES:
            continue
        seen.add(sid)
        score = PRIORITY.get(signal_type, 0)
        score += 16 if sid in changed_ids else 12 if sid in new_ids else 0
        score += 8 if _compact(signal.get("company_name") or signal.get("seller_name")) else 0
        score += 12 if _orgs(signal) else 0
        confidence = signal.get("confidence")
        score += float(confidence) * 20 if isinstance(confidence, (int, float)) else 0
        signal["_hunt_rank"] = score
        candidates.append(signal)
    candidates.sort(key=lambda x: (-float(x["_hunt_rank"]), _compact(x.get("signal_id"))))
    for item in candidates:
        item.pop("_hunt_rank", None)
    return candidates[:max_signals]


def _schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    schema.pop("title", None)
    return schema


def _usage(model: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    input_tokens = int(raw.get("input_tokens") or 0)
    output_tokens = int(raw.get("output_tokens") or 0)
    input_price, output_price = PRICES.get(model, (0.0, 0.0))
    cost = (input_tokens * input_price + output_tokens * output_price) / 1_000_000
    return {
        "model": model, "input_tokens": input_tokens, "output_tokens": output_tokens,
        "total_tokens": int(raw.get("total_tokens") or input_tokens + output_tokens),
        "estimated_cost_usd": round(cost, 6),
    }


def _stable_id(market: str, org: str, company: str, signal_ids: list[str]) -> str:
    identity = org or _normal(company) or "|".join(sorted(signal_ids))
    digest = sha256(f"{market}:{identity}".encode()).hexdigest()[:20]
    return f"hunt:{market.casefold()}:{digest}"


def _verified_link(candidate: TriageCase, signals: list[dict[str, Any]]) -> dict[str, Any]:
    if len(signals) < 2:
        return {"verified": False, "method": "SINGLE_SIGNAL", "state": "UNVERIFIED"}
    source_orgs = [_orgs(s) for s in signals]
    common_orgs = set.intersection(*source_orgs) if all(source_orgs) else set()
    if common_orgs:
        return {"verified": True, "method": "EXACT_ORGANISATION_NUMBER", "state": "SOURCE_VERIFIED"}
    names = [_normal(s.get("company_name") or s.get("seller_name")) for s in signals]
    locations = [_normal(s.get("location")) for s in signals]
    if names[0] and len(set(names)) == 1 and locations[0] and len(set(locations)) == 1:
        return {"verified": True, "method": "EXACT_LEGAL_NAME_AND_LOCATION", "state": "SOURCE_VERIFIED"}
    related = [_compact(s.get("related_opportunity_id")) for s in signals]
    if related[0] and len(set(related)) == 1:
        return {"verified": True, "method": "EXACT_RELATED_OPPORTUNITY_ID", "state": "SOURCE_VERIFIED"}
    return {"verified": False, "method": "MODEL_SUGGESTED_ONLY", "state": "REQUIRES_EXTERNAL_VERIFICATION"}


def _empty(status: str, generated: object, triage_model: str, deep_model: str, limits: dict[str, Any], error: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION, "generated_at": generated, "status": status,
        "triage_model": triage_model, "deep_model": deep_model, "limits": limits,
        "selected_signal_count": 0, "triage_request_count": 0, "deep_request_count": 0,
        "api_request_count": 0, "cases": [], "deep_case_count": 0, "usage": [],
        "estimated_cost_usd": 0.0, "unassigned_signal_ids": [], "error": error,
        "model_output_is_advisory": True, "source_evidence_required_for_verification": True,
        "promotion_to_opportunity_allowed": False, "analysis_eligible": False,
        "top5_eligible": False, "automatic_contact": False, "automatic_bid": False,
        "automatic_purchase": False, "automatic_payment": False,
    }


TRIAGE_INSTRUCTIONS = """Group only the supplied market signals into cautious hunt cases. Never claim a sale or inventory exists. Use only supplied signal IDs. Return strict JSON. Model output is advisory and requires external verification."""
DEEP_INSTRUCTIONS = """Analyze one supplied hunt case and propose bounded public-web follow-up queries. Do not claim facts absent from evidence. Never recommend contact, bidding, purchasing, reservation or payment. Return strict JSON."""


def run_openai_hunt_case_enrichment(
    brief: Mapping[str, Any], *, environment: Mapping[str, str] | None = None,
    client: StructuredClient | None = None,
) -> dict[str, Any]:
    env = dict(os.environ if environment is None else environment)
    triage_model = _compact(env.get("OPENAI_HUNT_TRIAGE_MODEL")) or "gpt-5.6-luna"
    deep_model = _compact(env.get("OPENAI_HUNT_DEEP_MODEL")) or "gpt-5.6-terra"
    max_signals = _env_int(env, "OPENAI_HUNT_MAX_SIGNALS", 10, 10)
    max_deep = _env_int(env, "OPENAI_HUNT_MAX_DEEP_CASES", 2, 2)
    max_requests = _env_int(env, "OPENAI_HUNT_MAX_API_REQUESTS", 3, 3)
    max_cost = _env_float(env, "OPENAI_HUNT_MAX_ESTIMATED_COST_USD", 0.16)
    limits = {
        "max_signals": max_signals, "max_deep_cases": max_deep,
        "max_api_requests": max_requests, "max_estimated_cost_usd": max_cost,
    }
    generated = brief.get("generated_at")
    api_client = client
    if api_client is None:
        api_key = _compact(env.get("OPENAI_API_KEY"))
        if not api_key:
            return _empty("SKIPPED_NO_API_KEY", generated, triage_model, deep_model, limits)
        api_client = OpenAIResponsesHTTPClient(api_key)
    signals = select_hunt_signals(brief, max_signals=max_signals)
    if not signals:
        return _empty("NO_ELIGIBLE_SIGNALS", generated, triage_model, deep_model, limits)
    compact_signals = [{
        "signal_id": s.get("signal_id"), "signal_type": s.get("signal_type"),
        "source_country": s.get("source_country"), "title": s.get("title"),
        "company_name": s.get("company_name"), "seller_name": s.get("seller_name"),
        "location": s.get("location"), "source": s.get("source"),
        "source_url": s.get("source_url"), "value": s.get("value"),
        "organisation_numbers": sorted(_orgs(s)),
    } for s in signals]
    try:
        raw, usage = api_client.create_structured_response(
            model=triage_model, instructions=TRIAGE_INSTRUCTIONS,
            input_text=json.dumps({"signals": compact_signals}, ensure_ascii=False),
            schema_name="market_hunt_case_triage", schema=_schema(TriageOutput),
            reasoning_effort="low", max_output_tokens=1200,
        )
        triage = TriageOutput.model_validate(raw)
    except (OpenAIHuntCaseError, ValidationError, requests.RequestException, ValueError) as exc:
        report = _empty("FAILED", generated, triage_model, deep_model, limits, {"type": type(exc).__name__, "message": _compact(exc)[:1000]})
        report.update({"selected_signal_count": len(signals), "triage_request_count": 1, "api_request_count": 1})
        return report
    usage_rows = [_usage(triage_model, usage)]
    by_id = {_compact(s.get("signal_id")): s for s in signals}
    assigned: set[str] = set()
    cases: list[dict[str, Any]] = []
    for candidate in sorted(triage.cases, key=lambda x: x.confidence, reverse=True):
        ids = [sid for sid in map(_compact, candidate.signal_ids) if sid in by_id and sid not in assigned]
        if not ids:
            continue
        assigned.update(ids)
        source_signals = [by_id[sid] for sid in ids]
        markets = {_compact(s.get("source_country")).upper() for s in source_signals}
        market = candidate.market_code if candidate.market_code in SUPPORTED_MARKETS else (next(iter(markets)) if len(markets) == 1 else "MULTI")
        claimed_org = re.sub(r"\D", "", candidate.organisation_number)
        source_orgs = set().union(*(_orgs(s) for s in source_signals))
        org = claimed_org if claimed_org in source_orgs else ""
        company = candidate.normalized_company_name or next((_compact(s.get("company_name") or s.get("seller_name")) for s in source_signals if _compact(s.get("company_name") or s.get("seller_name"))), "")
        verification = _verified_link(candidate, source_signals)
        case = {
            "hunt_case_id": _stable_id(market, org, company, ids),
            "case_title": candidate.case_title, "market_code": market,
            "normalized_company_name": company, "organisation_number": org or None,
            "model_claimed_organisation_number": claimed_org or None,
            "model_claimed_organisation_number_verified": bool(org),
            "signal_ids": ids, "signal_count": len(ids),
            "signal_types": sorted({_compact(s.get("signal_type")).upper() for s in source_signals}),
            "independent_source_count": len({_compact(s.get("source")) for s in source_signals if _compact(s.get("source"))}),
            "connection_basis_from_model": candidate.connection_basis,
            "link_verification": verification,
            "inventory_likelihood": candidate.inventory_likelihood,
            "sale_channel_likelihood": candidate.sale_channel_likelihood,
            "missing_information": candidate.missing_information,
            "next_hunt_action": candidate.next_hunt_action, "reason": candidate.reason,
            "confidence": candidate.confidence,
            "priority_score": round(candidate.confidence * 100 + (20 if verification["verified"] else 0), 2),
            "deep_analysis_status": "NOT_SELECTED", "deep_analysis": None,
            "model_output_is_advisory": True, "promotion_to_opportunity_allowed": False,
            "analysis_eligible": False, "top5_eligible": False,
            "automatic_contact": False, "automatic_bid": False,
            "automatic_purchase": False, "automatic_payment": False,
        }
        cases.append(case)
    cases.sort(key=lambda x: (-float(x["priority_score"]), x["hunt_case_id"]))
    request_count = 1
    deep_count = 0
    for case in cases[:max_deep]:
        if request_count >= max_requests:
            case["deep_analysis_status"] = "SKIPPED_REQUEST_LIMIT"
            continue
        request_count += 1
        try:
            raw, usage = api_client.create_structured_response(
                model=deep_model, instructions=DEEP_INSTRUCTIONS,
                input_text=json.dumps({"case": case, "signals": [by_id[x] for x in case["signal_ids"]]}, ensure_ascii=False, default=str),
                schema_name="market_hunt_case_deep_analysis", schema=_schema(DeepOutput),
                reasoning_effort="medium", max_output_tokens=1400,
            )
            deep = DeepOutput.model_validate(raw).model_dump(mode="json")
            deep["requires_external_verification"] = True
            case["deep_analysis_status"] = "SUCCESS"
            case["deep_analysis"] = deep
            deep_count += 1
            usage_rows.append(_usage(deep_model, usage))
        except (OpenAIHuntCaseError, ValidationError, requests.RequestException, ValueError) as exc:
            case["deep_analysis_status"] = "FAILED"
            case["deep_analysis"] = {"error_type": type(exc).__name__, "error": _compact(exc)[:1000], "requires_external_verification": True}
    estimated = round(sum(float(x["estimated_cost_usd"]) for x in usage_rows), 6)
    status = "SUCCESS" if estimated <= max_cost else "SKIPPED_BUDGET_GUARD"
    return {
        "schema_version": SCHEMA_VERSION, "generated_at": generated, "status": status,
        "triage_model": triage_model, "deep_model": deep_model, "limits": limits,
        "selected_signal_count": len(signals), "triage_request_count": 1,
        "deep_request_count": request_count - 1, "api_request_count": request_count,
        "cases": cases, "deep_case_count": deep_count, "usage": usage_rows,
        "estimated_cost_usd": estimated,
        "unassigned_signal_ids": sorted(set(by_id) - assigned),
        "model_output_is_advisory": True, "source_evidence_required_for_verification": True,
        "promotion_to_opportunity_allowed": False, "analysis_eligible": False,
        "top5_eligible": False, "automatic_contact": False, "automatic_bid": False,
        "automatic_purchase": False, "automatic_payment": False,
    }


def attach_hunt_case_intelligence(brief: Mapping[str, Any], report: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(brief))
    cases = _rows(report.get("cases"))
    result["hunt_case_intelligence"] = {
        "schema_version": report.get("schema_version"), "status": report.get("status"),
        "generated_at": report.get("generated_at"), "triage_model": report.get("triage_model"),
        "deep_model": report.get("deep_model"), "selected_signal_count": report.get("selected_signal_count", 0),
        "case_count": len(cases), "deep_case_count": report.get("deep_case_count", 0),
        "api_request_count": report.get("api_request_count", 0),
        "estimated_cost_usd": report.get("estimated_cost_usd", 0.0), "cases": cases[:3],
        "model_output_is_advisory": True, "source_evidence_required_for_verification": True,
        "promotion_to_opportunity_allowed": False, "automatic_contact": False,
        "automatic_bid": False, "automatic_purchase": False, "automatic_payment": False,
    }
    counts = dict(_mapping(result.get("counts")))
    counts.update({"hunt_cases": len(cases), "deep_hunt_cases": int(report.get("deep_case_count") or 0)})
    result["counts"] = counts
    return result


def render_openai_hunt_case_enrichment(report: Mapping[str, Any]) -> str:
    cases = _rows(report.get("cases"))
    lines = [
        "تحليل OpenAI لقضايا مطاردة مخزون الملابس",
        f"الوقت: {report.get('generated_at')}", f"الحالة: {report.get('status')}",
        f"الإشارات المفحوصة: {report.get('selected_signal_count', 0)}",
        f"قضايا المطاردة: {len(cases)}", f"قضايا محللة بعمق: {report.get('deep_case_count', 0)}",
        f"طلبات API: {report.get('api_request_count', 0)}",
        f"التكلفة المقدرة لهذا التشغيل: ${float(report.get('estimated_cost_usd') or 0):.4f}", "",
    ]
    if not cases:
        lines.append("لا توجد قضية مطاردة ناتجة من هذا التشغيل.")
    for index, case in enumerate(cases[:3], 1):
        lines.append(f"{index}) {case.get('case_title') or 'قضية دون عنوان'}")
        lines.append(f"   السوق: {case.get('market_code')} | الإشارات: {case.get('signal_count', 0)} | احتمال المخزون: {case.get('inventory_likelihood')} | الربط: {_mapping(case.get('link_verification')).get('state')}")
        lines.append(f"   سبب الأولوية: {_compact(case.get('reason')) or 'غير معروف'}")
        deep = _mapping(case.get("deep_analysis"))
        if case.get("deep_analysis_status") == "SUCCESS":
            lines.append(f"   فرضية المخزون: {_compact(deep.get('inventory_hypothesis'))}")
            queries = [_compact(x) for x in deep.get("targeted_search_queries") or [] if _compact(x)]
            if queries:
                lines.append("   استعلامات البحث الموجّهة:")
                lines.extend(f"   - {query}" for query in queries[:5])
    lines.extend(["", "هذه النتائج استشارية وليست إثباتًا لوجود بيع أو مخزون.", "لا شراء، لا مزايدة، لا اتصال، ولا دفع تلقائي."])
    return "\n".join(lines) + "\n"


def write_openai_hunt_case_artifacts(report: Mapping[str, Any], *, json_path: str | Path, text_path: str | Path) -> None:
    Path(json_path).write_text(json.dumps(dict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(text_path).write_text(render_openai_hunt_case_enrichment(report), encoding="utf-8")
