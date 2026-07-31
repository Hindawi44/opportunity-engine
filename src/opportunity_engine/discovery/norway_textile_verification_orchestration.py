"""Apply Norway textile page-verification policy to discovery payloads."""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping
from urllib.parse import urlparse

from opportunity_engine.discovery.clothing_inventory_search import PageVerification
from opportunity_engine.discovery.norway_textile_keywords import (
    build_norway_textile_keyword_queries,
)
from opportunity_engine.discovery.norway_textile_page_verification import (
    evaluate_norway_textile_page_verification,
)

_AUKSJONEN_CLOTHING_CATEGORY_PROVIDER = "Auksjonen Current Category"
_AUKSJONEN_CLOTHING_CATEGORY = "CLOTHING_INVENTORY"
_AUKSJONEN_HOSTS = frozenset({"auksjonen.no", "ny.auksjonen.no"})
_AUKSJONEN_TRAILING_ITEM_ID = re.compile(r"/(\d+)/?$")


def _query_category_map() -> dict[str, str]:
    return {
        query.query_id: query.category
        for query in build_norway_textile_keyword_queries()
    }


def _candidate_category(
    candidate: Mapping[str, Any],
    categories_by_query: Mapping[str, str],
) -> tuple[str | None, str | None]:
    providers = candidate.get("source_providers")
    if (
        isinstance(providers, list)
        and _AUKSJONEN_CLOTHING_CATEGORY_PROVIDER in providers
    ):
        return _AUKSJONEN_CLOTHING_CATEGORY, None

    query_ids = candidate.get("found_by_queries")
    if not isinstance(query_ids, list):
        return None, "candidate has no traceable query IDs"
    categories = {
        categories_by_query[query_id]
        for query_id in query_ids
        if isinstance(query_id, str) and query_id in categories_by_query
    }
    if not categories:
        return None, "candidate has no supported textile category"
    if len(categories) > 1:
        return None, "candidate maps to multiple textile categories"
    return next(iter(categories)), None


def _auksjonen_trailing_identity(candidate: Mapping[str, Any]) -> str | None:
    providers = candidate.get("source_providers")
    if not (
        isinstance(providers, list)
        and _AUKSJONEN_CLOTHING_CATEGORY_PROVIDER in providers
    ):
        return None
    source_urls = candidate.get("source_urls")
    if not isinstance(source_urls, list):
        return None
    identities: set[str] = set()
    for url in source_urls:
        if not isinstance(url, str):
            continue
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in _AUKSJONEN_HOSTS:
            continue
        match = _AUKSJONEN_TRAILING_ITEM_ID.search(parsed.path)
        if match:
            identities.add(f"url-id:{match.group(1)}")
    if len(identities) != 1:
        return None
    return next(iter(identities))


def _apply_auksjonen_identity(candidate: dict[str, Any]) -> None:
    identity = _auksjonen_trailing_identity(candidate)
    if identity is None:
        return
    candidate["opportunity_identity"] = identity
    candidate["identity_stable"] = True
    verifications = candidate.get("verification")
    if not isinstance(verifications, list):
        return
    for verification in verifications:
        if not isinstance(verification, dict):
            continue
        url = verification.get("url")
        if not isinstance(url, str):
            continue
        parsed = urlparse(url)
        match = _AUKSJONEN_TRAILING_ITEM_ID.search(parsed.path)
        if parsed.hostname in _AUKSJONEN_HOSTS and match:
            verification["opportunity_identity"] = f"url-id:{match.group(1)}"
            verification["identity_stable"] = True


def _page_verification(payload: Mapping[str, Any]) -> PageVerification:
    allowed = PageVerification.__dataclass_fields__
    return PageVerification(**{
        key: value for key, value in payload.items() if key in allowed
    })


def apply_norway_textile_page_verification_policy(
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate verified pages and rebuild Top 5 from accepted candidates only."""
    output = deepcopy(dict(result))
    categories_by_query = _query_category_map()
    candidates = output.get("all_discovered_candidates")
    if not isinstance(candidates, list):
        return output

    accepted_candidates: list[dict[str, Any]] = []
    accepted_count = 0
    rejected_count = 0

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        _apply_auksjonen_identity(candidate)
        category, category_error = _candidate_category(candidate, categories_by_query)
        candidate["textile_category"] = category
        decisions: list[dict[str, Any]] = []

        verifications = candidate.get("verification")
        if category_error:
            decisions.append({
                "accepted": False,
                "reason": category_error,
                "category": category,
            })
        elif isinstance(verifications, list) and verifications:
            for verification_payload in verifications:
                if not isinstance(verification_payload, Mapping):
                    continue
                decision = evaluate_norway_textile_page_verification(
                    _page_verification(verification_payload),
                    category=category,
                )
                decisions.append({
                    "accepted": decision.accepted,
                    "reason": decision.reason,
                    "category": decision.category,
                })
        else:
            decisions.append({
                "accepted": False,
                "reason": "candidate has no completed public-page verification",
                "category": category,
            })

        accepted = any(decision["accepted"] for decision in decisions)
        candidate["textile_page_verification"] = decisions
        candidate["textile_page_verification_accepted"] = accepted
        if accepted:
            accepted_count += 1
            if candidate.get("top5_eligible") is True:
                accepted_candidates.append(candidate)
        else:
            rejected_count += 1
            candidate["top5_eligible"] = False
            candidate["post_verification_top5_block_reason"] = (
                "norway_textile_page_verification_failed"
            )

    accepted_candidates.sort(
        key=lambda item: (
            item.get("discovery_score", 0),
            len(item.get("source_urls") or []),
        ),
        reverse=True,
    )
    output["top5_opportunities"] = accepted_candidates[:5]

    report = output.get("search_run_report")
    if isinstance(report, dict):
        report["norway_textile_page_verification_policy_applied"] = True
        report["norway_textile_page_verification_accepted"] = accepted_count
        report["norway_textile_page_verification_rejected"] = rejected_count
        report["top5_count"] = len(output["top5_opportunities"])
        report["top5_eligible_count"] = len(accepted_candidates)
        report["no_opportunities_found"] = not output["top5_opportunities"]

    return output
