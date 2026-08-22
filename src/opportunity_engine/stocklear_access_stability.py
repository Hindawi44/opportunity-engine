"""Read-only stability assessment for Stocklear's public opportunity pages.

The goal is not to bypass protection. It measures whether the public surface that
Opportunity Engine already proved useful remains reliably accessible without
login, cookies, CAPTCHA solving, proxy rotation, or production activation.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

SCHEMA_VERSION = "stocklear-access-stability-1.0"

_CHALLENGE_MARKERS = (
    "verify you are human",
    "checking your browser",
    "cf-chl-captcha",
    "captcha",
    "cloudflare ray id",
    "access denied",
)
_LOGIN_MARKERS = (
    "log in or register",
    "create my account",
    "log in and start bidding",
    "log in to your stocklear account",
)
_PUBLIC_LOT_MARKERS = (
    "number of pallets",
    "starting price",
    "last bid",
    "quality",
    "end of the auction",
    "ending date",
    " units",
    "lot of ",
    "batch of ",
    "set of ",
)


def _compact(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _host(value: object) -> str:
    try:
        return (urlsplit(str(value or "")).hostname or "").casefold().rstrip(".")
    except ValueError:
        return ""


def _path(value: object) -> str:
    try:
        return (urlsplit(str(value or "")).path or "/").casefold()
    except ValueError:
        return "/"


def classify_access_sample(
    *,
    url: str,
    status_code: int,
    final_url: str,
    body: str,
) -> dict[str, Any]:
    """Classify one public HTTP observation without attempting any bypass."""
    text = _compact(body)
    challenge = any(marker in text for marker in _CHALLENGE_MARKERS)
    login_wall = any(marker in text for marker in _LOGIN_MARKERS)
    login_redirect = (
        _host(url) == _host(final_url) == "joblot.stocklear.eu"
        and _path(final_url).rstrip("/") in {"/login", "/register"}
        and _path(url).rstrip("/") not in {"/login", "/register"}
    )
    public_markers = sum(1 for marker in _PUBLIC_LOT_MARKERS if marker in text) >= 2
    blocked = status_code == 403
    rate_limited = status_code == 429
    html_drift = False

    if blocked:
        access_status = "BLOCKED_403"
    elif rate_limited:
        access_status = "RATE_LIMITED_429"
    elif challenge:
        access_status = "CHALLENGE_PAGE"
    elif login_redirect:
        access_status = "LOGIN_REDIRECT"
    elif status_code >= 400:
        access_status = f"HTTP_{status_code}"
    elif public_markers and login_wall:
        access_status = "PUBLIC_PARTIAL_LOGIN_WALL"
    elif public_markers:
        access_status = "PUBLIC_ACCESS"
    elif status_code == 200:
        access_status = "HTML_DRIFT_OR_EMPTY_PUBLIC_DATA"
        html_drift = True
    else:
        access_status = "UNUSABLE"

    usable_public = access_status in {"PUBLIC_ACCESS", "PUBLIC_PARTIAL_LOGIN_WALL"}
    return {
        "schema_version": SCHEMA_VERSION,
        "url": url,
        "status_code": int(status_code),
        "final_url": final_url,
        "access_status": access_status,
        "usable_public": usable_public,
        "public_opportunity_markers": public_markers,
        "login_wall_present": login_wall,
        "login_redirect": login_redirect,
        "blocked": blocked,
        "rate_limited": rate_limited,
        "challenge_detected": challenge,
        "html_drift_suspected": html_drift,
    }


def summarize_access_stability(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate bounded observations into a conservative stability verdict."""
    rows = [dict(sample) for sample in samples if isinstance(sample, Mapping)]
    counts = Counter(str(row.get("access_status") or "UNKNOWN") for row in rows)
    usable = sum(1 for row in rows if row.get("usable_public") is True)
    blocked = sum(1 for row in rows if row.get("blocked") is True)
    rate_limited = sum(1 for row in rows if row.get("rate_limited") is True)
    challenges = sum(1 for row in rows if row.get("challenge_detected") is True)
    login_redirects = sum(1 for row in rows if row.get("login_redirect") is True)
    drift = sum(1 for row in rows if row.get("html_drift_suspected") is True)
    sample_count = len(rows)
    ratio = round(usable / sample_count, 6) if sample_count else 0.0

    stable = (
        sample_count >= 3
        and ratio >= 0.8
        and blocked == 0
        and rate_limited == 0
        and challenges == 0
        and login_redirects == 0
        and drift == 0
    )
    verdict = "PUBLIC_ACCESS_STABLE_PARTIAL" if stable else "ACCESS_UNSTABLE_OR_PROTECTED"

    return {
        "schema_version": SCHEMA_VERSION,
        "sample_count": sample_count,
        "usable_public_sample_count": usable,
        "usable_public_ratio": ratio,
        "blocked_count": blocked,
        "rate_limited_count": rate_limited,
        "challenge_count": challenges,
        "login_redirect_count": login_redirects,
        "html_drift_count": drift,
        "access_status_counts": dict(sorted(counts.items())),
        "samples": rows,
        "verdict": verdict,
        "production_promotion_recommended": False,
        "production_mutation": False,
        "automatic_promotion": False,
        "authentication_attempted": False,
        "captcha_bypass_attempted": False,
        "proxy_rotation_attempted": False,
    }
