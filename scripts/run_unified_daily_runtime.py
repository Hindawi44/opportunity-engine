#!/usr/bin/env python3
"""Build the visible six-market runtime after the daily bulletin is complete."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from opportunity_engine.discovery.unified_daily_runtime import (
    build_unified_daily_runtime,
)
from opportunity_engine.human_listing_review_queue import build_queue, readable_text
from opportunity_engine.balanced_link_review import build_balanced_review, readable_balanced_review
from opportunity_engine.operator_study_memory import export_memory
from opportunity_engine.source_status_reconciliation import reconcile_auksjonen_snapshot
from opportunity_engine.source_page_audit import audit_review_batch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="artifacts/multi-market-daily-operator-checkpoint",
    )
    parser.add_argument("--input-root", default="artifacts/multi-market-inputs")
    args = parser.parse_args()

    os.environ["OUTPUT_DIR"] = args.output_dir
    os.environ["INPUT_ROOT"] = args.input_root
    output_dir = Path(args.output_dir)
    paths = build_unified_daily_runtime(output_dir)
    report_path = output_dir / "multi-market-daily-checkpoint.json"
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        memory = export_memory(Path(args.input_root))
        queue = build_queue(report, memory)
        source_snapshot = Path(args.input_root) / "no-auksjonen" / "auksjonen-live-clothing-listings.json"
        if source_snapshot.is_file():
            try:
                evidence = json.loads(source_snapshot.read_text(encoding="utf-8"))
                queue = reconcile_auksjonen_snapshot(queue, evidence)
            except (OSError, ValueError, TypeError, AttributeError) as exc:
                queue["counts"]["auksjonen_snapshot_status"] = "UNREADABLE_SOURCE_SNAPSHOT"
                queue["counts"]["auksjonen_snapshot_error_type"] = type(exc).__name__
        else:
            queue["counts"]["auksjonen_snapshot_status"] = "MISSING_NO_ENDING_INFERRED"
        # This is strictly source-page read-only; it performs no paid search or
        # commercial action. Avoid external network calls in pytest regression.
        production_run = os.environ.get("GITHUB_ACTIONS") == "true" and "PYTEST_CURRENT_TEST" not in os.environ
        if production_run or os.environ.get("OPPORTUNITY_ENGINE_SOURCE_PAGE_AUDIT") == "1":
            queue = audit_review_batch(queue)
            (output_dir / "human-listing-page-audit-v1.json").write_text(
                json.dumps({"counts": queue["counts"], "audit": queue["source_page_audit"],
                            "batch": queue["daily_batch"], "held": queue["held_separately"]},
                           ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        # The discovery inbox does not relax evidence gates in the strict queue.
        # It restores suppressed source-specific leads and preserves campaign
        # parents as navigation tasks, never as verified individual lots.
        balanced = build_balanced_review(report, queue, memory)
        (output_dir / "human-balanced-link-review-v1.json").write_text(
            json.dumps(balanced, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (output_dir / "human-listing-review-queue-v1.json").write_text(
            json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        text = readable_text(queue)
        text += "\nتدقيق حالة مزادات Auksjonen (دليل مصدر مؤرخ، وليس تأكيد مخزون):\n"
        text += "حالة ملف المصدر: " + queue["counts"]["auksjonen_snapshot_status"] + "\n"
        for row in queue["daily_batch"]:
            proof = row.get("source_status_evidence")
            if proof:
                text += (f"- {row['title']}: {proof['status']} عند {proof['captured_at']}؛ "
                         f"نهاية معلنة {proof['ends_at']}؛ المخزون غير مؤكد.\n")
            elif row.get("source_status_note"):
                text += f"- {row['title']}: {row['source_status_note']}\n"
        if "source_page_audit" in queue:
            text += "\nتدقيق صفحات المصدر المحدود (لا يثبت هوية الشركة أو المخزون):\n"
            text += (f"فُحصت {queue['counts']['page_audit_attempted']} صفحات؛ "
                     f"هوية منتج من المصدر {queue['counts']['page_audit_product_id_evidence']}؛ "
                     f"تحويلات محتجزة {queue['counts']['page_audit_redirect_held']}؛ "
                     f"نفاد معلن {queue['counts']['page_audit_sold_out_held']}.\n")
            for row in queue["daily_batch"]:
                text += (f"- {row['title']}: "
                         f"{row.get('source_page_check_status', 'NOT_CHECKED')}; "
                         "الشركة والمخزون غير مؤكدين.\n")
        # Display actionable search leads to the human without inventing trade
        # qualifications or disguising a parent page as a direct item listing.
        text += "\n" + readable_balanced_review(balanced)
        (output_dir / "human-listing-review-queue-v1.txt").write_text(text, encoding="utf-8")
        phone_summary = output_dir / "multi-market-phone-summary.txt"
        if phone_summary.is_file():
            with phone_summary.open("a", encoding="utf-8") as handle:
                handle.write("\n" + text)
        print("human_listing_review_queue:", queue["counts"])
        print("balanced_link_review:", balanced["counts"])
    elif os.environ.get("GITHUB_ACTIONS") == "true":
        raise FileNotFoundError(f"Daily review source checkpoint is missing: {report_path}")
    print(f"unified_daily_pipeline: {paths['pipeline']}")
    print(f"unified_daily_runtime: {paths['runtime']}")
    print(f"unified_daily_summary: {paths['summary']}")
    print(f"unified_daily_reconciliation: {paths['reconciliation']}")
    print(f"unified_operator_report_json: {paths['operator_report_json']}")
    print(f"unified_operator_report_text: {paths['operator_report_text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
