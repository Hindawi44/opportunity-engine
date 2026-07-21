#!/usr/bin/env python3
"""Write a safe source-coverage report without exposing credentials."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _configured(*names: str) -> bool:
    return all(bool(os.getenv(name, "").strip()) for name in names)


def main() -> int:
    sources = [
        {
            "source": "Auksjonen.no",
            "access_mode": "public_direct_category_pages",
            "configured": True,
            "active": True,
            "coverage": [
                "vareparti-og-konkursbo",
                "overskuddsvarer",
                "interior-kontor-innredning",
                "varelager",
            ],
        },
        {
            "source": "FINN.no",
            "access_mode": "authorized_api_only",
            "configured": _configured("FINN_API_KEY", "FINN_ORG_ID"),
            "active": _configured("FINN_API_KEY", "FINN_ORG_ID"),
            "required_configuration": ["FINN_API_KEY", "FINN_ORG_ID"],
        },
        {
            "source": "Konkurskupp",
            "access_mode": "authorized_feed",
            "configured": _configured("KONKURSKUPP_FEED_URL"),
            "active": _configured("KONKURSKUPP_FEED_URL"),
            "required_configuration": ["KONKURSKUPP_FEED_URL"],
        },
        {
            "source": "Bjarøy",
            "access_mode": "authorized_feed",
            "configured": _configured("BJAROY_FEED_URL"),
            "active": _configured("BJAROY_FEED_URL"),
            "required_configuration": ["BJAROY_FEED_URL"],
        },
        {
            "source": "Konkurs.app",
            "access_mode": "authorized_feed",
            "configured": _configured("KONKURS_APP_FEED_URL"),
            "active": _configured("KONKURS_APP_FEED_URL"),
            "required_configuration": ["KONKURS_APP_FEED_URL"],
        },
    ]

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": "Only public category pages or explicitly authorized APIs/feeds are used; no access controls are bypassed.",
        "active_source_count": sum(bool(item["active"]) for item in sources),
        "configured_source_count": sum(bool(item["configured"]) for item in sources),
        "sources": sources,
    }

    output = Path("data/source_coverage.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "active_source_count": payload["active_source_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
