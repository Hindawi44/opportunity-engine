"""Buyer-profile configuration contracts."""

from opportunity_engine.buyers.profile import (
    SCHEMA_VERSION,
    BuyerProfileError,
    BuyerProfileV1,
    build_buyer_profile_snapshot,
)

__all__ = [
    "SCHEMA_VERSION",
    "BuyerProfileError",
    "BuyerProfileV1",
    "build_buyer_profile_snapshot",
]
