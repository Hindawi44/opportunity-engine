"""Operator-owned source exclusion for future discovery and human review.

Excluding a domain is a workflow preference, NOT evidence of fraud, closed listings,
missing stock, or commercial quality. Existing persisted records are never deleted.
"""
from __future__ import annotations

from urllib.parse import urlsplit

# Explicit human decisions. Keep historic records and explanations outside this filter.
OPERATOR_EXCLUDED_DOMAINS = frozenset({
    "friptadium.com",  # 2026-09-18: user explicitly excluded the whole site.
    "luxvintagewholesale.com",  # 2026-09-19: user explicitly excluded the whole site.
    "vinqa-grossiste.com",  # 2026-09-17: user explicitly excluded the whole site.
})


def excluded_domain(url: object) -> str | None:
    """Return excluded source hostname, matching exact hosts or their subdomains."""
    if not isinstance(url, str):
        return None
    try:
        parsed = urlsplit(url.strip())
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
            return None
        host = parsed.hostname.casefold().rstrip(".")
    except ValueError:
        return None
    for domain in sorted(OPERATOR_EXCLUDED_DOMAINS):
        if host == domain or host.endswith("." + domain):
            return domain
    return None


def is_operator_excluded_url(url: object) -> bool:
    return excluded_domain(url) is not None
