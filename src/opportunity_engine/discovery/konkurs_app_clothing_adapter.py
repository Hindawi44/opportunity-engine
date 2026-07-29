"""Bounded live adapter for clothing-related bankruptcy leads from Konkurs.app.

Konkurs.app documents a free public JSON API backed by Brønnøysundregistrene.
This adapter performs one small request for each of two observed clothing-industry
codes, retains company-level fields only, and never treats a bankruptcy record as
a verified inventory sale. It uses no paid search, AI API, browser automation,
login, seller contact, bid, purchase, reservation, or payment.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

API_BASE = "https://konkurs.app/api/konkursbo"
CLOTHING_NACE_CODES = ("47.710", "46.420")
INDUSTRY_LABELS = {
    "47.710": "Detaljhandel med klær",
    "46.420": "Engroshandel med klær og skotøy",
}
DEFAULT_LOOKBACK_DAYS = 365
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 50


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _number(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _truthy_flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return _compact(value).casefold() in {"1", "true", "yes", "ja"}


def _iso_date(value: object) -> str | None:
    text = _compact(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def build_api_endpoint(
    industry_code: str,
    *,
    from_date: str,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> str:
    if industry_code not in CLOTHING_NACE_CODES:
        raise ValueError("industry code is outside the approved clothing scope")
    try:
        date.fromisoformat(from_date)
    except ValueError as exc:
        raise ValueError("from_date must be YYYY-MM-DD") from exc
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    query = urlencode({
        "page": 1,
        "size": page_size,
        "sort": "stiftelsesdato",
        "order": "desc",
        "naeringskode": industry_code,
        "fra_dato": from_date,
        "status": "aktive",
    })
    return f"{API_BASE}?{query}"


def is_approved_api_endpoint(url: str) -> bool:
    parsed = urlparse(_compact(url))
    params = parse_qs(parsed.query)
    try:
        page = int((params.get("page") or [""])[0])
        size = int((params.get("size") or [""])[0])
        date.fromisoformat((params.get("fra_dato") or [""])[0])
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == "konkurs.app"
        and parsed.path == "/api/konkursbo"
        and (params.get("naeringskode") or [""])[0] in CLOTHING_NACE_CODES
        and (params.get("status") or [""])[0] == "aktive"
        and (params.get("sort") or [""])[0] == "stiftelsesdato"
        and (params.get("order") or [""])[0] == "desc"
        and page == 1
        and 1 <= size <= MAX_PAGE_SIZE
    )


def build_public_estate_url(orgnr: str) -> str:
    value = _compact(orgnr)
    if len(value) != 9 or not value.isdigit():
        raise ValueError("orgnr must be nine digits")
    return f"https://konkurs.app/konkursbo/{value}"


def _priority_score(
    *,
    opened_date: str | None,
    industry_code: str,
    mva_registered: bool,
    revenue: float | None,
    total_assets: float | None,
    today: date,
) -> int:
    score = 0
    if opened_date:
        age_days = max(0, (today - date.fromisoformat(opened_date)).days)
        if age_days <= 30:
            score += 40
        elif age_days <= 90:
            score += 30
        elif age_days <= 180:
            score += 20
        else:
            score += 10
    score += 20 if industry_code == "46.420" else 15
    if mva_registered:
        score += 10
    if total_assets is not None:
        if total_assets >= 10_000_000:
            score += 20
        elif total_assets >= 2_000_000:
            score += 10
    if revenue is not None:
        if revenue >= 10_000_000:
            score += 10
        elif revenue >= 2_000_000:
            score += 5
    return min(score, 100)


@dataclass(frozen=True, slots=True)
class KonkursAppClothingLead:
    estate_orgnr: str
    estate_name: str
    debtor_name: str
    url: str
    opened_date: str | None
    registered_date: str | None
    industry_code: str
    industry_description: str
    municipality: str | None
    postal_place: str | None
    mva_registered: bool
    accounting_year: str | None
    accounting_currency: str | None
    revenue: float | None
    total_assets: float | None
    total_debt: float | None
    priority_score: int
    source: str = "Konkurs.app API"

    def to_dict(self) -> dict[str, Any]:
        return {
            "estate_orgnr": self.estate_orgnr,
            "estate_name": self.estate_name,
            "debtor_name": self.debtor_name,
            "url": self.url,
            "opened_date": self.opened_date,
            "registered_date": self.registered_date,
            "industry_code": self.industry_code,
            "industry_description": self.industry_description,
            "municipality": self.municipality,
            "postal_place": self.postal_place,
            "mva_registered": self.mva_registered,
            "accounting_year": self.accounting_year,
            "accounting_currency": self.accounting_currency,
            "revenue": self.revenue,
            "total_assets": self.total_assets,
            "total_debt": self.total_debt,
            "priority_score": self.priority_score,
            "opportunity_state": "STRONG_LEAD_REQUIRES_VERIFICATION",
            "listing_status": "UNKNOWN",
            "inventory_sale_verified": False,
            "inventory_quantity_verified": False,
            "top5_eligible": False,
            "analysis_eligible": False,
            "person_data_retained": False,
            "source": self.source,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


def normalize_api_record(
    record: Mapping[str, Any],
    *,
    today: date | None = None,
) -> KonkursAppClothingLead | None:
    today = today or datetime.now(timezone.utc).date()
    industry_code = _compact(record.get("naeringskode"))
    if industry_code not in CLOTHING_NACE_CODES or not _truthy_flag(record.get("aktiv")):
        return None
    estate_orgnr = _compact(record.get("orgnr"))
    estate_name = _compact(record.get("navn"))
    debtor_name = _compact(record.get("debitor_navn"))
    if len(estate_orgnr) != 9 or not estate_orgnr.isdigit() or not estate_name or not debtor_name:
        return None
    opened_date = _iso_date(record.get("stiftelsesdato"))
    revenue = _number(record.get("regnskap_driftsinntekter"))
    total_assets = _number(record.get("regnskap_sum_eiendeler"))
    return KonkursAppClothingLead(
        estate_orgnr=estate_orgnr,
        estate_name=estate_name,
        debtor_name=debtor_name,
        url=build_public_estate_url(estate_orgnr),
        opened_date=opened_date,
        registered_date=_iso_date(record.get("registreringsdato")),
        industry_code=industry_code,
        industry_description=(
            _compact(record.get("naeringsbeskrivelse"))
            or INDUSTRY_LABELS[industry_code]
        ),
        municipality=_compact(record.get("kommune")) or None,
        postal_place=_compact(record.get("poststed")) or None,
        mva_registered=_truthy_flag(record.get("mva_registrert")),
        accounting_year=_compact(record.get("regnskap_aar")) or None,
        accounting_currency=_compact(record.get("regnskap_valuta")) or None,
        revenue=revenue,
        total_assets=total_assets,
        total_debt=_number(record.get("regnskap_sum_gjeld")),
        priority_score=_priority_score(
            opened_date=opened_date,
            industry_code=industry_code,
            mva_registered=_truthy_flag(record.get("mva_registrert")),
            revenue=revenue,
            total_assets=total_assets,
            today=today,
        ),
    )


@dataclass(frozen=True, slots=True)
class KonkursAppClothingCollection:
    captured_at: str
    from_date: str
    endpoints: tuple[str, ...]
    items_received: int
    leads: tuple[KonkursAppClothingLead, ...]
    scan_complete: bool
    errors: tuple[dict[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "konkurs-app-clothing-leads-1.0",
            "captured_at": self.captured_at,
            "from_date": self.from_date,
            "industry_codes": list(CLOTHING_NACE_CODES),
            "endpoints": list(self.endpoints),
            "items_received": self.items_received,
            "lead_count": len(self.leads),
            "scan_complete": self.scan_complete,
            "leads": [lead.to_dict() for lead in self.leads],
            "errors": list(self.errors),
            "commercial_top5_count": 0,
            "paid_search_used": False,
            "openai_api_used": False,
            "playwright_used": False,
            "person_data_retained": False,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


class KonkursAppClothingCollector:
    """Perform two bounded company-level API reads for active clothing estates."""

    def __init__(
        self,
        *,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        page_size: int = DEFAULT_PAGE_SIZE,
        timeout_seconds: float = 30.0,
        fetch_json: Callable[[str], Mapping[str, Any]] | None = None,
        today: date | None = None,
    ) -> None:
        if not 1 <= lookback_days <= 730:
            raise ValueError("lookback_days must be between 1 and 730")
        if not 1 <= page_size <= MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.lookback_days = lookback_days
        self.page_size = page_size
        self.timeout_seconds = timeout_seconds
        self.fetch_json = fetch_json or self._fetch
        self.today = today or datetime.now(timezone.utc).date()

    def _fetch(self, url: str) -> Mapping[str, Any]:
        if not is_approved_api_endpoint(url):
            raise ValueError("endpoint is outside the approved Konkurs.app scope")
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "OpportunityEngine/KonkursApp-Clothing-Leads-1.0",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            if int(response.status) != 200:
                raise RuntimeError(f"Konkurs.app API returned HTTP {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise RuntimeError("Konkurs.app API response is not a JSON object")
        return payload

    def collect(self) -> KonkursAppClothingCollection:
        captured_at = datetime.now(timezone.utc).isoformat()
        from_date = (self.today - timedelta(days=self.lookback_days)).isoformat()
        endpoints = tuple(
            build_api_endpoint(code, from_date=from_date, page_size=self.page_size)
            for code in CLOTHING_NACE_CODES
        )
        errors: list[dict[str, str]] = []
        received = 0
        leads_by_orgnr: dict[str, KonkursAppClothingLead] = {}
        for endpoint in endpoints:
            try:
                payload = self.fetch_json(endpoint)
                raw_data = payload.get("data")
                if not isinstance(raw_data, Sequence) or isinstance(raw_data, (str, bytes)):
                    raise RuntimeError("Konkurs.app API response lacks a data array")
                received += len(raw_data)
                for record in raw_data:
                    if not isinstance(record, Mapping):
                        continue
                    lead = normalize_api_record(record, today=self.today)
                    if lead is not None:
                        leads_by_orgnr.setdefault(lead.estate_orgnr, lead)
            except Exception as exc:
                errors.append({"url": endpoint, "error": str(exc)})
        leads = sorted(
            leads_by_orgnr.values(),
            key=lambda lead: (
                -lead.priority_score,
                lead.opened_date or "",
                lead.estate_orgnr,
            ),
            reverse=False,
        )
        return KonkursAppClothingCollection(
            captured_at=captured_at,
            from_date=from_date,
            endpoints=endpoints,
            items_received=received,
            leads=tuple(leads),
            scan_complete=not errors,
            errors=tuple(errors),
        )


def write_konkurs_app_artifacts(
    collection: KonkursAppClothingCollection,
    output_dir: str | Path,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / "konkurs-app-clothing-leads.json"
    lead_top5_path = target / "clothing-bankruptcy-leads-top5.json"
    commercial_top5_path = target / "live-clothing-top5.json"
    summary_path = target / "operator-summary.txt"

    report_path.write_text(
        json.dumps(collection.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lead_top5_path.write_text(
        json.dumps(
            [lead.to_dict() for lead in collection.leads[:5]],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    # Bankruptcy registrations are leads, not verified inventory sales.
    commercial_top5_path.write_text("[]\n", encoding="utf-8")

    lines = [
        "Konkurs.app clothing bankruptcy lead adapter",
        f"Lookback from: {collection.from_date}",
        f"API requests: {len(collection.endpoints)}",
        f"Items received: {collection.items_received}",
        f"Clothing bankruptcy leads: {len(collection.leads)}",
        "Verified inventory sales: 0",
        "Commercial Top 5 count: 0",
        f"Scan complete: {collection.scan_complete}",
        f"Errors: {len(collection.errors)}",
        "Paid Brave/OpenAI calls: 0",
        "Personal names retained: 0",
        "",
    ]
    if collection.leads:
        lines.append("Highest-priority leads requiring sale/inventory verification:")
        for lead in collection.leads[:5]:
            lines.append(
                f"- {lead.debtor_name} | {lead.municipality or 'unknown'} | "
                f"opened {lead.opened_date or 'unknown'} | score {lead.priority_score} | "
                f"{lead.url}"
            )
    else:
        lines.append("No recent active clothing bankruptcy leads found.")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "report": report_path,
        "lead_top5": lead_top5_path,
        "commercial_top5": commercial_top5_path,
        "summary": summary_path,
    }
