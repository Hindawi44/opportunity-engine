#!/usr/bin/env python3
"""Compare a date-stamped external ground-truth benchmark with saved engine artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.external_ground_truth_benchmark import evaluate_external_ground_truth

_TEXT_SUFFIXES = {".json", ".txt", ".md", ".csv", ".log", ".html"}


def _load_documents(root: Path) -> dict[str, object]:
    documents: dict[str, object] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in _TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if path.suffix.casefold() == ".json":
            try:
                documents[path.relative_to(root).as_posix()] = json.loads(text)
                continue
            except json.JSONDecodeError:
                pass
        documents[path.relative_to(root).as_posix()] = text
    return documents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    benchmark = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
    documents = _load_documents(Path(args.artifact_root))
    report = evaluate_external_ground_truth(benchmark, documents=documents)
    report["benchmark_path"] = Path(args.benchmark).as_posix()
    report["artifact_root"] = Path(args.artifact_root).as_posix()
    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "benchmark_count": report["benchmark_count"],
        "baseline_found_count": report["baseline_found_count"],
        "confirmed_miss_count": report["confirmed_miss_count"],
        "root_cause_counts": report["root_cause_counts"],
        "production_mutation": report["production_mutation"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
