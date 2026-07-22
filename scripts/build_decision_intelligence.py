#!/usr/bin/env python3
"""Build transparent, evidence-gated decisions from scored opportunities.

No missing cost or market value is estimated. BUY_REVIEW is advisory only and
always requires human approval. Maximum safe bid is calculated only when the
upstream economic evaluation is complete and verified.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _decision(item: dict[str, object]) -> dict[str, object]:
    score = _number(item.get("opportunity_score")) or 0.0
    asking = _number(item.get("asking_price_nok"))
    resale = _number(item.get("conservative_resale_value_nok"))
    total_cost = _number(item.get("total_cost_nok"))
    profit = _number(item.get("expected_profit_nok"))
    roi = _number(item.get("roi_percent"))
    missing = item.get("missing_evidence")
    missing = [str(value) for value in missing] if isinstance(missing, list) else []
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
        final_decision_ar = "مراقبة وجمع الأدلة"
        reasons.append("البيانات الاقتصادية غير مكتملة، لذلك لا يمكن إصدار توصية شراء موثوقة.")
        if missing:
            warnings.append("أدلة ناقصة: " + ", ".join(missing))
        next_actions.extend([
            "استكمال ثلاث مقارنات سوقية موثقة.",
            "توثيق العمولة والضريبة والنقل والفك والتخزين والإصلاح.",
        ])
    elif profit <= 0 or roi < 15.0 or score < 45.0:
        final_decision = "REJECT"
        final_decision_ar = "رفض"
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
        final_decision_ar = "مراجعة للشراء"
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
        final_decision_ar = "مراقبة"
        reasons.append("الفرصة مكتملة اقتصاديًا لكنها لا تحقق جميع شروط مراجعة الشراء المحافظة.")
        if maximum_safe_bid is not None and asking is not None and asking > maximum_safe_bid:
            warnings.append(
                f"سعر الطلب {asking:.0f} أعلى من الحد الآمن {maximum_safe_bid:.0f} كرونة."
            )
        next_actions.append("راقب انخفاض السعر أو تحسن شروط التكلفة قبل إعادة التقييم.")

    result = dict(item)
    result.update({
        "final_decision": final_decision,
        "final_decision_ar": final_decision_ar,
        "decision_confidence": "HIGH" if economics_complete else "LOW",
        "maximum_safe_bid_nok": round(maximum_safe_bid, 2) if maximum_safe_bid is not None else None,
        "target_profit_buffer_nok": round(target_profit, 2) if target_profit is not None else None,
        "verified_operating_costs_nok": round(operating_costs, 2) if operating_costs is not None else None,
        "decision_reasons_ar": reasons,
        "decision_warnings_ar": warnings,
        "next_actions_ar": next_actions,
        "automatic_purchase": False,
        "requires_human_approval": final_decision == "BUY_REVIEW",
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build P4 decision intelligence")
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
    generated_at = datetime.now(timezone.utc).isoformat()
    output_payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "method": "verified evidence, conservative target-profit buffer, human approval required",
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
