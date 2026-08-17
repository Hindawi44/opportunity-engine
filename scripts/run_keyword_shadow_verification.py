#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from opportunity_engine.discovery.keyword_shadow_verification import (
    run_keyword_shadow_verification,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run frozen stage-2 verification for the three Italy SHADOW keywords."
    )
    parser.add_argument(
        "--output",
        default="artifacts/keyword-shadow-verification-v1/report.json",
    )
    parser.add_argument(
        "--freshness",
        default="none",
        choices=("", "none", "pm", "py"),
    )
    args = parser.parse_args()

    freshness = None if args.freshness in {"", "none"} else args.freshness
    report = run_keyword_shadow_verification(
        environment=os.environ,
        freshness=freshness,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": report.get("status"),
                "queries": report.get("stage1_query_count"),
                "page_fetches": report.get("page_fetches_attempted"),
                "page_fetches_succeeded": report.get("page_fetches_succeeded"),
                "promote": report.get("promote_count"),
                "shadow": report.get("shadow_count"),
                "reject": report.get("reject_count"),
                "output": output.as_posix(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report.get("status") not in {"BLOCKED_CONFIGURATION", "BLOCKED_RETRIEVAL"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
