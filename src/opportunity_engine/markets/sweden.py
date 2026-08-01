"""Sweden Market Profile V1 loader and snapshot builder."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from opportunity_engine.markets.profile import (
    MarketProfileV1,
    build_market_profile_snapshot,
    load_json_object,
)


DEFAULT_SWEDEN_PROFILE_PATH = Path("config/markets/se_v1.json")


def load_sweden_market_profile(
    root: Path,
    *,
    profile_path: Path = DEFAULT_SWEDEN_PROFILE_PATH,
) -> MarketProfileV1:
    """Load the checked-in Sweden profile without performing calculations."""
    profile = MarketProfileV1.from_path(root / profile_path)
    if profile.market_code != "SE" or profile.market_name != "Sweden":
        raise ValueError("Sweden profile must identify market SE / Sweden")
    return profile


def build_sweden_market_profile_snapshot(
    root: Path,
    *,
    profile_path: Path = DEFAULT_SWEDEN_PROFILE_PATH,
) -> dict[str, Any]:
    """Resolve Sweden configuration against the official source registries."""
    profile = load_sweden_market_profile(root, profile_path=profile_path)
    plan_path = root / str(profile.source_registry["plan_path"])
    runtime_path = root / str(profile.source_registry["runtime_status_path"])
    return build_market_profile_snapshot(
        profile,
        load_json_object(plan_path),
        load_json_object(runtime_path),
    )
