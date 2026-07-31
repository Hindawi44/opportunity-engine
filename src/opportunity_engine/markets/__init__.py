"""Market-specific configuration boundaries."""

from opportunity_engine.markets.norway import (
    DEFAULT_PROFILE_PATH,
    build_norway_market_profile_snapshot,
    load_norway_market_profile,
)
from opportunity_engine.markets.profile import (
    SCHEMA_VERSION,
    MarketProfileError,
    MarketProfileV1,
    build_market_profile_snapshot,
    load_json_object,
)

__all__ = [
    "DEFAULT_PROFILE_PATH",
    "SCHEMA_VERSION",
    "MarketProfileError",
    "MarketProfileV1",
    "build_market_profile_snapshot",
    "build_norway_market_profile_snapshot",
    "load_json_object",
    "load_norway_market_profile",
]
