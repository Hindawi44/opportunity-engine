#!/usr/bin/env python3
"""Prepare human-review outreach drafts for eligible estate-manager cases."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from opportunity_engine.discovery.estate_manager_outreach_review import (
    build_outreach_review,
    write_outreach_review_artifacts,
)


def _read_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"JSON file must contain an object: {path}")
    return payload


def _read_array(path: Path) -> Sequence[object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError(f"JSON file must contain an array: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-registry", required=True, type=Path)
    parser.add_argument("--operator-actions", required=True, type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/estate-manager-outreach-review"),
    )
    parser.add_argument("--sender-name", default="Mahmoud")
    parser.add_argument("--sender-business", default="Namsos Skredderhus")
    args = parser.parse_args()

    result = build_outreach_review(
        _read_object(args.case_registry),
        _read_array(args.operator_actions),
        sender_name=args.sender_name,
        sender_business=args.sender_business,
    )
    paths = write_outreach_review_artifacts(result, args.output_dir)

    print(f"Eligible operator actions: {result.eligible_action_count}")
    print(f"Draft packets created: {len(result.packets)}")
    print(f"Cases skipped: {len(result.skipped)}")
    print("Automatic contact lookup/email/contact: false")
    print("Human approval required: true")
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
