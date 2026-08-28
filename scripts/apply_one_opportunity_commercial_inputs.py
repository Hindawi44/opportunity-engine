#!/usr/bin/env python3
"""Apply explicit VAT-aware commercial inputs to the latest selected opportunity."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from opportunity_engine.discovery.one_opportunity_commercial_vat_basis_v1 import (
    apply_commercial_inputs_with_vat_basis,
    render_commercial_analysis_with_vat_basis,
)


def _load(path: str | Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--opportunity-id", required=True)
    parser.add_argument(
        "--quantity-condition-status",
        choices=("CONFIRMED", "NOT_CONFIRMED"),
        required=True,
    )
    parser.add_argument("--final-payable-price-nok", required=True)
    parser.add_argument("--recoverable-input-vat-nok", required=True)
    parser.add_argument("--transport-nok", required=True)
    parser.add_argument("--conservative-resale-nok", required=True)
    parser.add_argument("--resale-output-vat-nok", required=True)
    parser.add_argument("--resale-comparable-count", required=True)
    parser.add_argument("--review-note", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = apply_commercial_inputs_with_vat_basis(
        _load(args.analysis),
        opportunity_identity=args.opportunity_id,
        quantity_condition_confirmed=args.quantity_condition_status == "CONFIRMED",
        final_payable_price_nok=args.final_payable_price_nok,
        recoverable_input_vat_nok=args.recoverable_input_vat_nok,
        transport_nok=args.transport_nok,
        conservative_resale_nok=args.conservative_resale_nok,
        resale_output_vat_nok=args.resale_output_vat_nok,
        resale_comparable_count=args.resale_comparable_count,
        review_note=args.review_note,
    )
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "one-opportunity-commercial-analysis.json"
    text_path = output / "one-opportunity-commercial-analysis.txt"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    text_path.write_text(
        render_commercial_analysis_with_vat_basis(report),
        encoding="utf-8",
    )
    print(text_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
