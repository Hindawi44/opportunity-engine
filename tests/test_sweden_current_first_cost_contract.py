from datetime import datetime
from zoneinfo import ZoneInfo

from opportunity_engine.discovery.sweden_current_first import (
    build_blinto_current_first_queries,
    build_klaravik_current_first_queries,
)


def test_current_first_does_not_expand_source_query_budget():
    now = datetime(2026, 8, 17, tzinfo=ZoneInfo("Europe/Stockholm"))
    assert len(build_blinto_current_first_queries(8, now=now)) == 8
    assert len(build_klaravik_current_first_queries(8, now=now)) == 8
