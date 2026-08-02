"""Completion reconciliation for bounded public Riegermann pagination.

The query-aware crawler can legitimately fetch the friendly bootstrap page and
then encounter an explicit ``pagenumber=1`` link containing the same objects.
That duplicate first page is evidence about the page range, not a catalog
failure.  This layer reconciles the diagnostics only when completeness is
proved by the public result count or by a contiguous page-number sequence.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

from opportunity_engine.discovery import germany_riegermann_live as live_layer
from opportunity_engine.discovery import (
    germany_riegermann_query_pagination as query_compat,
)

_DUPLICATE_PAGE_ERROR = "pagination page produced no new item URLs"
_ORIGINAL_QUERY_RUN = query_compat.run_riegermann_live_discovery_query_compat


def _page_number(url: str) -> int | None:
    values = parse_qs(urlparse(url).query).get("pagenumber") or []
    if not values:
        return None
    try:
        page_number = int(values[-1])
    except (TypeError, ValueError):
        return None
    return page_number if page_number > 0 else None


def _is_benign_bootstrap_duplicate(error: dict[str, Any]) -> bool:
    return bool(
        error.get("error") == _DUPLICATE_PAGE_ERROR
        and _page_number(str(error.get("url") or "")) == 1
    )


def _catalog_parent(live: live_layer.RiegermannLiveResult) -> dict[str, Any] | None:
    return next(
        (
            candidate
            for candidate in live.discovery_result["all_discovered_candidates"]
            if candidate.get("page_role") == "AUCTION_EVENT"
        ),
        None,
    )


def reconcile_riegermann_catalog_completion(
    live: live_layer.RiegermannLiveResult,
) -> live_layer.RiegermannLiveResult:
    """Promote coverage to complete only when public evidence proves it."""
    diagnostics = live.discovery_result["search_run_report"]["riegermann_live"]
    page_urls = [str(url) for url in diagnostics.get("catalog_page_urls") or []]
    page_numbers = {
        page_number
        for url in page_urls
        if (page_number := _page_number(url)) is not None
    }
    expected_page_count = diagnostics.get("catalog_expected_page_count")
    if expected_page_count is None and page_numbers:
        expected_page_count = max(page_numbers)
        diagnostics["catalog_expected_page_count"] = expected_page_count

    errors = list(diagnostics.get("catalog_page_errors") or [])
    blocking_errors = [
        error for error in errors if not _is_benign_bootstrap_duplicate(error)
    ]
    benign_duplicate_count = len(errors) - len(blocking_errors)

    total_results = diagnostics.get("catalog_total_results")
    observed = diagnostics.get("child_lots_observed")
    result_count_proves_completion = bool(
        isinstance(total_results, int)
        and total_results > 0
        and isinstance(observed, int)
        and observed >= total_results
    )
    contiguous_pages_prove_completion = bool(
        isinstance(expected_page_count, int)
        and expected_page_count > 0
        and set(range(1, expected_page_count + 1)).issubset(page_numbers)
    )
    limit_reached = diagnostics.get("catalog_page_limit_reached") is True
    completion_proved = bool(
        not limit_reached
        and not blocking_errors
        and (
            result_count_proves_completion
            or contiguous_pages_prove_completion
        )
    )

    diagnostics.update(
        {
            "catalog_result_count_proves_completion": (
                result_count_proves_completion
            ),
            "catalog_contiguous_pages_prove_completion": (
                contiguous_pages_prove_completion
            ),
            "catalog_duplicate_bootstrap_page_count": benign_duplicate_count,
            "catalog_unique_numbered_page_count": len(page_numbers),
        }
    )
    if not completion_proved:
        return live

    diagnostics["catalog_page_errors"] = blocking_errors
    diagnostics["catalog_coverage_complete"] = True
    diagnostics["catalog_coverage_reason"] = "complete"
    live.diagnostics.update(diagnostics)

    parent = _catalog_parent(live)
    if parent is None:
        return live

    parent.update(
        {
            "catalog_coverage_complete": True,
            "catalog_coverage_reason": "complete",
            "catalog_expected_page_count": expected_page_count,
            "catalog_result_count_proves_completion": (
                result_count_proves_completion
            ),
            "catalog_contiguous_pages_prove_completion": (
                contiguous_pages_prove_completion
            ),
            "catalog_duplicate_bootstrap_page_count": benign_duplicate_count,
        }
    )
    parent["missing_information"] = [
        item
        for item in parent.get("missing_information") or []
        if item != "complete public catalog coverage"
    ]
    if parent.get("post_verification_top5_block_reason") == (
        "catalog_pagination_incomplete"
    ):
        parent.pop("post_verification_top5_block_reason", None)

    if not parent.get("promoted_bulk_lot_count"):
        parent["next_verification_step"] = (
            "Catalog coverage is complete; no explicit bulk child lot requires "
            "item-page verification."
        )
        parent["next_action"] = (
            "Retain the auction as parent evidence and do not promote ordinary "
            "single garments."
        )
    return live


def run_riegermann_live_discovery_completion_compat(
    catalog_url: str,
    *,
    information_url: str | None = None,
    session: Any | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = live_layer.DEFAULT_MAX_RESPONSE_BYTES,
    item_verification_limit: int = 10,
    catalog_page_limit: int = 100,
) -> live_layer.RiegermannLiveResult:
    """Run query-aware pagination and reconcile only proven completion."""
    live = _ORIGINAL_QUERY_RUN(
        catalog_url,
        information_url=information_url,
        session=session,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
        item_verification_limit=item_verification_limit,
        catalog_page_limit=catalog_page_limit,
    )
    return reconcile_riegermann_catalog_completion(live)


def install_riegermann_catalog_completion_compatibility() -> None:
    """Install query-aware pagination with proven completion reconciliation."""
    query_compat.install_riegermann_query_catalog_compatibility()
    live_layer.run_riegermann_live_discovery = (
        run_riegermann_live_discovery_completion_compat
    )
