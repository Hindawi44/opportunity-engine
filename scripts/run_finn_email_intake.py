#!/usr/bin/env python3
"""Read FINN saved-search emails and pass them through the existing pipeline."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import quote

import requests

from opportunity_engine.discovery.finn_email_intake import (
    FinnEmailMessage,
    collect_finn_saved_search_messages,
    message_from_mapping,
    message_from_rfc822,
    run_finn_email_intake,
    write_finn_email_intake_artifacts,
)
from opportunity_engine.discovery.multi_market_operator_checkpoint import (
    opportunity_identity,
)

GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_MESSAGES_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
DEFAULT_GMAIL_QUERY = 'from:agent@finn.no subject:"Nye annonser:" newer_than:7d'
DEFAULT_MAX_MESSAGES = 20
MAX_GMAIL_MESSAGES = 50
DEFAULT_TIMEOUT_SECONDS = 20.0
_AUKSJONEN_SELLER_RE = re.compile(r"\bauksjonen(?:\.no)?\s+as\b", re.IGNORECASE)


def _load_json(path: Path) -> list[FinnEmailMessage]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
        payload = payload["messages"]
    elif isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError(f"{path}: JSON must be a message object or messages list")
    messages: list[FinnEmailMessage] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError(f"{path}: every message must be an object")
        messages.append(message_from_mapping(item))
    return messages


def _load(path: Path) -> list[FinnEmailMessage]:
    if path.suffix.casefold() == ".json":
        return _load_json(path)
    return [message_from_rfc822(path.read_bytes())]


def _json_object(response: requests.Response, *, label: str) -> Mapping[str, Any]:
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{label} returned invalid JSON") from exc
    if not isinstance(payload, Mapping):
        raise RuntimeError(f"{label} must return a JSON object")
    return payload


def _decode_gmail_raw(value: object) -> bytes:
    encoded = str(value or "").strip()
    if not encoded:
        raise RuntimeError("Gmail message response did not contain raw RFC822 data")
    encoded += "=" * (-len(encoded) % 4)
    try:
        return base64.urlsafe_b64decode(encoded.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise RuntimeError("Gmail message response contained invalid raw data") from exc


def fetch_finn_messages_from_gmail(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    *,
    query: str = DEFAULT_GMAIL_QUERY,
    max_messages: int = DEFAULT_MAX_MESSAGES,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    session: requests.Session | None = None,
) -> list[FinnEmailMessage]:
    """Fetch a bounded set of FINN alerts through the read-only Gmail API."""
    if not client_id or not client_secret or not refresh_token:
        raise RuntimeError("Gmail OAuth credentials are incomplete")
    if not 1 <= max_messages <= MAX_GMAIL_MESSAGES:
        raise ValueError(f"max_messages must be between 1 and {MAX_GMAIL_MESSAGES}")
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    http = session or requests.Session()
    token = _json_object(
        http.post(
            GMAIL_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            headers={"Accept": "application/json"},
            timeout=timeout,
        ),
        label="Gmail OAuth token endpoint",
    )
    access_token = str(token.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError("Gmail OAuth token response did not contain an access token")

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    listing = _json_object(
        http.get(
            GMAIL_MESSAGES_URL,
            params={"q": query, "maxResults": max_messages},
            headers=headers,
            timeout=timeout,
        ),
        label="Gmail messages list",
    )
    references = listing.get("messages") or []
    if not isinstance(references, list):
        raise RuntimeError("Gmail messages list returned an invalid messages field")

    messages: list[FinnEmailMessage] = []
    for reference in references[:max_messages]:
        if not isinstance(reference, Mapping):
            continue
        message_id = str(reference.get("id") or "").strip()
        if not message_id:
            continue
        payload = _json_object(
            http.get(
                f"{GMAIL_MESSAGES_URL}/{quote(message_id, safe='')}",
                params={"format": "raw"},
                headers=headers,
                timeout=timeout,
            ),
            label="Gmail raw message",
        )
        messages.append(message_from_rfc822(_decode_gmail_raw(payload.get("raw"))))
    return messages


def _normalized_title(value: object) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", str(value or "").casefold()).split())


def _candidate_urls(candidate: Mapping[str, Any]) -> set[str]:
    urls = {
        str(value).strip()
        for value in candidate.get("source_urls") or []
        if str(value).strip()
    }
    canonical = str(candidate.get("canonical_url") or candidate.get("url") or "").strip()
    if canonical:
        urls.add(canonical)
    return urls


def link_auksjonen_channels(
    result: dict[str, Any],
    messages: Iterable[FinnEmailMessage],
    auksjonen_report_path: str | Path | None,
) -> int:
    """Alias exact FINN/Auksjonen duplicates to one opportunity identity.

    Linking is deliberately narrow: the FINN email must explicitly identify
    ``Auksjonen.No AS`` as seller and its normalized title must match exactly one
    clothing-lot title in the already-collected Auksjonen report.
    """
    if not auksjonen_report_path:
        return 0
    path = Path(auksjonen_report_path)
    if not path.exists():
        return 0

    payload = json.loads(path.read_text(encoding="utf-8"))
    listings = payload.get("listings") if isinstance(payload, Mapping) else None
    if not isinstance(listings, list):
        return 0

    collection = collect_finn_saved_search_messages(messages)
    lead_by_url = {lead.url: lead for lead in collection.leads}
    title_index: dict[str, list[Mapping[str, Any]]] = {}
    for item in listings:
        if not isinstance(item, Mapping) or item.get("inventory_lot_signal") is not True:
            continue
        title = _normalized_title(item.get("title") or item.get("name"))
        if title:
            title_index.setdefault(title, []).append(item)

    linked = 0
    linked_urls: set[str] = set()
    for output_name in ("all_discovered_candidates", "discovery_top5"):
        for candidate in result.get(output_name) or []:
            if not isinstance(candidate, dict):
                continue
            lead = next(
                (lead_by_url[url] for url in _candidate_urls(candidate) if url in lead_by_url),
                None,
            )
            if lead is None or not _AUKSJONEN_SELLER_RE.search(lead.description):
                continue
            matches = title_index.get(_normalized_title(lead.title), [])
            if len(matches) != 1:
                continue
            auction = matches[0]
            identity = opportunity_identity(auction, "Auksjonen.no")
            candidate["opportunity_identity"] = identity
            candidate["cross_channel_link"] = {
                "status": "EXACT_TITLE_AND_SELLER_MATCH",
                "upstream_channel": "FINN_SAVED_SEARCH_EMAIL",
                "sale_channel": "Auksjonen.no",
                "seller_evidence": "Auksjonen.No AS",
            }
            for capture in candidate.get("source_capture") or []:
                if isinstance(capture, dict):
                    capture["related_sale_channel"] = "Auksjonen.no"
                    capture["relation_status"] = "EXACT_TITLE_AND_SELLER_MATCH"
            if lead.url not in linked_urls:
                linked_urls.add(lead.url)
                linked += 1

    report = result.get("search_run_report")
    if isinstance(report, dict):
        report["auksjonen_cross_channel_links"] = linked
        report["cross_channel_link_method"] = "EXACT_TITLE_AND_SELLER_MATCH"
    return linked


def _gmail_credentials() -> tuple[str, str, str]:
    return (
        os.environ.get("GMAIL_CLIENT_ID", "").strip(),
        os.environ.get("GMAIL_CLIENT_SECRET", "").strip(),
        os.environ.get("GMAIL_REFRESH_TOKEN", "").strip(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "message_files",
        nargs="*",
        help="RFC822 .eml or connector-export .json files",
    )
    parser.add_argument(
        "--gmail-api",
        action="store_true",
        help="Read bounded FINN alerts from Gmail using repository secrets",
    )
    parser.add_argument("--gmail-query", default=DEFAULT_GMAIL_QUERY)
    parser.add_argument("--max-messages", type=int, default=DEFAULT_MAX_MESSAGES)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--auksjonen-report",
        help="Optional current Auksjonen report used for narrow cross-channel aliasing",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/finn-email-intake",
    )
    args = parser.parse_args()

    if not args.message_files and not args.gmail_api:
        parser.error("supply message files or use --gmail-api")

    messages = [
        message
        for raw_path in args.message_files
        for message in _load(Path(raw_path))
    ]
    if args.gmail_api:
        messages.extend(fetch_finn_messages_from_gmail(
            *_gmail_credentials(),
            query=args.gmail_query,
            max_messages=args.max_messages,
            timeout=args.timeout,
        ))

    collection = collect_finn_saved_search_messages(messages)
    result = run_finn_email_intake(collection)
    link_auksjonen_channels(result, messages, args.auksjonen_report)
    paths = write_finn_email_intake_artifacts(
        result,
        collection,
        Path(args.output_dir),
    )

    report = result["search_run_report"]
    print(f"Execution status: {report['execution_status']}")
    print(f"Accepted FINN messages: {report['email_messages_accepted']}")
    print(f"Extracted FINN leads: {report['email_leads_extracted']}")
    print(f"Auksjonen cross-channel links: {report.get('auksjonen_cross_channel_links', 0)}")
    print(f"Analysis-eligible opportunities: {report['analysis_eligible_count']}")
    print(f"Top opportunities requiring review: {report['top5_count']}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
