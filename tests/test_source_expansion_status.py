from scripts.build_source_expansion_status import build_status


def test_phase_stays_locked_until_all_sources_collect():
    plan = {
        "phase": "source_expansion_before_economic_ranking",
        "completion_rule": "all collect",
        "markets": [
            {
                "market": "Norway",
                "sources": [
                    {"source": "Auksjonen.no", "priority": 1, "current_status": "collecting"},
                    {"source": "FINN.no", "priority": 2, "current_status": "awaiting_authorized_configuration"},
                ],
            }
        ],
    }
    funnel = {
        "sources": [
            {"source": "Auksjonen.no", "status": "collecting", "fetched": 10, "error": None},
            {"source": "FINN.no", "status": "awaiting_authorized_configuration", "fetched": 0, "error": None},
        ]
    }

    result = build_status(plan, funnel)

    assert result["phase_complete"] is False
    assert result["economic_ranking_unlocked"] is False
    assert result["summary"] == {
        "required_source_count": 2,
        "complete_source_count": 1,
        "blocked_source_count": 1,
        "planned_source_count": 0,
        "remaining_source_count": 1,
    }


def test_phase_unlocks_only_when_every_source_has_verified_collection():
    plan = {
        "phase": "source_expansion_before_economic_ranking",
        "completion_rule": "all collect",
        "markets": [
            {
                "market": "Norway",
                "sources": [
                    {"source": "Auksjonen.no", "priority": 1, "current_status": "collecting"},
                    {"source": "FINN.no", "priority": 2, "current_status": "collecting"},
                ],
            }
        ],
    }
    funnel = {
        "sources": [
            {"source": "Auksjonen.no", "status": "collecting", "fetched": 10, "error": None},
            {"source": "FINN.no", "status": "collecting", "fetched": 3, "error": None},
        ]
    }

    result = build_status(plan, funnel)

    assert result["phase_complete"] is True
    assert result["economic_ranking_unlocked"] is True
    assert result["summary"]["remaining_source_count"] == 0
