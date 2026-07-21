#!/usr/bin/env python3
"""Enrich shortlisted Auksjonen opportunities from their public listing pages.

Only directly observed metadata is accepted. Missing or unparseable values remain null.
The script never estimates prices, fees, VAT, transport, resale value, or profit.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _walk(value: object) -> Iterable[dict[str, object]]:
    if isinstance(value, list):
        for item in value:
            yield from _walk(item)
    elif isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)


def _json_ld(html: str) -> Iterable[dict[str, object]]:
    pattern = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)
    for match in pattern.finditer(html):
        try:
            payload = json.loads(match.group(1).strip())
        except (json.JSONDecodeError, TypeError):
            continue
        yield from _walk(payload)


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if value >= 0 else None
    cleaned = re.sub(r'[^0-9,.-]', '', str(value or '')).replace(',', '.')
    try:
        result = float(cleaned)
    except ValueError:
        return None
    return result if result >= 0 else None


def parse_listing_metadata(html: str) -> dict[str, object]:
    result: dict[str, object] = {"asking_price_nok": None, "city": None, "ends_at": None}
    for item in _json_ld(html):
        item_type = str(item.get('@type') or '').casefold()
        if item_type not in {'product', 'offer', 'event'}:
            continue
        offers = item.get('offers') if isinstance(item.get('offers'), dict) else item
        price = _number(offers.get('price')) if isinstance(offers, dict) else None
        if price is not None and result['asking_price_nok'] is None:
            result['asking_price_nok'] = price
        valid_through = offers.get('validThrough') if isinstance(offers, dict) else None
        if valid_through and result['ends_at'] is None:
            result['ends_at'] = str(valid_through)
        address = item.get('address') if isinstance(item.get('address'), dict) else {}
        city = address.get('addressLocality') if isinstance(address, dict) else None
        if city and result['city'] is None:
            result['city'] = ' '.join(str(city).split())

    if result['asking_price_nok'] is None:
        for pattern in (
            r'(?:Høyeste bud|Fastpris|Kjøp nå)\s*[:]?\s*([0-9][0-9 .\u00a0]*)\s*(?:kr|,-)',
            r'"price"\s*:\s*"?([0-9][0-9 .]*)',
        ):
            match = re.search(pattern, html, re.I)
            if match:
                result['asking_price_nok'] = _number(match.group(1))
                break
    return result


def fetch_html(url: str, timeout: float) -> str:
    request = Request(url, headers={
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'nb-NO,nb;q=0.9,en;q=0.7',
        'User-Agent': 'Mozilla/5.0 (compatible; Opportunity-Engine/1.0)',
    })
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        charset = response.headers.get_content_charset() or 'utf-8'
        return response.read().decode(charset, errors='replace')


def enrich(payload: dict[str, object], *, timeout: float = 20.0) -> tuple[dict[str, object], dict[str, object]]:
    queue = payload.get('queue', [])
    if not isinstance(queue, list):
        raise ValueError('queue must be a list')
    evidence: dict[str, object] = {}
    enriched_count = 0
    errors: dict[str, str] = {}
    for item in queue:
        if not isinstance(item, dict):
            continue
        url = str(item.get('url') or '')
        opportunity_id = str(item.get('opportunity_id') or '')
        if 'auksjonen.no/auksjon/' not in url.casefold():
            continue
        try:
            metadata = parse_listing_metadata(fetch_html(url, timeout))
        except (HTTPError, URLError, TimeoutError, RuntimeError, OSError) as exc:
            errors[opportunity_id or url] = str(exc)
            continue
        observed: dict[str, object] = {}
        for field in ('asking_price_nok', 'city', 'ends_at'):
            value = metadata.get(field)
            if value is not None and not item.get(field):
                item[field] = value
                observed[field] = value
        if observed:
            enriched_count += 1
        evidence[opportunity_id] = {
            'source': 'Auksjonen.no public listing page',
            'url': url,
            'captured_at': datetime.now(timezone.utc).isoformat(),
            'observed': observed,
            'verified': bool(observed),
        }
    payload['listing_metadata_enrichment'] = {
        'method': 'directly observed public listing metadata only; no estimates',
        'enriched_count': enriched_count,
        'error_count': len(errors),
    }
    report = {
        'schema_version': 1,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'enriched_count': enriched_count,
        'error_count': len(errors),
        'evidence': evidence,
        'errors': errors,
    }
    return payload, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--queue', default='data/opportunity_review_queue.json')
    parser.add_argument('--output', default='data/opportunity_review_queue.json')
    parser.add_argument('--evidence-output', default='data/listing_metadata_evidence.json')
    parser.add_argument('--timeout', type=float, default=20.0)
    args = parser.parse_args()
    payload = json.loads(Path(args.queue).read_text(encoding='utf-8'))
    enriched, report = enrich(payload, timeout=args.timeout)
    Path(args.output).write_text(json.dumps(enriched, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    Path(args.evidence_output).write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'enriched_count': report['enriched_count'], 'error_count': report['error_count']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
