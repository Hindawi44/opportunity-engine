"""Bounded single-case estate-manager enrichment for a reviewed bankruptcy lead.

The pilot performs exactly one manually selected Konkurs.app estate lookup. It
retains only company identifiers and the publicly registered professional
estate-manager role needed for human review. It does not build a person database,
search broadly, contact anyone, or treat the bankruptcy as an inventory sale.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse
from urllib.request import Request, urlopen

API_BASE = "https://konkurs.app/api/konkursbo"


def _compact(value: object) -> str:
    return " ".join(str(value or "").split())


def _valid_orgnr(value: object) -> bool:
    text = _compact(value)
    return len(text) == 9 and text.isdigit()


def build_single_estate_endpoint(estate_orgnr: str) -> str:
    value = _compact(estate_orgnr)
    if not _valid_orgnr(value):
        raise ValueError("estate_orgnr must be nine digits")
    return f"{API_BASE}/{value}"


def is_approved_single_estate_endpoint(url: str, *, estate_orgnr: str) -> bool:
    parsed = urlparse(_compact(url))
    expected = build_single_estate_endpoint(estate_orgnr)
    return (
        _compact(url) == expected
        and parsed.scheme == "https"
        and parsed.hostname == "konkurs.app"
        and parsed.path == f"/api/konkursbo/{estate_orgnr}"
        and not parsed.query
        and not parsed.fragment
    )


def build_official_estate_url(estate_orgnr: str) -> str:
    value = _compact(estate_orgnr)
    if not _valid_orgnr(value):
        raise ValueError("estate_orgnr must be nine digits")
    return f"https://virksomhet.brreg.no/nb/oppslag/enheter/{value}"


@dataclass(frozen=True, slots=True)
class EstateManagerEnrichment:
    captured_at: str
    estate_orgnr: str
    estate_name: str
    debtor_orgnr: str
    debtor_name: str
    opened_date: str | None
    industry_code: str | None
    industry_description: str | None
    municipality: str | None
    estate_manager_name: str | None
    source_endpoint: str

    def to_dict(self) -> dict[str, Any]:
        manager_found = bool(self.estate_manager_name)
        return {
            "schema_version": "estate-manager-enrichment-pilot-1.0",
            "captured_at": self.captured_at,
            "estate_orgnr": self.estate_orgnr,
            "estate_name": self.estate_name,
            "debtor_orgnr": self.debtor_orgnr,
            "debtor_name": self.debtor_name,
            "opened_date": self.opened_date,
            "industry_code": self.industry_code,
            "industry_description": self.industry_description,
            "municipality": self.municipality,
            "estate_manager_name": self.estate_manager_name,
            "estate_manager_identified": manager_found,
            "lead_stage": (
                "ESTATE_MANAGER_IDENTIFIED" if manager_found else "ESTATE_MANAGER_UNKNOWN"
            ),
            "professional_role_only": True,
            "person_data_scope": "PUBLIC_PROFESSIONAL_ROLE_ONLY",
            "official_estate_url": build_official_estate_url(self.estate_orgnr),
            "source_endpoint": self.source_endpoint,
            "public_sale_found": False,
            "inventory_sale_verified": False,
            "inventory_quantity_verified": False,
            "listing_status": "UNKNOWN",
            "top5_eligible": False,
            "analysis_eligible": False,
            "operator_review_required": True,
            "automatic_contact": False,
            "automatic_bid": False,
            "automatic_purchase_decision": False,
            "automatic_payment": False,
        }


def normalize_single_estate_record(
    record: Mapping[str, Any],
    *,
    requested_estate_orgnr: str,
    captured_at: str | None = None,
) -> EstateManagerEnrichment:
    estate_orgnr = _compact(record.get("orgnr"))
    if estate_orgnr != requested_estate_orgnr or not _valid_orgnr(estate_orgnr):
        raise ValueError("response estate orgnr does not match requested estate")
    if not bool(record.get("aktiv")):
        raise ValueError("estate is not active")

    estate_name = _compact(record.get("navn"))
    debtor_orgnr = _compact(record.get("debitor_orgnr"))
    debtor_name = _compact(record.get("debitor_navn"))
    if not estate_name or not debtor_name or not _valid_orgnr(debtor_orgnr):
        raise ValueError("response lacks required company identity fields")

    manager_name = _compact(record.get("bostyrer")) or None
    return EstateManagerEnrichment(
        captured_at=captured_at or datetime.now(timezone.utc).isoformat(),
        estate_orgnr=estate_orgnr,
        estate_name=estate_name,
        debtor_orgnr=debtor_orgnr,
        debtor_name=debtor_name,
        opened_date=_compact(record.get("stiftelsesdato")) or None,
        industry_code=_compact(record.get("naeringskode")) or None,
        industry_description=_compact(record.get("naeringsbeskrivelse")) or None,
        municipality=_compact(record.get("kommune")) or None,
        estate_manager_name=manager_name,
        source_endpoint=build_single_estate_endpoint(estate_orgnr),
    )


class EstateManagerEnrichmentCollector:
    """Fetch one explicitly selected active estate record and nothing else."""

    def __init__(
        self,
        *,
        estate_orgnr: str,
        timeout_seconds: float = 30.0,
        fetch_json: Callable[[str], Mapping[str, Any]] | None = None,
    ) -> None:
        self.estate_orgnr = _compact(estate_orgnr)
        build_single_estate_endpoint(self.estate_orgnr)
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds
        self.fetch_json = fetch_json or self._fetch

    def _fetch(self, url: str) -> Mapping[str, Any]:
        if not is_approved_single_estate_endpoint(url, estate_orgnr=self.estate_orgnr):
            raise ValueError("endpoint is outside the approved single-estate scope")
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "OpportunityEngine/EstateManager-Enrichment-Pilot-1.0",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            if int(response.status) != 200:
                raise RuntimeError(f"Konkurs.app API returned HTTP {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise RuntimeError("Konkurs.app API response is not a JSON object")
        return payload

    def collect(self) -> EstateManagerEnrichment:
        endpoint = build_single_estate_endpoint(self.estate_orgnr)
        payload = self.fetch_json(endpoint)
        return normalize_single_estate_record(
            payload,
            requested_estate_orgnr=self.estate_orgnr,
        )


def write_estate_manager_artifacts(
    enrichment: EstateManagerEnrichment,
    output_dir: str | Path,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    enrichment_path = target / "estate-manager-enrichment.json"
    commercial_top5_path = target / "live-clothing-top5.json"
    summary_path = target / "operator-summary.txt"

    enrichment_path.write_text(
        json.dumps(enrichment.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    commercial_top5_path.write_text("[]\n", encoding="utf-8")

    payload = enrichment.to_dict()
    lines = [
        "Single-case estate-manager enrichment pilot",
        f"Estate: {enrichment.estate_name} ({enrichment.estate_orgnr})",
        f"Debtor: {enrichment.debtor_name} ({enrichment.debtor_orgnr})",
        f"Estate manager identified: {payload['estate_manager_identified']}",
        f"Estate manager professional role: {enrichment.estate_manager_name or 'unknown'}",
        f"Lead stage: {payload['lead_stage']}",
        "Public sale found: false",
        "Verified inventory sale: false",
        "Commercial Top 5 count: 0",
        "Automatic contact/bid/purchase/payment: false",
        f"Official estate URL: {payload['official_estate_url']}",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "enrichment": enrichment_path,
        "commercial_top5": commercial_top5_path,
        "summary": summary_path,
    }
