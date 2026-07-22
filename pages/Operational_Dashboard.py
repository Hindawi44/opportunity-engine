"""Mobile-first read-only operational dashboard."""
from __future__ import annotations

from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from opportunity_engine.operational_dashboard import build_snapshot

st.set_page_config(page_title="Operational Dashboard", page_icon="📊", layout="wide")
st.title("📊 لوحة التشغيل اليومية")
st.caption("قرارات ومتابعات وصحة المصادر — عرض فقط، دون شراء أو مزايدة تلقائية.")

try:
    snapshot = build_snapshot(ROOT / "data")
except ValueError as exc:
    st.error(str(exc))
    st.stop()

if snapshot.warnings:
    for warning in snapshot.warnings:
        st.error(warning)

c1, c2, c3, c4 = st.columns(4)
c1.metric("🟢 BUY_REVIEW", snapshot.counts["BUY_REVIEW"])
c2.metric("🟡 WATCH", snapshot.counts["WATCH"])
c3.metric("🔴 REJECT", snapshot.counts["REJECT"])
c4.metric("⏰ متأخرة", len(snapshot.overdue_follow_ups))

health_status = str(snapshot.health.get("status") or snapshot.health.get("pipeline_status") or "UNKNOWN").upper()
if health_status in {"HEALTHY", "SUCCESS", "OK"}:
    st.success(f"صحة النظام: {health_status}")
elif health_status in {"DEGRADED", "WARNING", "PARTIAL"}:
    st.warning(f"صحة النظام: {health_status}")
else:
    st.info(f"صحة النظام: {health_status}")

st.subheader("الفرص الحالية")
filter_value = st.selectbox("عرض القرار", ["ALL", "BUY_REVIEW", "WATCH", "REJECT"])
items = snapshot.decisions
if filter_value != "ALL":
    items = [item for item in items if item.get("canonical_decision") == filter_value]

if not items:
    st.info("لا توجد فرص ضمن هذا الفلتر.")

for item in items:
    decision = item.get("canonical_decision", "WATCH")
    title = item.get("title") or item.get("opportunity_id") or "فرصة بلا عنوان"
    with st.container(border=True):
        st.markdown(f"### {title}")
        a, b = st.columns(2)
        a.write(f"**القرار:** {decision}")
        b.write(f"**المدينة:** {item.get('city') or 'غير متاحة'}")
        st.write(f"**السعر المطلوب:** {item.get('asking_price_nok') if item.get('asking_price_nok') is not None else 'غير متاح'} NOK")
        safe_bid = item.get("maximum_safe_bid_nok")
        st.write(f"**الحد الآمن للمزايدة:** {safe_bid if safe_bid is not None else 'غير محسوب'}")
        next_action = item.get("next_action") or item.get("suggested_action")
        if next_action:
            st.write(f"**الإجراء التالي:** {next_action}")
        reasons = item.get("decision_reasons_ar") or item.get("reasons") or []
        if isinstance(reasons, list) and reasons:
            st.write("**أسباب القرار:**")
            for reason in reasons:
                st.write(f"• {reason}")
        url = item.get("url") or item.get("canonical_url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            st.link_button("فتح الإعلان", url, use_container_width=True)

st.subheader("المتابعات المستحقة والمتأخرة")
if not snapshot.follow_ups:
    st.info("لا توجد مهام متابعة حاليًا.")
else:
    for task in snapshot.follow_ups:
        status = str(task.get("status") or "PENDING").upper()
        if status not in {"DUE", "OVERDUE"}:
            continue
        with st.container(border=True):
            st.write(f"**{task.get('title') or task.get('opportunity_id') or 'متابعة'}**")
            st.write(f"الحالة: {status}")
            st.write(f"الموعد: {task.get('due_at') or task.get('follow_up_at') or 'غير محدد'}")
            st.write(f"الإجراء: {task.get('next_action') or task.get('action') or 'مراجعة بشرية'}")

st.subheader("صحة المصادر")
sources = snapshot.health.get("sources")
if isinstance(sources, dict) and sources:
    for source, value in sources.items():
        status = value.get("status") if isinstance(value, dict) else value
        st.write(f"• **{source}:** {status}")
else:
    st.caption("لا توجد تفاصيل مصادر في التقرير الحالي.")

st.subheader("التعلم الآمن")
st.write(f"الوضع: {snapshot.learning.get('mode', 'غير متاح')}")
st.write(f"تحديث الأوزان تلقائيًا: {snapshot.learning.get('automatic_weight_updates', False)}")
st.caption("هذه الصفحة للعرض واتخاذ القرار البشري فقط. لا تنفذ شراءً أو مزايدة.")
