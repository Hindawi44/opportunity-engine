"""First user-facing Streamlit interface for ODS alpha."""

from __future__ import annotations

from pathlib import Path
import sys

# Allow Streamlit Community Cloud to import the src-layout package directly.
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import streamlit as st

from opportunity_engine.ods import run_ods


st.set_page_config(
    page_title="ODS — Opportunity Development System",
    page_icon="🔎",
    layout="wide",
)

st.title("🔎 ODS — Opportunity Development System")
st.caption("نسخة Alpha: اكتشاف فرص الأزياء، ترتيبها، وبناء Business Blueprint للفرصة الأقوى.")

with st.form("ods-analysis-form"):
    subject = st.text_input("القطاع أو المجال", value="أزياء")
    country = st.text_input("الدولة", value="Norway")
    shortlist_size = st.slider("عدد الفرص النهائية", min_value=1, max_value=10, value=5)
    submitted = st.form_submit_button("ابدأ التحليل", type="primary")

if submitted:
    with st.spinner("ODS يعمل الآن: Discovery → Ranking → BDNA"):
        try:
            result = run_ods(
                subject,
                country=country,
                shortlist_size=shortlist_size,
            )
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
        else:
            st.success(
                f"اكتشف النظام {result.discovered_count} فرص، ثم اختار أفضل "
                f"{len(result.ranked_opportunities)}."
            )

            st.subheader("الفرص المرتبة")
            rows = [
                {
                    "الترتيب": item.rank,
                    "الفرصة": item.opportunity.title,
                    "الفئة": item.opportunity.category,
                    "الدرجة": item.final_score,
                    "الثقة": round(item.opportunity.confidence * 100, 1),
                }
                for item in result.ranked_opportunities
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            blueprint = result.blueprint
            st.subheader("Business Blueprint — الفرصة الأولى")
            st.markdown(f"### {blueprint.opportunity.title}")
            st.write(blueprint.opportunity.description)

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Ranking Score", f"{blueprint.ranking_score:.2f}/100")
                st.markdown("**Business DNA**")
                for value in blueprint.business_dna:
                    st.write(f"• {value}")
                st.markdown("**الأصل الأساسي**")
                st.write(blueprint.core_asset)
                st.markdown("**نماذج الإيراد**")
                for value in blueprint.revenue_models:
                    st.write(f"• {value}")

            with col2:
                st.markdown("**الميزة الدفاعية (Moat)**")
                for value in blueprint.moat:
                    st.write(f"• {value}")
                st.markdown("**مسار النمو**")
                for value in blueprint.growth_path:
                    st.write(f"• {value}")
                st.markdown("**المخاطر**")
                for value in blueprint.risks:
                    st.write(f"• {value}")

            st.markdown("**الفرضيات المطلوب اختبارها لاحقًا**")
            for value in blueprint.hypotheses:
                st.write(f"• {value}")

            with st.expander("سجل تشغيل ODS"):
                for event in result.session.audit_log:
                    st.code(event)
else:
    st.info("أدخل «أزياء» أو Fashion ثم اضغط «ابدأ التحليل». القطاعات الأخرى ستُضاف لاحقًا.")
