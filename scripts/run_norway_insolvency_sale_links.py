"""Bounded Norway-only cross-site insolvency-sale leads, review-only.

An official company event and a listing claim do not prove identity, stock,
availability or permission to buy. No paid APIs, foreign searches or DB writes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping
from urllib.parse import urljoin, urlsplit

import requests

SOURCES = {
    "Norsk Avvikling": "https://norskavvikling.no/butikk/",
    "Vareauksjonen": "https://www.vareauksjonen.no/",
    "Auksjonen": "https://www.auksjonen.no/auksjoner/torget/vareparti-og-konkursbo",
}
INSOLVENCY = re.compile(r"konkurs(?:bo(?:et|ets)?|salg|rammet)?|avvikling|opphørssalg|tømmesalg", re.I)
# Do not match "alle produkter kan være fra konkursbo" in generic page boilerplate.
ITEM_ESTATE = re.compile(
    r"selges\s+av\s*:\s*konkursbo|selges\s+fra\s+(?:ett?\s+)?konkursbo"
    r"|konkursboet\s+etter|konkurssalg\s+p[åa]g[åa]r", re.I,
)
ENDED = re.compile(r"denne auksjonen er nå ferdig|auksjon(?:en)? er avsluttet|auksjon avsluttet|\bsolgt\b|\bavsluttet\b", re.I)
MAX_BYTES = 1_500_000


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self.headings: list[str] = []
        self.parts: list[str] = []
        self.href: str | None = None
        self.anchor_parts: list[str] = []
        self.heading = False
        self.heading_parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in {"script", "style"}:
            self.skip += 1
        if tag == "a" and values.get("href") and self.href is None:
            self.href = str(values["href"])
            self.anchor_parts = [str(values.get("title") or values.get("aria-label") or "")]
        if tag == "img" and self.href is not None:
            self.anchor_parts.append(str(values.get("alt") or ""))
        if tag == "h1":
            self.heading = True
            self.heading_parts = []

    def handle_data(self, value: str) -> None:
        if self.skip:
            return
        self.parts.append(value)
        if self.href is not None:
            self.anchor_parts.append(value)
        if self.heading:
            self.heading_parts.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1
        if tag == "a" and self.href is not None:
            self.anchors.append((self.href, " ".join(" ".join(self.anchor_parts).split())))
            self.href = None
        if tag == "h1" and self.heading:
            self.headings.append(" ".join(" ".join(self.heading_parts).split()))
            self.heading = False


def exact_item(source: str, raw: str, index: str) -> str | None:
    try:
        url = urljoin(index, raw)
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.query or parsed.fragment or
                parsed.username or parsed.password or parsed.port not in (None, 443)):
            return None
        host, path = (parsed.hostname or "").lower(), parsed.path
        if source == "Norsk Avvikling":
            valid = host in {"norskavvikling.no", "www.norskavvikling.no"} and bool(re.fullmatch(r"/produkt/[a-z0-9-]+/?", path, re.I))
        elif source == "Vareauksjonen":
            valid = host in {"vareauksjonen.no", "www.vareauksjonen.no"} and bool(re.fullmatch(r"/Event/Details/\d+/[^?#]+/C\d+(?:/[^?#]+)?/?", path, re.I))
        elif source == "Auksjonen":
            valid = host in {"auksjonen.no", "www.auksjonen.no"} and bool(re.fullmatch(r"/auksjon/(torget|overskuddsvarer)/[^/]+/\d{4,}/?", path, re.I))
        else:
            valid = False
        return url if valid else None
    except ValueError:
        return None


def fetch_html(url: str) -> str:
    """Only allowlisted public HTTPS pages, no redirects; cap decoded HTML."""
    if not any(url == index or exact_item(name, url, index) == url for name, index in SOURCES.items()):
        raise ValueError("Unapproved Norwegian public source URL")
    response = requests.get(url, timeout=12, allow_redirects=False,
                            headers={"User-Agent": "OpportunityEngine-NO-insolvency/1.1", "Accept": "text/html"},
                            stream=True)
    try:
        response.raise_for_status()
        if response.is_redirect or "html" not in response.headers.get("content-type", "").lower():
            raise RuntimeError("Redirect or non-HTML response")
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(chunk_size=65536):
            size += len(chunk)
            if size > MAX_BYTES:
                raise RuntimeError("Public page exceeds bounded decompressed size")
            chunks.append(chunk)
        return b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
    finally:
        response.close()


def discover(events_report: Mapping[str, Any], *, loader: Callable[[str], str] = fetch_html,
             max_details: int = 9, now: datetime | None = None) -> dict[str, Any]:
    if events_report.get("schema_version") != "norway-insolvency-event-sample-1":
        raise ValueError("Official Norway event report is required")
    if not 1 <= max_details <= 9:
        raise ValueError("Detail page budget must be 1..9")
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    events = events_report.get("events")
    if not isinstance(events, list):
        raise ValueError("Official report must include actual sampled events")
    companies = {}
    for event in events:
        if not isinstance(event, dict) or event.get("source_country") != "NO":
            raise ValueError("Invalid event source")
        org = str(event.get("organisation_number") or "")
        if not (len(org) == 9 and org.isascii() and org.isdigit() and
                event.get("official_url") == f"https://data.brreg.no/enhetsregisteret/api/enheter/{org}"):
            raise ValueError("Official organisation evidence missing")
        companies[org] = event
    errors: list[dict[str, str]] = []
    sources: list[dict[str, Any]] = []
    urls: dict[str, tuple[str, str]] = {}
    auksjonen_fallback: dict[str, tuple[str, str]] = {}
    for name, index in SOURCES.items():
        try:
            page = Page()
            page.feed(loader(index))
            exact = 0
            found = 0
            for href, label in page.anchors:
                direct = exact_item(name, href, index)
                if direct:
                    exact += 1
                    if INSOLVENCY.search(label + " " + urlsplit(direct).path):
                        urls.setdefault(direct, (name, label))
                        found += 1
                    elif name == "Auksjonen" and len(auksjonen_fallback) < 8:
                        # A category is not estate proof. Check a few exact item
                        # descriptions for explicit estate-sale wording.
                        auksjonen_fallback.setdefault(direct, (name, label))
            if not page.anchors:
                status = "NO_ANCHORS_UNVERIFIED_NOT_ZERO"
                errors.append({"source": name, "stage": "index", "reason": "No HTML anchors extracted; not evidence of zero listings"})
            elif not exact:
                status = "NO_SUPPORTED_INDIVIDUAL_ROUTES_UNVERIFIED"
                errors.append({"source": name, "stage": "index", "reason": "Site links do not match supported exact-item routes; coverage incomplete"})
            else:
                status = "READ_BOUNDED"
            sources.append({"source": name, "index_url": index, "status": status,
                            "html_anchor_count": len(page.anchors), "individual_listing_links": exact,
                            "bankruptcy_labeled_exact_links": found})
        except Exception as exc:
            errors.append({"source": name, "stage": "index", "reason": f"{type(exc).__name__}: {exc}"})
            sources.append({"source": name, "index_url": index, "status": "FAILED_NOT_ZERO",
                            "html_anchor_count": None, "individual_listing_links": None,
                            "bankruptcy_labeled_exact_links": None})
    for url, row in auksjonen_fallback.items():
        urls.setdefault(url, row)
    leads: list[dict[str, Any]] = []
    closed = 0
    checked = 0
    for url, (name, label) in list(urls.items())[:max_details]:
        checked += 1
        try:
            page = Page()
            page.feed(loader(url))
            heading = page.headings[0] if page.headings else ""
            if not heading:
                continue
            text = " ".join(" ".join(page.parts).split())
            start = text.find(heading)
            item_text = text[max(0, start):max(0, start) + 3500]
            if not (INSOLVENCY.search(heading) or ITEM_ESTATE.search(item_text[:1800])):
                continue
            if ENDED.search(item_text):
                closed += 1
                continue
            relation = "NO_OFFICIAL_COMPANY_MATCH_SOURCE_CLAIM_ONLY"
            org = None
            for number, event in companies.items():
                company = str(event["company_name"]).strip()
                if re.search(rf"(?<!\d){re.escape(number)}(?!\d)", item_text):
                    org, relation = number, "ORGANISATION_NUMBER_ON_PAGE_NOT_SELLER_VERIFIED"
                    break
                if len(company) >= 8 and company.casefold() in item_text.casefold():
                    org, relation = number, "COMPANY_NAME_ON_PAGE_NOT_SELLER_VERIFIED"
                    break
            leads.append({"source": name, "url": url, "title": heading, "index_label": label,
                          "organisation_number": org,
                          "official_event_url": companies[org]["official_url"] if org else None,
                          "relation_evidence": relation,
                          "sale_status": "UNVERIFIED_NO_SOURCE_NATIVE_OPEN_PROOF",
                          "seller_identity_verified": False, "availability_verified": False,
                          "inventory_verified": False, "review_only": True, "captured_at": stamp})
        except Exception as exc:
            errors.append({"source": name, "stage": "item", "url": url,
                           "reason": f"{type(exc).__name__}: {exc}"})
    return {"schema_version": "no-insolvency-multisource-evidence-1", "captured_at": stamp,
            "scope": "NO_ONLY_BANKRUPTCY_LIQUIDATION_ALL_SECTORS",
            "event_sample_count": len(companies), "marketplace_sources": sources,
            "candidate_exact_urls_from_indices": len(urls), "detail_pages_checked": checked,
            "detail_budget": max_details, "closed_pages_excluded": closed,
            "review_only_unverified_direct_leads": leads, "unverified_lead_count": len(leads),
            "verified_insolvency_sale_count": 0, "verified_insolvency_sale_links": [],
            "source_errors": errors, "source_coverage_complete": False,
            "paid_provider_requests": 0, "automatic_contact": False, "automatic_bid": False,
            "automatic_purchase": False, "automatic_payment": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-details", type=int, default=9)
    args = parser.parse_args()
    result = discover(json.loads(args.events.read_text(encoding="utf-8")), max_details=args.max_details)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "insolvency-sale-link-investigations.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["النرويج — متابعة روابط بيع متعلقة بالإفلاس: أدلة بحث، لا فرص بيع مؤكدة.",
             f"مصادر جرى اختبارها: {len(SOURCES)} | روابط فردية تحتاج مراجعة: {result['unverified_lead_count']} | روابط بيع إفلاس مثبتة: 0"]
    for item in result["review_only_unverified_direct_leads"]:
        lines += [f"{item['source']}: {item['title']}", item["url"],
                  f"الصلة: {item['relation_evidence']} | البيع وتوافر الأصول غير مثبتين."]
    for failure in result["source_errors"]:
        lines.append(f"تعذر التحقق من {failure['source']}: {failure['reason']}")
    (args.output_dir / "insolvency-sale-link-investigations-ar.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("event_sample_count", "candidate_exact_urls_from_indices", "detail_pages_checked", "unverified_lead_count", "closed_pages_excluded", "verified_insolvency_sale_count", "source_errors")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
