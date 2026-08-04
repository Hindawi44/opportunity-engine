"""Bounded public Blinto seller-identity extraction for Swedish market artifacts.

The extractor reuses exact Blinto auction URLs already discovered by the engine,
reads only public pages, removes forms and generic financing inputs, and preserves
only explicit seller/company identity evidence. Search titles never become company
names, generic seller classifications never become identities, and no contact,
bid, reservation, purchase, or payment is performed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping, MutableMapping, Sequence

import requests

from opportunity_engine.discovery.direct_official_source_adapters import (
    _compact,
    _iso_utc,
    _safety_payload,
    _target_spec,
)
from opportunity_engine.discovery.sweden_blinto import (
    BLINTO_HOST,
    canonicalize_blinto_auction_url,
)


SCHEMA_VERSION = "blinto-seller-identity-extraction-1.0"
OUTPUT_FILENAME = "blinto-seller-identity-evidence.json"
DEFAULT_PAGE_LIMIT = 20
DEFAULT_FILE_LIMIT = 100
DEFAULT_FILE_BYTES = 5_000_000
DEFAULT_RESPONSE_BYTES = 1_500_000
DEFAULT_TIMEOUT_SECONDS = 15.0

_BLINTO_URL_RE = re.compile(
    r"https://(?:www\.)?blinto\.se/auction/[A-Za-z0-9][A-Za-z0-9_-]*/?",
    re.I,
)
_EXCLUDED_HTML_BLOCK_RE = re.compile(
    r"<(?:script|style|noscript|svg|form)\b[^>]*>.*?</(?:script|style|noscript|svg|form)>",
    re.I | re.S,
)
_BLOCK_TAG_RE = re.compile(
    r"</?(?:article|aside|blockquote|br|dd|div|dl|dt|fieldset|figcaption|figure|"
    r"footer|h[1-6]|header|li|main|nav|ol|p|section|table|tbody|td|th|thead|tr|ul)"
    r"\b[^>]*>",
    re.I,
)
_TAG_RE = re.compile(r"<[^>]+>")
_SAME_LINE_COMPANY_RE = re.compile(
    r"(?i)^(?:säljare|saljare|företag|foretag|företagsnamn|foretagsnamn|"
    r"uppdragsgivare|organisationsnamn|bolagsnamn)\s*[:#-]\s*(?P<name>.+)$"
)
_NATURAL_COMPANY_RE = re.compile(
    r"(?i)^(?:objektet\s+)?säljs\s+på\s+uppdrag\s+av\s+(?P<name>.+)$"
)
_BANKRUPTCY_COMPANY_RE = re.compile(
    r"(?i)^konkursboet\s+efter\s+(?P<name>.+)$"
)
_ORG_NUMBER_RE = re.compile(
    r"(?i)(?:organisationsnummer|org\.?\s*nr|orgnr)\s*[:#-]?\s*"
    r"(?P<number>(?:16)?\d{6}[- ]?\d{4})"
)
_EXACT_ORG_NUMBER_RE = re.compile(r"^(?:16)?(?P<a>\d{6})[- ]?(?P<b>\d{4})$")
_EXACT_COMPANY_LABELS = {
    "säljare",
    "saljare",
    "företag",
    "foretag",
    "företagsnamn",
    "foretagsnamn",
    "uppdragsgivare",
    "organisationsnamn",
    "bolagsnamn",
}
_GENERIC_COMPANY_VALUES = {
    "blinto",
    "blinto ab",
    "blinto kundtjänst",
    "blinto kundtjanst",
    "privatperson",
    "privatperson eller annan ej momspliktig säljare",
    "privatperson eller annan ej momspliktig saljare",
    "annan ej momspliktig säljare",
    "annan ej momspliktig saljare",
    "momspliktig organisation",
    "annan momspliktig organisation",
    "säljare",
    "saljare",
    "seller",
    "ägaren",
    "agaren",
    "uppdragsgivaren",
    "kunden",
    "okänd",
    "okand",
    "unknown",
}
_TRAILING_UI_RE = re.compile(
    r"(?i)\s+(?:har du också|har du ocksa|kontakta kundtjänst|"
    r"kontakta kundtjanst|finansiering|karta över|karta over|"
    r"auktionen|högsta bud|hogsta bud|vinnande bud|objekt-id)\b.*$"
)
_SELLER_CLASSIFICATIONS = (
    (
        "PRIVATE_OR_NON_VAT_SELLER",
        (
            "privatperson eller annan ej momspliktig säljare",
            "privatperson eller annan ej momspliktig saljare",
            "annan ej momspliktig säljare",
            "annan ej momspliktig saljare",
        ),
    ),
    (
        "VAT_LIABLE_ORGANISATION",
        (
            "momspliktig organisation",
            "momspliktig säljare",
            "momspliktig saljare",
        ),
    ),
    (
        "BANKRUPTCY_ESTATE",
        (
            "konkursbo",
            "konkursboet",
        ),
    ),
)

HtmlGetter = Callable[[str, float], tuple[str, str]]


@dataclass(frozen=True, slots=True)
class BlintoSellerIdentityEvidence:
    """One bounded identity result from a single public Blinto auction page."""

    source_url: str
    company_name: str | None
    organisationsnummer: str | None
    seller_type: str | None
    evidence_lines: tuple[str, ...]
    verified_public_page: bool = True

    @property
    def has_identity(self) -> bool:
        return bool(self.company_name or self.organisationsnummer)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _default_html_get(url: str, timeout: float) -> tuple[str, str]:
    response = requests.get(
        url,
        timeout=timeout,
        allow_redirects=True,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": (
                "opportunity-engine/blinto-seller-identity-extraction "
                "(+https://github.com/Hindawi44/opportunity-engine)"
            ),
        },
    )
    response.raise_for_status()
    raw = bytes(response.content)
    if len(raw) > DEFAULT_RESPONSE_BYTES:
        raise RuntimeError("Blinto response exceeded the bounded response size")
    return response.url, raw.decode(response.encoding or "utf-8", errors="replace")


def _normalise_org_number(value: object) -> str | None:
    compact = re.sub(r"\s+", "", str(value or ""))
    match = _EXACT_ORG_NUMBER_RE.fullmatch(compact)
    if not match:
        return None
    number = f"{match.group('a')}{match.group('b')}"
    digits = [int(character) for character in number]
    total = 0
    for index, digit in enumerate(digits[:-1]):
        weighted = digit * 2 if index % 2 == 0 else digit
        total += weighted // 10 + weighted % 10
    check_digit = (10 - total % 10) % 10
    return number if check_digit == digits[-1] else None


def _normalise_company_name(value: object) -> str | None:
    text = html.unescape(str(value or ""))
    text = " ".join(text.split())
    text = _TRAILING_UI_RE.sub("", text)
    text = re.split(
        r"(?i)\s+(?:organisationsnummer|org\.?\s*nr|orgnr)\b",
        text,
        maxsplit=1,
    )[0].strip(" \t\r\n:;,-–—")
    if not 2 <= len(text) <= 200:
        return None
    folded = text.casefold()
    if folded in _GENERIC_COMPANY_VALUES:
        return None
    if any(
        phrase in folded
        for phrase in (
            "privatperson eller annan",
            "momspliktig organisation",
            "ej momspliktig säljare",
            "ej momspliktig saljare",
            "kontakta kundtjänst",
            "kontakta kundtjanst",
            "det är ej möjligt att söka finansiering",
            "det ar ej mojligt att soka finansiering",
        )
    ):
        return None
    if "://" in text or "@" in text or not any(character.isalpha() for character in text):
        return None
    if folded.startswith(("www.", "blinto ", "objektet säljs", "objektet saljs")):
        return None
    return text


def _public_identity_lines(decoded: str) -> list[str]:
    fragment = _EXCLUDED_HTML_BLOCK_RE.sub("\n", decoded)
    fragment = _BLOCK_TAG_RE.sub("\n", fragment)
    fragment = _TAG_RE.sub(" ", fragment)
    lines: list[str] = []
    for raw_line in html.unescape(fragment).splitlines():
        line = " ".join(raw_line.split()).strip()
        if not line:
            continue
        lines.append(line[:500])
    return lines[:2000]


def _seller_type(lines: Sequence[str]) -> str | None:
    folded = " ".join(lines).casefold()
    for seller_type, phrases in _SELLER_CLASSIFICATIONS:
        if any(phrase in folded for phrase in phrases):
            return seller_type
    return None


def _company_candidates(lines: Sequence[str]) -> list[tuple[int, str, str]]:
    candidates: list[tuple[int, str, str]] = []
    for index, line in enumerate(lines):
        folded = line.casefold().strip(" :#-")
        if folded in _EXACT_COMPANY_LABELS and index + 1 < len(lines):
            candidate = _normalise_company_name(lines[index + 1])
            if candidate:
                candidates.append((index, candidate, f"{line}: {lines[index + 1]}"))

        for pattern in (
            _SAME_LINE_COMPANY_RE,
            _NATURAL_COMPANY_RE,
            _BANKRUPTCY_COMPANY_RE,
        ):
            match = pattern.match(line)
            if not match:
                continue
            candidate = _normalise_company_name(match.group("name"))
            if candidate:
                candidates.append((index, candidate, line))
            break

    deduplicated: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for candidate in candidates:
        marker = re.sub(r"\W+", "", candidate[1].casefold())
        if not marker or marker in seen:
            continue
        seen.add(marker)
        deduplicated.append(candidate)
    return deduplicated


def _organisation_candidates(
    lines: Sequence[str],
    *,
    anchor_indexes: Sequence[int],
) -> list[tuple[int, str, str]]:
    if not anchor_indexes:
        return []
    candidates: list[tuple[int, str, str]] = []
    for index, line in enumerate(lines):
        for match in _ORG_NUMBER_RE.finditer(line):
            number = _normalise_org_number(match.group("number"))
            if not number:
                continue
            if min(abs(index - anchor) for anchor in anchor_indexes) > 5:
                continue
            candidates.append((index, number, line))
    return candidates


def extract_blinto_seller_identity(
    decoded: str,
    *,
    source_url: str,
) -> BlintoSellerIdentityEvidence:
    """Extract only explicit seller identity from one public Blinto HTML page."""

    canonical = canonicalize_blinto_auction_url(source_url)
    if canonical is None:
        raise ValueError("source_url must be one exact public Blinto auction URL")

    lines = _public_identity_lines(decoded)
    companies = _company_candidates(lines)
    anchor_indexes = [item[0] for item in companies]
    for index, line in enumerate(lines):
        folded = line.casefold()
        if any(
            marker in folded
            for marker in (
                "säljare",
                "saljare",
                "uppdragsgivare",
                "på uppdrag av",
                "pa uppdrag av",
                "konkursbo",
            )
        ):
            anchor_indexes.append(index)
    organisations = _organisation_candidates(
        lines,
        anchor_indexes=anchor_indexes,
    )

    company_name = companies[0][1] if companies else None
    organisation_number = organisations[0][1] if organisations else None
    evidence_lines: list[str] = []
    for _, _, evidence in (*companies[:1], *organisations[:1]):
        if evidence not in evidence_lines:
            evidence_lines.append(evidence)
    seller_type = _seller_type(lines)
    if seller_type and not evidence_lines:
        classification_line = next(
            (
                line
                for line in lines
                if any(
                    phrase in line.casefold()
                    for kind, phrases in _SELLER_CLASSIFICATIONS
                    if kind == seller_type
                    for phrase in phrases
                )
            ),
            None,
        )
        if classification_line:
            evidence_lines.append(classification_line)

    return BlintoSellerIdentityEvidence(
        source_url=canonical.canonical_url,
        company_name=company_name,
        organisationsnummer=organisation_number,
        seller_type=seller_type,
        evidence_lines=tuple(evidence_lines[:3]),
    )


def _walk_blinto_urls(value: object, result: MutableMapping[str, None]) -> None:
    if isinstance(value, Mapping):
        for item in value.values():
            _walk_blinto_urls(item, result)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            _walk_blinto_urls(item, result)
        return
    if not isinstance(value, str):
        return
    for match in _BLINTO_URL_RE.finditer(value):
        identity = canonicalize_blinto_auction_url(match.group(0))
        if identity is not None:
            result.setdefault(identity.canonical_url, None)


def discover_blinto_artifact_urls(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    file_limit: int = DEFAULT_FILE_LIMIT,
    max_file_bytes: int = DEFAULT_FILE_BYTES,
) -> tuple[list[str], dict[str, Any]]:
    """Return bounded exact Blinto URLs already present in Swedish artifacts."""

    if file_limit < 1 or max_file_bytes < 1:
        raise ValueError("artifact scan bounds must be positive")

    target = _target_spec(manifest, "SE")
    artifact_dir: Path | None = None
    result: dict[str, None] = {}
    scanned = 0
    skipped_large = 0
    invalid = 0

    if target is not None:
        raw_dir = _compact(target.get("artifact_dir"))
        if raw_dir:
            artifact_dir = Path(root) / raw_dir
            if artifact_dir.exists():
                paths = [
                    path
                    for path in sorted(artifact_dir.rglob("*.json"))
                    if path.name != OUTPUT_FILENAME
                ][:file_limit]
                for path in paths:
                    try:
                        size = path.stat().st_size
                    except OSError:
                        invalid += 1
                        continue
                    if size > max_file_bytes:
                        skipped_large += 1
                        continue
                    try:
                        payload = json.loads(path.read_text(encoding="utf-8"))
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                        invalid += 1
                        continue
                    scanned += 1
                    _walk_blinto_urls(payload, result)

    return sorted(result), {
        "artifact_dir": artifact_dir.as_posix() if artifact_dir else None,
        "artifact_json_files_scanned": scanned,
        "artifact_json_files_skipped_large": skipped_large,
        "artifact_json_files_invalid": invalid,
        "candidate_page_url_count": len(result),
    }


def collect_blinto_seller_identity_evidence(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at: datetime | None = None,
    page_limit: int = DEFAULT_PAGE_LIMIT,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    html_get: HtmlGetter = _default_html_get,
) -> dict[str, Any]:
    """Collect bounded seller identity evidence from already-known Blinto pages."""

    if not 1 <= page_limit <= 25:
        raise ValueError("page_limit must be between 1 and 25")
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    urls, discovery = discover_blinto_artifact_urls(manifest, root=root)
    selected = urls[:page_limit]
    truncated = len(urls) > len(selected)
    evidence: list[dict[str, Any]] = []
    errors: list[str] = []
    pages_fetched = 0

    for canonical_url in selected:
        request_url = canonical_url.replace(
            f"https://{BLINTO_HOST}/",
            f"https://www.{BLINTO_HOST}/",
            1,
        )
        try:
            final_url, decoded = html_get(request_url, timeout)
            final_identity = canonicalize_blinto_auction_url(final_url)
            expected_identity = canonicalize_blinto_auction_url(canonical_url)
            if final_identity is None or expected_identity is None:
                raise RuntimeError("Blinto page redirected outside an exact auction URL")
            if final_identity.listing_key != expected_identity.listing_key:
                raise RuntimeError("Blinto page redirected to a different auction occurrence")
            pages_fetched += 1
            item = extract_blinto_seller_identity(
                decoded,
                source_url=final_identity.canonical_url,
            )
            if item.has_identity or item.seller_type:
                evidence.append(item.to_dict())
        except Exception as exc:
            errors.append(
                f"{canonical_url}: {type(exc).__name__}: {exc}"
            )

    identity_count = sum(
        bool(item.get("company_name") or item.get("organisationsnummer"))
        for item in evidence
    )
    complete = not truncated and not errors
    if not complete:
        status = "PARTIAL_RETRIEVAL" if pages_fetched else "BLOCKED_DIRECT_ACCESS"
    else:
        status = "SUCCESS" if identity_count else "VALID_ZERO"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc(now),
        "source_country": "SE",
        "source_key": "BLINTO_SELLER_IDENTITY_EXTRACTION",
        "source_name": "Blinto public auction seller identity",
        "access_mode": "BOUNDED_PUBLIC_PAGE",
        "status": status,
        "block_reason": None,
        "page_limit": page_limit,
        "page_limit_reached": truncated,
        "selected_page_url_count": len(selected),
        "pages_fetched": pages_fetched,
        "retrieval_complete": complete,
        "seller_evidence_count": len(evidence),
        "accepted_identity_count": identity_count,
        "explicit_company_name_count": sum(
            bool(item.get("company_name")) for item in evidence
        ),
        "organisation_number_count": sum(
            bool(item.get("organisationsnummer")) for item in evidence
        ),
        "seller_classification_count": sum(
            bool(item.get("seller_type")) for item in evidence
        ),
        "errors": errors,
        "seller_evidence": evidence,
        **discovery,
        **_safety_payload(),
    }


def write_blinto_seller_identity_evidence(
    manifest: Mapping[str, Any],
    *,
    root: str | Path = ".",
    observed_at: datetime | None = None,
    page_limit: int = DEFAULT_PAGE_LIMIT,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    html_get: HtmlGetter = _default_html_get,
) -> dict[str, Any]:
    """Collect and write the source artifact consumed by the Swedish identity bridge."""

    report = collect_blinto_seller_identity_evidence(
        manifest,
        root=root,
        observed_at=observed_at,
        page_limit=page_limit,
        timeout=timeout,
        html_get=html_get,
    )
    target = _target_spec(manifest, "SE")
    raw_dir = _compact(target.get("artifact_dir")) if target else ""
    if not raw_dir:
        report["status"] = "BLOCKED_CONFIGURATION"
        report["block_reason"] = "MISSING_SWEDEN_ARTIFACT_DIRECTORY"
        report["artifact_path"] = None
        return report

    output = Path(root) / raw_dir / OUTPUT_FILENAME
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        artifact_path = output.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        artifact_path = output.as_posix()
    report["artifact_path"] = artifact_path
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
