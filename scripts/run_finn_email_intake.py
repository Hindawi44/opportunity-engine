#!/usr/bin/env python3
"""Parse supplied FINN saved-search emails into Clothing Inventory leads."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from opportunity_engine.discovery.finn_email_intake import (
    FinnEmailMessage,
    collect_finn_saved_search_messages,
    message_from_mapping,
    message_from_rfc822,
    run_finn_email_intake,
    write_finn_email_intake_artifacts,
)


def _load_json(path: Path) -> list[FinnEmailMessage]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
        payload = payload["messages"]
    elif isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError(f"{path}: JSON must be a message object or messages list")
    messages: list[FinnEmailMessage] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError(f"{path}: every message must be an object")
        messages.append(message_from_mapping(item))
    return messages


def _load(path: Path) -> list[FinnEmailMessage]:
    if path.suffix.casefold() == ".json":
        return _load_json(path)
    return [message_from_rfc822(path.read_bytes())]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "message_files",
        nargs="+",
        help="RFC822 .eml or connector-export .json files",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/finn-email-intake",
    )
    args = parser.parse_args()

    messages = [
        message
        for raw_path in args.message_files
        for message in _load(Path(raw_path))
    ]
    collection = collect_finn_saved_search_messages(messages)
    result = run_finn_email_intake(collection)
    paths = write_finn_email_intake_artifacts(
        result,
        collection,
        Path(args.output_dir),
    )

    report = result["search_run_report"]
    print(f"Execution status: {report['execution_status']}")
    print(f"Accepted FINN messages: {report['email_messages_accepted']}")
    print(f"Extracted FINN leads: {report['email_leads_extracted']}")
    print(f"Analysis-eligible opportunities: {report['analysis_eligible_count']}")
    print(f"Top opportunities requiring review: {report['top5_count']}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
