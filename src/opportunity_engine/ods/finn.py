"""Authorized FINN API connector.

FINN API access is restricted to advertisers and business partners with a valid
agreement, API key, and rights to the relevant advert data. This module does not
scrape public FINN pages and must not be used to bypass FINN access controls.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .live_data import SourceDocument
from .models import ODSRequest

FINN_API_BASE = "https://cache.api.finn.no/iad"
FINN_API_KEY_HEADER = "x-FINN-apikey"
XmlTransport = Callable[[str, float, dict[str, str]], bytes]

_ATOM = "{http://www.w3.org/2005/Atom}"

TARGET_FINN_TERMS = (
    "butikkinnredning", "butikkutstyr", "klesstativ", "hylle", "vitrineskap",
    "butikkdisk", "kassadisk", "mannekeng", "varelager", "restparti",
    "konkurslager", "overskuddslager", "kontormøbler", "kontorstol",
    "skrivebord", "arkivskap", "lagerreol", "pallereol", "lagerutstyr",
    "kjøledisk", "fryser", "kaffemaskin", "kassesystem", "industrisymaskin",
    "symaskin", "overlock", "tekstil", "stoffparti",
)

EXCLUDED_FINN_TERMS = (
    "personbil", "varebil", "lastebil", "motorsykkel", "båt", "bolig",
    "leilighet", "tomt", "iphone", "samsung galaxy", "mobiltelefon",
    "barneklær", "dameklær", "herreklær", "sko", "småelektrisk",
)


def _default_xml_transport(url: str, timeout: float, headers: dict[str, str]) -> bytes:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS base
            return response.read()
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise RuntimeError("FINN API authorization failed; verify API agreement, key, and orgId") from exc
        raise RuntimeError(f"FINN API returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"FINN API request failed: {exc.reason}") from exc


@dataclass(frozen=True)
class FinnApiClient:
    """Small client for an authorized FINN Atom search feed."""

    api_key: str
    org_id: str
    market: str = "bap/forsale"
    timeout: float = 15.0
    base_url: str = FINN_API_BASE
    transport: XmlTransport = _default_xml_transport

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("FINN api_key must not be empty")
        if not self.org_id.strip():
            raise ValueError("FINN org_id must not be empty")
        if not re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", self.market.strip()):
            raise ValueError("FINN market contains unsupported characters")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if not self.base_url.startswith("https://"):
            raise ValueError("FINN base_url must use HTTPS")

    @property
    def headers(self) -> dict[str, str]:
        return {
            FINN_API_KEY_HEADER: self.api_key,
            "Accept": "application/atom+xml",
            "User-Agent": "ODS-Opportunity-Engine/0.5",
        }

    def search(self, *, keyword: str | None = None, rows: int = 30) -> tuple[SourceDocument, ...]:
        if not 1 <= rows <= 1000:
            raise ValueError("rows must be between 1 and 1000")
        params = {"orgId": self.org_id, "rows": rows}
        if keyword and keyword.strip():
            params["q"] = keyword.strip()
        url = f"{self.base_url}/search/{self.market}?{urlencode(params)}"
        payload = self.transport(url, self.timeout, self.headers)
        return parse_finn_atom_feed(payload)

    def search_targeted_business_listings(self, *, rows_per_query: int = 25) -> tuple[SourceDocument, ...]:
        """Run a small authorized query set for commercial resale opportunities."""
        if not 1 <= rows_per_query <= 100:
            raise ValueError("rows_per_query must be between 1 and 100")
        documents: list[SourceDocument] = []
        seen: set[str] = set()
        for keyword in TARGET_FINN_TERMS:
            for document in self.search(keyword=keyword, rows=rows_per_query):
                searchable = f"{document.title} {document.text}".casefold()
                if any(term in searchable for term in EXCLUDED_FINN_TERMS):
                    continue
                if document.document_id in seen:
                    continue
                seen.add(document.document_id)
                metadata = dict(document.metadata)
                metadata["discovery_query"] = keyword
                metadata["targeted_business_listing"] = True
                documents.append(
                    SourceDocument(
                        document_id=document.document_id,
                        source_name=document.source_name,
                        source_type=document.source_type,
                        title=document.title,
                        text=document.text,
                        url=document.url,
                        published_at=document.published_at,
                        country=document.country,
                        metadata=metadata,
                    )
                )
        return tuple(documents)


@dataclass(frozen=True)
class FinnConnector:
    """Normalize authorized FINN adverts into ODS source documents."""

    client: FinnApiClient
    rows: int = 30
    name: str = "finn_authorized_api"

    def fetch(self, request: ODSRequest) -> tuple[SourceDocument, ...]:
        return self.client.search(keyword=request.subject, rows=self.rows)


def parse_finn_atom_feed(payload: bytes | str) -> tuple[SourceDocument, ...]:
    """Parse a FINN Atom feed defensively; unknown fields are ignored."""
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise RuntimeError("FINN API returned invalid Atom XML") from exc

    documents: list[SourceDocument] = []
    for entry in root.findall(f"{_ATOM}entry"):
        raw_id = _text(entry.find(f"{_ATOM}id"))
        title = _text(entry.find(f"{_ATOM}title")) or "FINN advert"
        summary = _text(entry.find(f"{_ATOM}summary"))
        content = _text(entry.find(f"{_ATOM}content"))
        url = _best_link(entry)
        updated = _parse_datetime(_text(entry.find(f"{_ATOM}updated")))
        document_id = _document_id(raw_id, url, title)
        text = _strip_html(" ".join(part for part in (summary, content) if part).strip())
        if not text:
            text = title
        documents.append(
            SourceDocument(
                document_id=f"finn-{document_id}",
                source_name="FINN.no",
                source_type="authorized_classified_ad",
                title=title,
                text=text,
                url=url,
                published_at=updated,
                country="Norway",
                metadata={
                    "access_mode": "authorized_api",
                    "raw_atom_id": raw_id,
                },
            )
        )
    return tuple(documents)


def _best_link(entry: ElementTree.Element) -> str | None:
    fallback = None
    for link in entry.findall(f"{_ATOM}link"):
        href = link.attrib.get("href")
        if not href:
            continue
        href = href.strip()
        rel = link.attrib.get("rel")
        if rel == "alternate":
            return href
        if rel == "self":
            fallback = href
    return fallback


def _text(element: ElementTree.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _document_id(raw_id: str, url: str | None, title: str) -> str:
    material = raw_id or url or title
    match = re.search(r"(\d{5,})", material)
    if match:
        return match.group(1)
    return re.sub(r"[^a-z0-9]+", "-", material.casefold()).strip("-")[:80] or "unknown"


def _strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()
