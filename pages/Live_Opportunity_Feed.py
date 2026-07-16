"""Streamlit dashboard for the persistent live opportunity feed."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import streamlit as st

from opportunity_engine.ods.brreg_collector import BrregSearchSlice
from opportunity_engine.ods.live_feed import LiveOpportunityFeed

st.set_page_config(page_title="ODS Live Opportunity Feed", page_icon="🛰️", layout="wide")
st.title("🛰️ Live Opportunity Feed — تغذية الفرص الحية")
st.caption(
    "يجمع هذا المسار إشارات رسمية محدودة من Brønnøysund، يحذف التكرار، ويحتفظ بوقت أول وآخر ظهور. "
    "ظهور شركة في الإفلاس أو التصفية لا يثبت أن أصولها معروضة للبيع."
)

with st.form("live-feed-form"):
    subjects_raw = st.text_area(
        "عبارات البحث — عبارة في كل سطر",
        value="klær\nbutikk\ninteriør",
        height=120,
    )
    col1, col2, col3 = st.columns(3)
    municipality = col1.text_input("البلدية (اختياري)")
    industry_code = col2.text_input("كود النشاط NACE (اختياري)")
    page_size = col3.slider("حجم عينة كل بحث", 1, 100, 50)
    submitted = st.form_submit_button("تحديث التغذية الحية", type="primary")

if submitted:
    subjects = tuple(
        dict.fromkeys(value.strip() for value in subjects_raw.replace(",", "\n").splitlines() if value.strip())
    )
    if not subjects:
        st.error("أدخل عبارة بحث واحدة على الأقل.")
    else:
        slices = tuple(
            BrregSearchSlice(
                subject=subject,
                municipality=municipality.strip() or None,
                industry_code=industry_code.strip() or None,
                page_size=page_size,
            )
            for subject in subjects
        )
        feed = LiveOpportunityFeed(
            ROOT / "data" / "live_opportunity_feed.json",
            ROOT / "data" / "live_feed_memory.json",
        )
        try:
            with st.spinner("يجري فحص المصادر وتحديث التغذية..."):
                result = feed.refresh(slices)
        except (OSError, RuntimeError, ValueError) as exc:
            st.error(f"تعذر تحديث التغذية: {exc}")
        else:
            st.success(f"اكتمل التحديث: {result.generated_at}")
            a, b, c, d = st.columns(4)
            a.metric("NEW", result.new_count)
            b.metric("UPDATED", result.updated_count)
            c.metric("UNCHANGED", result.unchanged_count)
            d.metric("REMOVED", result.removed_count)

            if result.collector.errors:
                st.subheader("أخطاء جزئية")
                for error in result.collector.errors:
                    st.warning(error)

            rows = []
            for item in result.items:
                official_url = next((value for value in item.evidence if value.startswith("https://")), None)
                rows.append({
                    "الحالة": item.status,
                    "الفرصة": item.title,
                    "الفئة": item.category,
                    "ODS/Ranking Score": item.score,
                    "أول اكتشاف": item.discovered_at,
                    "آخر ظهور": item.last_seen_at,
                    "مرات الظهور": item.times_seen,
                    "المصدر": item.source,
                    "الرابط الرسمي": official_url,
                })
            st.subheader("التغذية الحالية")
            if rows:
                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True,
                    column_config={"الرابط الرسمي": st.column_config.LinkColumn("الرابط الرسمي")},
                )
            else:
                st.info("لم تظهر إشارات إفلاس أو تصفية في عينات البحث الحالية.")

            st.caption(
                "الحفظ الحالي JSON محلي وقد لا يكون دائمًا بين إعادة تشغيل خادم Streamlit Cloud. "
                "هذه تغذية إشارات للتحقق، وليست قائمة أصول متاحة للشراء أو تقديرًا للربح."
            )
else:
    st.info("حدد عبارات البحث ثم اضغط «تحديث التغذية الحية».")
