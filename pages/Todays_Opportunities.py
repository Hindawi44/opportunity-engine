"""Streamlit page for the ranked daily opportunity snapshot."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from opportunity_engine.ods.daily_opportunity_report import DailyOpportunityReport, RankedDailyOpportunity  # noqa: E402
from opportunity_engine.ods.today_dashboard import OpportunityDisplayMetadata, build_today_dashboard  # noqa: E402

SNAPSHOT_PATH = ROOT / "data" / "todays_opportunities.json"


def _tuple_text(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_dashboard_snapshot(path: Path = SNAPSHOT_PATH):
    """Load the scheduler-produced snapshot using the current ``rows`` schema.

    ``ranked`` remains supported for backwards compatibility with older snapshots.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    report_date = date.fromisoformat(str(payload["report_date"]))
    raw_rows = payload.get("rows", payload.get("ranked", []))
    if not isinstance(raw_rows, list):
        raise ValueError("rows must be a list")

    ranked: list[RankedDailyOpportunity] = []
    metadata: dict[str, OpportunityDisplayMetadata] = {}
    for index, raw in enumerate(raw_rows, start=1):
        if not isinstance(raw, dict):
            continue
        opportunity_id = str(raw.get("opportunity_id", "")).strip()
        if not opportunity_id:
            continue
        ranked.append(
            RankedDailyOpportunity(
                rank=int(raw.get("rank", index)),
                opportunity_id=opportunity_id,
                decision=str(raw.get("decision", "monitor")),
                decision_label=str(raw.get("decision_label", "🟡 راقب")),
                score=float(raw.get("score", 0.0)),
                score_grade=str(raw.get("score_grade", "U")),
                score_breakdown=_tuple_text(raw.get("score_breakdown")),
                expected_profit_nok=_optional_float(raw.get("expected_profit_nok")),
                roi=_optional_float(raw.get("roi")),
                confidence=str(raw.get("confidence", "insufficient")),
                maximum_purchase_price_nok=_optional_float(raw.get("maximum_purchase_price_nok")),
                reasons=_tuple_text(raw.get("reasons")),
                warnings=_tuple_text(raw.get("warnings")),
                blockers=_tuple_text(raw.get("blockers")),
            )
        )
        title = str(raw.get("title") or opportunity_id).strip()
        url = str(raw.get("url", "")).strip() or None
        metadata[opportunity_id] = OpportunityDisplayMetadata(
            title=title,
            url=url,
            city=str(raw.get("city", "")).strip() or None,
            ends_at=str(raw.get("ends_at", "")).strip() or None,
            asking_price_nok=_optional_float(raw.get("asking_price_nok")),
            market_value_nok=_optional_float(raw.get("market_value_nok")),
            market_median_nok=_optional_float(raw.get("market_median_nok")),
            market_discount=_optional_float(raw.get("market_discount")),
            market_verification_status=str(raw.get("market_verification_status", "unavailable")),
            market_verification_label=str(raw.get("market_verification_label", "⚪ سوق غير متحقق")),
            market_comparable_count=int(raw.get("market_comparable_count", 0) or 0),
            market_is_verified=raw.get("market_is_verified") is True,
            first_seen_at=raw.get("first_seen_at"),
            last_seen_at=raw.get("last_seen_at"),
            first_price_nok=_optional_float(raw.get("first_price_nok")),
            lowest_price_nok=_optional_float(raw.get("lowest_price_nok")),
            highest_price_nok=_optional_float(raw.get("highest_price_nok")),
            price_change_count=int(raw.get("price_change_count", 0) or 0),
            price_change_from_first=_optional_float(raw.get("price_change_from_first")),
            listing_age_days=int(raw.get("listing_age_days", 0) or 0),
            price_history_status=str(raw.get("price_history_status", "unpriced")),
            price_history_label=str(raw.get("price_history_label", "⚪ لا يوجد سعر")),
            significant_price_drop=raw.get("significant_price_drop") is True,
            seller_id=raw.get("seller_id"),
            seller_name=raw.get("seller_name"),
            seller_type=raw.get("seller_type"),
            seller_score=_optional_float(raw.get("seller_score")),
            seller_grade=str(raw.get("seller_grade", "U")),
            seller_risk=str(raw.get("seller_risk", "unknown")),
            seller_risk_label=str(raw.get("seller_risk_label", "⚪ بائع غير متحقق")),
            seller_confidence=str(raw.get("seller_confidence", "insufficient")),
            seller_is_verified=raw.get("seller_is_verified") is True,
            seller_evidence_count=int(raw.get("seller_evidence_count", 0) or 0),
            seller_reasons=_tuple_text(raw.get("seller_reasons")),
            seller_warnings=_tuple_text(raw.get("seller_warnings")),
        )

    report = DailyOpportunityReport(
        report_date=report_date,
        total_count=int(payload.get("total_count", len(ranked))),
        buy_count=int(payload.get("buy_count", sum(item.decision == "buy" for item in ranked))),
        monitor_count=int(payload.get("monitor_count", sum(item.decision == "monitor" for item in ranked))),
        reject_count=int(payload.get("reject_count", sum(item.decision == "reject" for item in ranked))),
        ranked=tuple(ranked),
        summary_lines=_tuple_text(payload.get("summary_lines")),
    )
    return build_today_dashboard(report, metadata)


st.set_page_config(page_title="فرص اليوم", page_icon="📊", layout="wide")
st.title("📊 فرص اليوم")
st.caption("قرارات محافظة مبنية على بيانات السوق والتكاليف المتوفرة. تحقق يدويًا من الإعلان قبل أي شراء.")

if not SNAPSHOT_PATH.exists():
    st.info("لم يتم إنشاء لقطة فرص اليوم بعد. ستُنتجها مرحلة التشغيل المجدول التالية في data/todays_opportunities.json.")
    st.stop()

try:
    view = load_dashboard_snapshot()
except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
    st.error(f"تعذر قراءة تقرير فرص اليوم: {exc}")
    st.stop()

st.caption(f"تاريخ التقرير: {view.report_date}")
metric_columns = st.columns(4)
metric_columns[0].metric("كل الفرص", view.total_count)
metric_columns[1].metric("🟢 شراء", view.buy_count)
metric_columns[2].metric("🟡 مراقبة", view.monitor_count)
metric_columns[3].metric("🔴 رفض", view.reject_count)

for line in view.summary_lines:
    st.write(line)

if not view.rows:
    st.warning("لا توجد فرص قابلة للعرض في التقرير الحالي.")
    st.stop()

rows = [{
    "الترتيب": row.rank,
    "الفرصة": row.title,
    "القرار": row.decision_label,
    "الربح المتوقع NOK": row.expected_profit_nok,
    "ROI %": None if row.roi is None else round(row.roi * 100, 1),
    "الحد الأقصى للمزايدة NOK": row.maximum_purchase_price_nok,
    "الثقة": row.confidence,
    "المدينة": row.city,
    "ينتهي": row.ends_at,
    "الإعلان": row.url,
} for row in view.rows]

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, column_config={
    "الإعلان": st.column_config.LinkColumn("فتح الإعلان", display_text="فتح"),
    "الربح المتوقع NOK": st.column_config.NumberColumn(format="%.0f kr"),
    "الحد الأقصى للمزايدة NOK": st.column_config.NumberColumn(format="%.0f kr"),
})

st.subheader("تفاصيل القرارات")
for row in view.rows:
    with st.expander(f"#{row.rank} — {row.decision_label} — {row.title}"):
        if row.url:
            st.link_button("فتح الإعلان الأصلي", row.url)
        if row.reasons:
            st.markdown("**سبب القرار**")
            for reason in row.reasons:
                st.write(f"- {reason}")
        if row.warnings:
            st.markdown("**التحذيرات**")
            for warning in row.warnings:
                st.warning(warning)
        if row.blockers:
            st.markdown("**البيانات الناقصة أو الموانع**")
            for blocker in row.blockers:
                st.write(f"- {blocker}")
