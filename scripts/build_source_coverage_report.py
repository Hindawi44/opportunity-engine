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
    konkurs_app_feed_configured = _configured("KONKURS_APP_FEED_URL")
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
            "access_mode": "authorized_feed" if konkurs_app_feed_configured else "limited_public_api",
            "configured": True,
            "active": True,
            "coverage": "one recent active page per pipeline run",
            "page_size": int(os.getenv("KONKURS_APP_PAGE_SIZE", "25") or "25"),
            "authorized_feed_override": konkurs_app_feed_configured,
            "note": "Discovery leads only; the public API does not prove that assets are offered for sale.",
        },
    ]

    payload = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": "Only public documented endpoints, public category pages, or explicitly authorized APIs/feeds are used; no access controls are bypassed and no mass harvesting is performed.",
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
