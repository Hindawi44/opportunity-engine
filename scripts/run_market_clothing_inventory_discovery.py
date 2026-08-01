#!/usr/bin/env python3
"""Run Clothing Inventory discovery for one explicitly selected market."""
from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


def select_market_runner(market: str) -> Callable[[], int]:
    """Return the existing market runner and fail closed for unsupported codes."""
    normalized = market.strip().upper()
    if normalized == "NO":
        from scripts.run_clothing_inventory_discovery_search import main

        return main
    if normalized == "SE":
        from scripts.run_sweden_clothing_inventory_discovery_search import main

        return main
    raise ValueError(f"unsupported market code: {market}")


def main() -> int:
    selector = argparse.ArgumentParser(add_help=False)
    selector.add_argument("--market", choices=("NO", "SE"), default="NO")
    selected, remaining = selector.parse_known_args()
    runner = select_market_runner(selected.market)
    sys.argv = [sys.argv[0], *remaining]
    return runner()


if __name__ == "__main__":
    raise SystemExit(main())
