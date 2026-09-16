#!/usr/bin/env python3
"""Read-only pending investigation with bounded first-look coverage.

The evidence/classification/lifecycle implementation remains in the unchanged
core module. This runner adjusts only page selection and adds audit counters.
"""
from __future__ import annotations

if __package__:
    from . import _pending_opportunity_investigation_core as _core
else:
    import _pending_opportunity_investigation_core as _core

# Preserve the established public entrypoints, constants and CLI behavior.
for _export in dir(_core):
    if not _export.startswith("_"):
        globals()[_export] = getattr(_core, _export)

_original_investigate = _core.investigate_pending_opportunities
SCHEMA_VERSION = "pending-opportunity-investigation-1.6"


def _ranked_unique_candidates(report, state_records):
    """Apply existing priority/age/score rules, but fetch each URL only once."""
    ranked = []
    for item in _core._rows(report.get("deduplicated_opportunities")):
        if not _core._is_pending(item):
            continue
        url = _core._investigation_url(item)
        if not url:
            continue
        history = state_records.get(_core._state_key(item)) or {}
        attempts = _core._attempt_count(state_records, item)
        if _core._exact_item_page_blockers(item):
            priority = 0
        elif _core._durable_exact_lot(history) and _core._enrichment_blockers(item):
            priority = 1
        else:
            priority = 2
        try:
            score = float(item.get("discovery_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        key = (
            priority,
            0 if attempts == 0 else 1,
            _core._text(history.get("last_investigated_at")),
            -score,
            _core._text(item.get("opportunity_identity")),
        )
        ranked.append((key, url, item, priority, attempts))
    ranked.sort(key=lambda entry: entry[0])
    seen_urls = set()
    unique = []
    for _, url, item, priority, attempts in ranked:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        unique.append((url, item, priority, attempts))
    return unique


def _first_look_target(limit, unseen_count):
    # Focused 1-4 record investigations keep the previous strict priority order.
    return min(unseen_count, max(1, limit // 5)) if limit >= 5 else 0


def select_pending_opportunities(report, limit=10, investigation_state=None):
    if not 1 <= limit <= _core.MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {_core.MAX_LIMIT}")
    candidates = _ranked_unique_candidates(report, _core._state_records(investigation_state))
    target = _first_look_target(limit, sum(attempts == 0 for _, _, _, attempts in candidates))
    selected = []
    selected_urls = set()

    def append(candidate):
        url = candidate[0]
        if len(selected) < limit and url not in selected_urls:
            selected.append(candidate)
            selected_urls.add(url)

    # Exact-item-page verification is urgent, and consumes the budget first.
    for candidate in candidates:
        if candidate[2] == 0:
            append(candidate)

    first_looks = sum(candidate[3] == 0 for candidate in selected)
    for candidate in candidates:
        if first_looks >= target or len(selected) >= limit:
            break
        if candidate[3] == 0 and candidate[0] not in selected_urls:
            append(candidate)
            first_looks += 1

    # Fill all remaining slots under the existing priority/oldest/score order.
    for candidate in candidates:
        append(candidate)
    return [candidate[1] for candidate in selected]


def investigate_pending_opportunities(
    report, *, limit=10, page_fetcher=None, investigation_state=None,
):
    # Preserve default public-page fetcher and the unchanged evidence gates.
    fetcher = _core.fetch_public_page if page_fetcher is None else page_fetcher
    state_records = _core._state_records(investigation_state)
    candidates = _ranked_unique_candidates(report, state_records)
    unseen_unique = sum(attempts == 0 for _, _, _, attempts in candidates)
    counts = {str(priority): sum(row[2] == priority for row in candidates)
              for priority in (0, 1, 2)}
    target = _first_look_target(limit, unseen_unique) if 1 <= limit <= _core.MAX_LIMIT else 0
    result = _original_investigate(
        report, limit=limit, page_fetcher=fetcher, investigation_state=investigation_state,
    )
    first_looks = int(result["newly_investigated_count"])
    deferred = None
    if target > first_looks:
        deferred = "URGENT_PRIORITY_ZERO_CONSUMED_PAGE_BUDGET"
    elif limit < 5 and unseen_unique and first_looks == 0:
        deferred = "FOCUSED_LIMIT_BELOW_FIRST_LOOK_QUOTA"
    result.update({
        "schema_version": SCHEMA_VERSION,
        "reserved_first_look_target": target,
        "selected_first_look_count": first_looks,
        "first_look_deferred_reason": deferred,
        "priority_candidate_counts": counts,
        "unique_selectable_page_count": len(candidates),
    })
    return result


# The unchanged core main() dynamically resolves these two functions. Route it
# through this runner while keeping state, evidence and no-purchase gates intact.
_core.select_pending_opportunities = select_pending_opportunities
_core.investigate_pending_opportunities = investigate_pending_opportunities


def main():
    return _core.main()


if __name__ == "__main__":
    raise SystemExit(main())
