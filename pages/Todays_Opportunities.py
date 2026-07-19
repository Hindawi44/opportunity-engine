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

from opportunity_engine.ods.daily_opportunity_report import (  # noqa: E402
    DailyOpportunityReport,
    RankedDailyOpportunity,
)
from opportunity_engine.ods.today_dashboard import (  # noqa: E402
    OpportunityDisplayMetadata,
    build_today_dashboard,
)

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
    """Load a scheduler-produced JSON snapshot conservatively."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    report_date = date.fromisoformat(str(payload["report_date"]))
    raw_rows = payload.get("ranked", [])
    if not isinstance(raw_rows, list):
        raise ValueError("ranked must be a list")

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
        city = str(raw.get("city", "")).strip() or None
        ends_at = str(raw.get("ends_at", "")).strip() or None
        metadata[opportunity_id] = OpportunityDisplayMetadata(
            title=title,
            url=url,
            city=city,
            ends_at=ends_at,
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
    st.info(
        "لم يتم إنشاء لقطة فرص اليوم بعد. ستُنتجها مرحلة التشغيل المجدول التالية في "
        "data/todays_opportunities.json."
    )
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

rows = [
    {
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
    }
    for row in view.rows
]

st.dataframe(
    pd.DataFrame(rows),
    use_container_width=True,
    hide_index=True,
    column_config={
        "الإعلان": st.column_config.LinkColumn("فتح الإعلان", display_text="فتح"),
        "الربح المتوقع NOK": st.column_config.NumberColumn(format="%.0f kr"),
        "الحد الأقصى للمزايدة NOK": st.column_config.NumberColumn(format="%.0f kr"),
    },
)

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
