"""Shared boundaries for Norwegian bankruptcy search hints and sale evidence."""
from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlsplit


NON_SALE_HOSTS = frozenset({
    "brreg.no", "proff.no", "purehelp.no", "gulesider.no", "firmalisten.no",
    "mynk.no", "konkurs.app",
})
GENERIC_INDEX_PATHS = frozenset({
    "/", "/butikk/", "/auksjoner/torget/vareparti-og-konkursbo",
    "/auksjoner/torget/vareparti-og-konkursbo/",
})


def sale_url_rejection(url: str) -> str | None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if any(host == domain or host.endswith("." + domain) for domain in NON_SALE_HOSTS):
        return "COMPANY_DIRECTORY_NOT_SALE_PAGE"
    if parsed.path.casefold() in GENERIC_INDEX_PATHS:
        return "GENERIC_INDEX_NOT_EXACT_SALE_PAGE"
    return None


def validate_follow_up_context(
    value: object, *, organisation_number: str, company_name: str,
) -> dict[str, Any] | None:
    """Validate bounded search hints; they never supply sale-page identity."""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("Bankruptcy follow-up context must be an object")
    estate = str(value.get("estate_organisation_number") or "")
    trustee = " ".join(str(value.get("trustee_name") or "").split())
    source_url = str(value.get("source_url") or "")
    if (
        value.get("organisation_number") != organisation_number
        or value.get("company_name") != company_name
        or value.get("search_hints_only") is not True
        or len(estate) != 9
        or not estate.isascii()
        or not estate.isdigit()
        or estate == organisation_number
        or source_url != "https://konkurs.app/konkursbo/" + estate
        or not trustee
        or len(trustee) > 150
    ):
        raise ValueError("Invalid bankruptcy follow-up context")
    return {
        "organisation_number": organisation_number,
        "company_name": company_name,
        "estate_organisation_number": estate,
        "trustee_name": trustee,
        "source_url": source_url,
        "search_hints_only": True,
    }
