"""Streamlit control page for one auditable autonomous research cycle."""
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from opportunity_engine.ods.autonomous_agent import AutonomousResearchAgent
from opportunity_engine.ods.brreg_collector import BrregSearchSlice

st.set_page_config(page_title="ODS Autonomous Research Agent", page_icon="🤖", layout="wide")
st.title("🤖 Autonomous Research Agent — وكيل البحث المستقل")
st.caption(
    "ينفّذ دورة بحث واحدة كاملة: جمع → تغذية حية → إثراء الأدلة → قرار → تنبيهات التغييرات فقط. "
    "التشغيل الدوري يحتاج Scheduler خارجي؛ Streamlit لا يعمل كخدمة خلفية دائمة."
)

with st.form("agent-run-form"):
    subjects_raw = st.text_area(
        "عبارات البحث — عبارة في كل سطر",
        value="butikk\nklær\ninteriør",
        height=120,
    )
    left, middle, right = st.columns(3)
    municipality = left.text_input("البلدية (اختياري)")
    industry_code = middle.text_input("كود النشاط NACE (اختياري)")
    page_size = right.slider("حجم عينة كل شريحة", 1, 100, 50)
    submitted = st.form_submit_button("تشغيل دورة البحث", type="primary")

if submitted:
    subjects = tuple(
        value.strip()
        for value in subjects_raw.replace(",", "\n").splitlines()
        if value.strip()
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
        data_dir = ROOT / "data"
        agent = AutonomousResearchAgent(
            feed_path=data_dir / "live_opportunity_feed.json",
            memory_path=data_dir / "brreg_opportunity_history.json",
            alert_state_path=data_dir / "autonomous_agent_alert_state.json",
            run_log_path=data_dir / "autonomous_agent_runs.jsonl",
        )
        try:
            with st.spinner("يجري تشغيل دورة البحث المتكاملة..."):
                result = agent.run(slices)
        except (OSError, RuntimeError, ValueError) as exc:
            st.error(f"تعذر إكمال دورة البحث: {exc}")
        else:
            st.success("اكتملت دورة البحث.")
            a, b, c, d = st.columns(4)
            a.metric("الفرص النشطة", len(result.decisions))
            b.metric("التنبيهات الجديدة", len(result.alerts))
            c.metric("التنبيهات المكررة المحجوبة", result.suppressed_count)
            d.metric("الشرائح الفاشلة", result.feed.collector.slices_failed)

            if result.alerts:
                st.subheader("التغييرات التي تستحق الانتباه")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "الفرصة": alert.title,
                                "نوع التغيير": alert.change_type,
                                "القرار": alert.decision,
                                "درجة القرار": alert.decision_score,
                                "السبب": alert.reason,
                            }
                            for alert in result.alerts
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("لا توجد تغييرات جديدة تستحق تنبيهًا في هذه الدورة.")

            if result.decisions:
                st.subheader("جميع القرارات الحالية")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "الفرصة": report.title,
                                "القرار": report.decision.value,
                                "درجة القرار": report.decision_score,
                                "درجة الأدلة": report.evidence_score,
                                "اكتمال الأدلة %": report.evidence_completeness,
                                "المصادر المستقلة": report.independent_sources,
                            }
                            for report in result.decisions
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

            st.caption(
                "التخزين الحالي ملفات JSON/JSONL محلية، وقد لا يستمر بعد إعادة تشغيل Streamlit Cloud. "
                "لا يرسل الوكيل بريدًا أو Telegram، ولا ينفذ شراءً تلقائيًا."
            )
