#!/usr/bin/env python3
"""Manage the persistent opportunity portfolio ledger."""

from __future__ import annotations

import argparse
import json

from opportunity_engine.ods.portfolio_manager import PortfolioManager, snapshot_to_dict


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage confirmed opportunity purchases and sales")
    parser.add_argument("--database", default="data/portfolio.json")
    parser.add_argument("--initial-capital", type=float, default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    purchase = sub.add_parser("purchase")
    purchase.add_argument("--opportunity-id", required=True)
    purchase.add_argument("--title", required=True)
    purchase.add_argument("--purchase-price", required=True, type=float)
    purchase.add_argument("--acquisition-cost", type=float, default=0.0)
    purchase.add_argument("--estimated-value", type=float, default=None)
    purchase.add_argument("--notes", default=None)

    value = sub.add_parser("value")
    value.add_argument("--opportunity-id", required=True)
    value.add_argument("--estimated-value", type=float, default=None)

    sale = sub.add_parser("sale")
    sale.add_argument("--opportunity-id", required=True)
    sale.add_argument("--sale-price", required=True, type=float)
    sale.add_argument("--selling-cost", type=float, default=0.0)

    sub.add_parser("snapshot")
    args = parser.parse_args()

    manager = PortfolioManager(args.database, initial_capital_nok=args.initial_capital)
    if args.command == "purchase":
        result = manager.record_purchase(
            opportunity_id=args.opportunity_id,
            title=args.title,
            purchase_price_nok=args.purchase_price,
            acquisition_cost_nok=args.acquisition_cost,
            estimated_value_nok=args.estimated_value,
            notes=args.notes,
        )
        print(json.dumps(result.__dict__, ensure_ascii=False, sort_keys=True))
    elif args.command == "value":
        result = manager.update_estimated_value(args.opportunity_id, args.estimated_value)
        print(json.dumps(result.__dict__, ensure_ascii=False, sort_keys=True))
    elif args.command == "sale":
        result = manager.record_sale(
            args.opportunity_id,
            sale_price_nok=args.sale_price,
            selling_cost_nok=args.selling_cost,
        )
        print(json.dumps(result.__dict__, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(snapshot_to_dict(manager.snapshot()), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
