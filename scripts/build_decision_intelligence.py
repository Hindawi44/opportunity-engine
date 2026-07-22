#!/usr/bin/env python3
"""Build transparent, evidence-gated decisions from scored opportunities.

P4.1 makes ``final_decision`` the canonical decision. Legacy recommendation
fields are synchronized for backwards compatibility; no consumer may observe a
WATCH/REJECT contradiction. Missing evidence is presented in Arabic while raw
keys remain available for machine processing.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


EVIDENCE_LABELS_AR = {
    "three_verified_market_comparables": "ثلاث مقارنات سوقية موثقة",
    "pending_market_comparables_require_review": "مراجعة المقارنات السوقية المرشحة",
    "auction_fee": "عمولة المزاد",
    "auction_fee_nok": "عمولة المزاد",
    "vat_status": "حالة ضريبة القيمة المضافة",
    "vat_nok": "قيمة ضريبة القيمة المضافة",
    "transport_cost": "تكلفة النقل",
    "transport_cost_nok": "تكلفة النقل",
    "dismantling_cost": "تكلفة الفك",
    "dismantling_cost_nok": "تكلفة الفك",
    "storage_cost_nok": "تكلفة التخزين",
    "repair_cost_nok": "تكلفة الإصلاح",
    "other_costs_nok": "التكاليف الأخرى",
    "condition_and_missing_parts": "حالة البضاعة والأجزاء الناقصة",
}

DECISION_AR = {
    "BUY_REVIEW": "مراجعة للشراء",
    "WATCH": "مراقبة وجمع الأدلة",
    "REJECT": "رفض",
}


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _arabic_evidence_labels(keys: list[str]) -> list[str]:
    return [EVIDENCE_LABELS_AR.get(key, key.replace("_nok", "").replace("_", " ")) for key in keys]


def _decision(item: dict[str, object]) -> dict[str, object]:
    score = _number(item.get("opportunity_score")) or 0.0
    asking = _number(item.get("asking_price_nok"))
    resale = _number(item.get("conservative_resale_value_nok"))
    total_cost = _number(item.get("total_cost_nok"))
    profit = _number(item.get("expected_profit_nok"))
    roi = _number(item.get("roi_percent"))
    missing_raw = item.get("missing_evidence")
    missing = [str(value) for value in missing_raw] if isinstance(missing_raw, list) else []
    missing_ar = _arabic_evidence_labels(missing)
    economics_complete = (
        item.get("decision") == "REVIEW_NUMBERS"
        and asking is not None
        and resale is not None
        and total_cost is not None
        and profit is not None
        and roi is not None
        and not missing
    )

    maximum_safe_bid = None
    target_profit = None
    operating_costs = None
    if economics_complete:
        operating_costs = max(0.0, total_cost - asking)
        target_profit = max(2_000.0, resale * 0.20)
        maximum_safe_bid = max(0.0, resale - operating_costs - target_profit)

    reasons: list[str] = []
    warnings: list[str] = []
    next_actions: list[str] = []

    if not economics_complete:
        final_decision = "WATCH"
        reasons.append("البيانات الاقتصادية غير مكتملة، لذلك لا يمكن إصدار توصية شراء موثوقة.")
        if missing_ar:
            warnings.append("أدلة ناقصة: " + "، ".join(missing_ar))
        next_actions.extend([
            "استكمال ثلاث مقارنات سوقية موثقة.",
            "توثيق العمولة والضريبة والنقل والفك والتخزين والإصلاح.",
        ])
    elif profit <= 0 or roi < 15.0 or score < 45.0:
        final_decision = "REJECT"
        reasons.append("الربحية أو العائد أو الدرجة لا تحقق الحد الأدنى المحافظ.")
        if profit <= 0:
            warnings.append("الربح المتوقع غير إيجابي.")
        if roi < 15.0:
            warnings.append(f"العائد المتوقع منخفض: {roi:.1f}%.")
        if score < 45.0:
            warnings.append(f"درجة الفرصة منخفضة: {score:.1f}/100.")
    elif (
        item.get("recommendation") == "BUY_REVIEW"
        and score >= 75.0
        and profit >= 2_000.0
        and roi >= 30.0
        and maximum_safe_bid is not None
        and asking is not None
        and asking <= maximum_safe_bid
    ):
        final_decision = "BUY_REVIEW"
        reasons.extend([
            "الأدلة الاقتصادية مكتملة وفق المدخلات الموثقة.",
            f"الربح المتوقع {profit:.0f} كرونة والعائد {roi:.1f}%.",
            f"سعر الطلب لا يتجاوز الحد الأقصى الآمن للمزايدة ({maximum_safe_bid:.0f} كرونة).",
        ])
        warnings.append("هذه توصية للمراجعة البشرية وليست أمر شراء تلقائيًا.")
        next_actions.extend([
            "فحص حالة البضاعة والأجزاء الناقصة قبل المزايدة.",
            "تأكيد تكلفة النقل والفك كتابيًا.",
            "عدم تجاوز الحد الأقصى الآمن للمزايدة.",
        ])
    else:
        final_decision = "WATCH"
        reasons.append("الفرصة مكتملة اقتصاديًا لكنها لا تحقق جميع شروط مراجعة الشراء المحافظة.")
        if maximum_safe_bid is not None and asking is not None and asking > maximum_safe_bid:
            warnings.append(f"سعر الطلب {asking:.0f} أعلى من الحد الآمن {maximum_safe_bid:.0f} كرونة.")
        next_actions.append("راقب انخفاض السعر أو تحسن شروط التكلفة قبل إعادة التقييم.")

    final_decision_ar = DECISION_AR[final_decision]
    result = dict(item)
    result.update({
        "final_decision": final_decision,
        "final_decision_ar": final_decision_ar,
        "official_decision_field": "final_decision",
        # Backwards-compatible aliases: always identical to the canonical decision.
        "recommendation": final_decision,
        "recommendation_ar": final_decision_ar,
        "decision_confidence": "HIGH" if economics_complete else "LOW",
        "maximum_safe_bid_nok": round(maximum_safe_bid, 2) if maximum_safe_bid is not None else None,
        "target_profit_buffer_nok": round(target_profit, 2) if target_profit is not None else None,
        "verified_operating_costs_nok": round(operating_costs, 2) if operating_costs is not None else None,
        "missing_evidence_ar": missing_ar,
        "decision_reasons_ar": reasons,
        "decision_warnings_ar": warnings,
        "next_actions_ar": next_actions,
        "automatic_purchase": False,
        "requires_human_approval": final_decision == "BUY_REVIEW",
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build P4.1 decision intelligence")
    parser.add_argument("--scored", default="data/scored_opportunities.json")
    parser.add_argument("--output", default="data/decision_intelligence.json")
    args = parser.parse_args()

    payload = json.loads(Path(args.scored).read_text(encoding="utf-8"))
    opportunities = payload.get("opportunities", [])
    if not isinstance(opportunities, list):
        raise ValueError("scored opportunities must be a list")

    decisions = [_decision(item) for item in opportunities if isinstance(item, dict)]
    priority = {"BUY_REVIEW": 0, "WATCH": 1, "REJECT": 2}
    decisions.sort(key=lambda item: (
        priority.get(str(item.get("final_decision")), 9),
        -float(item.get("opportunity_score") or 0),
    ))
    for item in decisions:
        if item.get("recommendation") != item.get("final_decision"):
            raise ValueError("decision consistency invariant violated")

    generated_at = datetime.now(timezone.utc).isoformat()
    output_payload = {
        "schema_version": 2,
        "generated_at": generated_at,
        "method": "canonical final decision, verified evidence, conservative target-profit buffer, human approval required",
        "official_decision_field": "final_decision",
        "decision_count": len(decisions),
        "buy_review_count": sum(item["final_decision"] == "BUY_REVIEW" for item in decisions),
        "watch_count": sum(item["final_decision"] == "WATCH" for item in decisions),
        "reject_count": sum(item["final_decision"] == "REJECT" for item in decisions),
        "decisions": decisions,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"decision_count": len(decisions), "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
