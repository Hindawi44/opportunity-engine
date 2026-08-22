from __future__ import annotations

import json


def test_core_query_scope_excludes_signal_only_market_radar_queries(tmp_path) -> None:
    from opportunity_engine.daily_learning_runtime import (
        load_active_learning_queries,
        load_core_opportunity_queries,
    )

    config = tmp_path / "queries.json"
    config.write_text(
        json.dumps(
            {
                "queries": [
                    "opphørssalg arbeidsklær sikkerhetssko Norge",
                    "konkurssalg varelager tekstil Norge",
                ]
            }
        ),
        encoding="utf-8",
    )

    core_queries = load_core_opportunity_queries(config)
    all_learning_queries = load_active_learning_queries(config)

    assert core_queries == [
        "opphørssalg arbeidsklær sikkerhetssko Norge",
        "konkurssalg varelager tekstil Norge",
    ]
    assert any("avviklingssalg" in query.casefold() for query in all_learning_queries)
    assert not any("avviklingssalg" in query.casefold() for query in core_queries)


def test_bauhaus_verified_terms_leave_true_core_query_gap() -> None:
    from opportunity_engine.automatic_query_gap_miss_scout import _query_contains_term

    core_queries = [
        "opphørssalg arbeidsklær sikkerhetssko Norge",
        "konkurssalg varelager tekstil Norge",
    ]

    assert _query_contains_term(core_queries, "opphørssalg") is True
    assert _query_contains_term(core_queries, "avviklingssalg") is False
