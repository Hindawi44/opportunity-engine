"""Fail-closed second pass over Norway insolvency sale leads; review only.

A public auction claiming an estate does not establish seller ownership or a
currently purchasable lot. Preserve raw evidence, remove sold items from the
operator cards, and check *explicitly named* estates against the official CCR.
No paid providers, foreign URLs, commerce actions or database modifications.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping

import requests

from scripts.run_norway_insolvency_sample import BASE
from scripts.run_norway_insolvency_sale_links import Page, SOURCES, exact_item, fetch_html

CLOSED = re.compile(r"\bsolgt\b|\bavsluttet\b|\blukket\b|\buts[oø]lgt\b|auksjonen er nå ferdig", re.I)
ESTATE_NAME = re.compile(
    r"\bkonkursbo(?:et)?\s+etter\s+([\wÆØÅæøå&., -]{3,90}?\b(?:AS|ASA|ANS|DA))\b",
    re.I,
)
INSOLVENT_FLAGS = ("konkurs", "underAvvikling", "underTvangsavviklingEllerTvangsopplosning")
MAX_LOOKUPS = 3


def normalized(text: str) -> str:
    return " ".join(str(text).split()).casefold()


def index_says_closed(html: str, title: str) -> bool:
    """Use the named lot's *own* short index-card window, not page-wide Solgt."""
    parser = Page()
    parser.feed(html)
    body = normalized(" ".join(parser.parts))
    needle = normalized(title.split(" Vis overvåkningsliste")[0]).strip()
    if len(needle) < 10:
        return False
    cursor = 0
    while True:
        where = body.find(needle, cursor)
        if where == -1:
            return False
        # Site renders price, bid count, then Solgt within the product card.
        # Never scan an entire page: another lot may be sold while ours is open.
        window = body[where + len(needle):where + len(needle) + 135]
        if CLOSED.search(window.split("pause", 1)[0]):
            return True
        cursor = where + len(needle)


def item_says_closed(html: str, title: str) -> bool:
    parser = Page()
    parser.feed(html)
    body = normalized(" ".join(parser.parts))
    needle = normalized(title.split(" Vis overvåkningsliste")[0]).strip()
    where = body.find(needle) if len(needle) >= 10 else -1
    if where == -1:
        return False  # Missing direct-page proof is UNKNOWN, not ACTIVE.
    return bool(CLOSED.search(body[where + len(needle):where + len(needle) + 220].split("pause", 1)[0]))


def named_estate(html: str) -> str | None:
    parser = Page()
    parser.feed(html)
    # Auction-specific headings and early description only; not site-wide footer.
    text = " ".join(" ".join(parser.parts).split())[:2500]
    for candidate in [*parser.headings[:2], text]:
        match = ESTATE_NAME.search(candidate)
        if match:
            return " ".join(match.group(1).split()).strip("., ")
    return None


def lookup_name(name: str) -> Mapping[str, Any]:
    """One bounded, redirect-free public registry name lookup; no API key."""
    if not 3 <= len(name) <= 100 or not ESTATE_NAME.search("konkursbo etter " + name):
        raise ValueError("Unsafe estate name")
    response = requests.get(BASE, params={"navn": name, "size": 5}, timeout=12,
                            allow_redirects=False, headers={"Accept": "application/json",
                                                            "User-Agent": "OpportunityEngine-NO-estate-identity/1.0"})
    response.raise_for_status()
    if (response.is_redirect or response.url.split("?", 1)[0] != BASE or
            len(response.content) > 500_000):
        raise RuntimeError("Official name lookup redirected or exceeded size budget")
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise RuntimeError("Invalid official lookup response")
    return payload


def official_match(name: str, payload: Mapping[str, Any]) -> dict[str, Any] | None:
    embedded = payload.get("_embedded")
    rows = embedded.get("enheter") if isinstance(embedded, Mapping) else None
    if not isinstance(rows, list):
        return None
    matching = []
    for row in rows[:5]:
        if not isinstance(row, Mapping) or normalized(row.get("navn", "")) != normalized(name):
            continue
        number = str(row.get("organisasjonsnummer") or "")
        address = row.get("forretningsadresse")
        if (len(number) != 9 or not number.isascii() or not number.isdigit() or
                (isinstance(address, Mapping) and address.get("landkode") not in (None, "NO"))):
            continue
        flags = [flag for flag in INSOLVENT_FLAGS if row.get(flag) is True]
        if flags:
            matching.append({"organisation_number": number, "official_event_url": f"{BASE}/{number}",
                             "confirmed_registry_flags": flags})
    return matching[0] if len(matching) == 1 else None


def audit(preliminary: Mapping[str, Any], events: Mapping[str, Any], *,
          loader: Callable[[str], str] = fetch_html,
          registry_lookup: Callable[[str], Mapping[str, Any]] = lookup_name,
          now: datetime | None = None) -> dict[str, Any]:
    if (preliminary.get("schema_version") != "no-insolvency-multisource-evidence-1" or
            preliminary.get("scope") != "NO_ONLY_BANKRUPTCY_LIQUIDATION_ALL_SECTORS" or
            events.get("schema_version") != "norway-insolvency-event-sample-1"):
        raise ValueError("Norway-only original reports required")
    raw = preliminary.get("review_only_unverified_direct_leads")
    if not isinstance(raw, list) or len(raw) > 9:
        raise ValueError("Unbounded or invalid preliminary lead list")
    sample = {}
    for row in events.get("events", []):
        if not isinstance(row, Mapping) or row.get("source_country") != "NO":
            raise ValueError("Untrusted event sample")
        org = str(row.get("organisation_number") or "")
        if row.get("official_url") != f"{BASE}/{org}" or len(org) != 9 or not org.isascii() or not org.isdigit():
            raise ValueError("Invalid official event URL")
        sample[normalized(row.get("company_name", ""))] = row
    errors = list(preliminary.get("source_errors") or [])
    index_cache: dict[str, str | None] = {}
    lookup_cache: dict[str, dict[str, Any] | None] = {}
    included, excluded, quarantine = [], [], []
    for lead in raw:
        source, url = lead.get("source"), lead.get("url")
        if (source not in SOURCES or not isinstance(url, str) or
                exact_item(source, url, SOURCES[source]) != url):
            quarantine.append({"url": url if isinstance(url, str) else None, "reason": "INVALID_OR_NON_NORWEGIAN_ITEM_URL"})
            continue
        item = dict(lead)
        if source not in index_cache:
            try:
                index_cache[source] = loader(SOURCES[source])
            except Exception as exc:
                index_cache[source] = None
                errors.append({"source": source, "stage": "status_index", "reason": f"{type(exc).__name__}: {exc}"})
        index = index_cache[source]
        if source == "Vareauksjonen" and index is not None and index_says_closed(index, str(item.get("title") or "")):
            excluded.append({"url": url, "source": source, "title": item.get("title"),
                             "reason": "SOURCE_INDEX_ITEM_SOLD_OR_ENDED"})
            continue
        try:
            html = loader(url)
        except Exception as exc:
            errors.append({"source": source, "stage": "status_item", "url": url,
                           "reason": f"{type(exc).__name__}: {exc}"})
            quarantine.append({"url": url, "reason": "ITEM_STATUS_FETCH_FAILED"})
            continue
        if item_says_closed(html, str(item.get("title") or "")):
            excluded.append({"url": url, "source": source, "title": item.get("title"),
                             "reason": "SOURCE_ITEM_SOLD_OR_ENDED"})
            continue
        # A failed index prevents claiming current availability; retain only as
        # a clearly labelled identity investigation, never an active sale.
        item["sale_status"] = "UNKNOWN_NOT_VERIFIED_ACTIVE"
        item["availability_verified"] = False
        item["seller_identity_verified"] = False
        item["inventory_verified"] = False
        item["official_entity_status_confirmed"] = False
        estate = named_estate(html)
        item["explicit_estate_name"] = estate
        item["organisation_number"] = None
        item["official_event_url"] = None
        item["relation_evidence"] = "NO_EXPLICIT_ESTATE_COMPANY_NAME"
        if estate:
            existing = sample.get(normalized(estate))
            if existing and set(existing.get("event_kinds", [])) & set(INSOLVENT_FLAGS):
                number = existing["organisation_number"]
                item.update({"organisation_number": number, "official_event_url": existing["official_url"],
                             "official_entity_status_confirmed": True,
                             "relation_evidence": "NAMED_ESTATE_MATCHES_OFFICIAL_SAMPLED_INSOLVENCY"})
            elif estate in lookup_cache or len(lookup_cache) < MAX_LOOKUPS:
                if estate not in lookup_cache:
                    try:
                        lookup_cache[estate] = official_match(estate, registry_lookup(estate))
                    except Exception as exc:
                        lookup_cache[estate] = None
                        errors.append({"source": "Brreg", "stage": "estate_name", "name": estate,
                                       "reason": f"{type(exc).__name__}: {exc}"})
                verified = lookup_cache[estate]
                if verified:
                    item.update(verified)
                    item["official_entity_status_confirmed"] = True
                    item["relation_evidence"] = "NAMED_ESTATE_MATCHES_LIVE_OFFICIAL_INSOLVENCY"
                else:
                    item["relation_evidence"] = "NAMED_ESTATE_NOT_OFFICIALLY_CONFIRMED"
            else:
                item["relation_evidence"] = "OFFICIAL_NAME_LOOKUP_BUDGET_EXHAUSTED"
        included.append(item)
    result = dict(preliminary)
    result.update({"schema_version": "no-insolvency-status-audited-1",
                   "status_audited_at": (now or datetime.now(timezone.utc)).isoformat(),
                   "precheck_unverified_lead_count": len(raw),
                   "review_only_unverified_direct_leads": included, "unverified_lead_count": len(included),
                   "sale_closed_excluded_after_recheck": len(excluded), "closed_or_sold_evidence": excluded,
                   "status_check_quarantined": quarantine,
                   "named_estates_registry_confirmed": sum(bool(x["official_entity_status_confirmed"]) for x in included),
                   "official_name_lookups": len(lookup_cache), "source_errors": errors,
                   "verified_insolvency_sale_count": 0, "verified_insolvency_sale_links": [],
                   "source_coverage_complete": False})
    return result


def render_arabic(result: Mapping[str, Any]) -> str:
    lines = ["النرويج — مراجعة حالة البيع والارتباط الرسمي (محدودة، وليست بحثًا شاملًا).",
             f"روابط أولية: {result['precheck_unverified_lead_count']} | استبعدت كمباعة أو منتهية: {result['sale_closed_excluded_after_recheck']} | روابط غير مثبتة للمراجعة: {result['unverified_lead_count']} | مبيعات إفلاس مؤكدة: 0",
             "حالة البيع غير المثبتة لا تعني أن المزاد مفتوح. دعوى الإفلاس وحدها لا تثبت صلة الشركة أو ملكية الأصول."]
    for lead in result["review_only_unverified_direct_leads"]:
        lines.extend(["", f"{lead['source']}: {lead['title']}", lead["url"],
                      f"صلة الشركة: {lead['relation_evidence']} | حالة البيع: {lead['sale_status']}"])
    for row in result["closed_or_sold_evidence"]:
        lines.append(f"استُبعد من المراجعة: {row['url']} — {row['reason']}")
    for row in result["status_check_quarantined"]:
        lines.append(f"حُجر للتحقق: {row['url']} — {row['reason']}")
    for error in result["source_errors"]:
        lines.append(f"تعذر التحقق: {error}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    original = args.output_dir / "insolvency-sale-link-investigations.json"
    raw = original.read_text(encoding="utf-8")
    report = audit(json.loads(raw), json.loads(args.events.read_text(encoding="utf-8")))
    # Preserve the raw study before replacing operator-facing evidence.
    (args.output_dir / "insolvency-sale-link-precheck.json").write_text(raw, encoding="utf-8")
    previous_ar = args.output_dir / "insolvency-sale-link-investigations-ar.txt"
    if previous_ar.exists():
        (args.output_dir / "insolvency-sale-link-precheck-ar.txt").write_text(
            previous_ar.read_text(encoding="utf-8"), encoding="utf-8")
    original.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    previous_ar.write_text(render_arabic(report), encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "precheck_unverified_lead_count", "sale_closed_excluded_after_recheck",
        "unverified_lead_count", "named_estates_registry_confirmed",
        "official_name_lookups", "verified_insolvency_sale_count", "source_errors")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
