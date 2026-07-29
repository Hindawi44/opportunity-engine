#!/usr/bin/env python3
"""Run one bounded public network probe against ny.auksjonen.no."""
from __future__ import annotations

import argparse
from pathlib import Path

from opportunity_engine.discovery.auksjonen_live_probe import (
    AuksjonenLiveProbeConfig,
    AuksjonenLiveSourceProbe,
    DEFAULT_ENTRY_URL,
    write_probe_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry-url", default=DEFAULT_ENTRY_URL)
    parser.add_argument(
        "--output-dir",
        default="artifacts/auksjonen-live-source-probe",
    )
    parser.add_argument("--delay-seconds", type=float, default=7.0)
    parser.add_argument("--max-responses", type=int, default=60)
    args = parser.parse_args()

    probe = AuksjonenLiveSourceProbe(AuksjonenLiveProbeConfig(
        entry_url=args.entry_url,
        delay_seconds=args.delay_seconds,
        max_responses=args.max_responses,
    ))
    result = probe.run()
    paths = write_probe_artifacts(result, Path(args.output_dir))

    print("Auksjonen live-source probe completed")
    print(f"Final URL: {result.final_url}")
    print(f"JSON/API responses: {len(result.network_responses)}")
    print(f"Candidate objects: {len(result.candidate_objects)}")
    print(f"DOM links: {len(result.dom_links)}")
    print(f"Errors: {len(result.errors)}")
    print("Paid Brave/OpenAI calls: 0")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
