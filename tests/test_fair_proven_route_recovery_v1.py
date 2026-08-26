from __future__ import annotations

from opportunity_engine.discovery import fair_proven_route_recovery_v1 as fair
from opportunity_engine.discovery import provider_unique_page_verification as verifier


def _row(host: str, index: int, *, market: str = "IT") -> dict[str, str]:
    return {
        "market_code": market,
        "query": "bounded recovery test",
        "title": f"Lot {index}",
        "url": f"https://{host}/products/lot-{index}",
        "domain": host,
        "provider": verifier.PROVEN_ROUTE_RECOVERY_PROVIDER,
        "proven_route_recovery": "true",
        "route_memory_is_qualification_evidence": "false",
        "fresh_page_verification_required": "true",
    }


def _urls(rows: list[dict[str, str]], host: str) -> set[str]:
    return {row["url"] for row in rows if host in row["url"]}


def test_fair_recovery_keeps_existing_budget_contract() -> None:
    assert verifier.MAX_PROVEN_ROUTE_RECOVERY_FETCHES == 12
    assert verifier.MAX_ALLOWED_PAGE_FETCHES == 30
    assert fair.SEARCH_REQUESTS_ADDED == 0
    assert fair.PAGE_FETCH_BUDGET_ADDED == 0


def test_under_capacity_preserves_upstream_order() -> None:
    rows = [
        _row("stockitaly24.com", 3),
        _row("stockoutlet.it", 1),
        _row("stockitaly24.com", 1),
    ]
    selected = fair.fair_select_recovery_candidates(rows, limit=12, seed=99)

    assert [row["url"] for row in selected] == [row["url"] for row in rows]
    assert all(row["fair_recovery_scheduler_version"] == fair.VERSION for row in selected)
    assert all(row["fair_recovery_candidate_pool_size"] == "3" for row in selected)


def test_oversubscribed_pool_is_host_fair_and_rotates_between_runs() -> None:
    rows = [
        *[_row("stockitaly24.com", index) for index in range(1, 13)],
        *[_row("stockoutlet.it", index) for index in range(1, 4)],
    ]

    first = fair.fair_select_recovery_candidates(rows, limit=12, seed=343)
    second = fair.fair_select_recovery_candidates(rows, limit=12, seed=344)

    assert len(first) == 12
    assert len(second) == 12
    assert len(_urls(first, "stockoutlet.it")) == 3
    assert len(_urls(second, "stockoutlet.it")) == 3
    assert len(_urls(first, "stockitaly24.com")) == 9
    assert len(_urls(second, "stockitaly24.com")) == 9
    assert _urls(first, "stockitaly24.com") != _urls(second, "stockitaly24.com")
    assert len(_urls(first, "stockitaly24.com") | _urls(second, "stockitaly24.com")) > 9
    assert all(row["fair_recovery_limit_unchanged"] == "true" for row in first)
    assert all(row["fair_recovery_global_page_fetch_cap_unchanged"] == "true" for row in first)


def test_wrapper_reads_larger_memory_pool_but_returns_only_existing_slots(monkeypatch) -> None:
    observed: dict[str, int] = {}
    rows = [
        *[_row("stockitaly24.com", index) for index in range(1, 13)],
        *[_row("stockoutlet.it", index) for index in range(1, 4)],
    ]

    def fake_upstream(**kwargs):
        observed["limit"] = kwargs["limit"]
        return rows[: kwargs["limit"]]

    monkeypatch.setattr(fair, "_UPSTREAM_ROUTE_LOADER", fake_upstream)
    monkeypatch.setenv(fair.ROTATION_SEED_ENV, "344")

    selected = fair._fair_route_loader(
        market="IT",
        current_hosts={"stockoutlet.it"},
        current_urls=set(),
        query="Italia abbigliamento stock lotto",
        limit=12,
    )

    assert observed["limit"] == 120
    assert len(selected) == 12
    assert {row["fair_recovery_candidate_pool_size"] for row in selected} == {"15"}
    assert {row["fair_recovery_rotation_seed"] for row in selected} == {"344"}


def test_duplicate_memory_urls_cannot_consume_multiple_recovery_slots() -> None:
    repeated = _row("stockitaly24.com", 1)
    rows = [repeated, dict(repeated), _row("stockoutlet.it", 1)]

    selected = fair.fair_select_recovery_candidates(rows, limit=12, seed=0)

    assert len(selected) == 2
    assert len({row["url"] for row in selected}) == 2
