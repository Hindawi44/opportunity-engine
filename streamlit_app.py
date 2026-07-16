"""User-facing Streamlit interface for ODS alpha."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import streamlit as st

from opportunity_engine.ods import (
    SSBMarketEvidenceService,
    SSBTrendIntelligenceService,
    calculate_ssb_adjustment,
    calculate_trend_adjustment,
    run_ods,
)

st.set_page_config(page_title="ODS — Opportunity Development System", page_icon="🔎", layout="wide")
st.title("🔎 ODS — Opportunity Development System")
st.caption("نسخة Alpha: اكتشاف الفرص، ترتيبها، بناء Business Blueprint، وخطة تحقق عملية.")

with st.form("ods-analysis-form"):
    subject = st.text_input("القطاع أو المجال", value="أزياء")
    country = st.text_input("الدولة", value="Norway")
    shortlist_size = st.slider("عدد الفرص النهائية", min_value=1, max_value=10, value=5)
    include_ssb = st.checkbox("إضافة دليل واتجاه سوق حي من SSB", value=True)
    submitted = st.form_submit_button("ابدأ التحليل", type="primary")

if submitted:
    with st.spinner("ODS يعمل الآن: Discovery → Ranking → BDNA → Validation"):
        try:
            result = run_ods(subject, country=country, shortlist_size=shortlist_size)
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
        else:
            st.success(f"اكتشف النظام {result.discovered_count} فرص، ثم اختار أفضل {len(result.ranked_opportunities)}.")
            evidence = None
            trend = None
            if include_ssb:
                st.subheader("Live Intelligence from SSB — ذكاء السوق الرسمي")
                try:
                    evidence = SSBMarketEvidenceService().load_retail_evidence()
                except (ValueError, RuntimeError) as exc:
                    st.warning(f"تعذر تحميل دليل SSB الآن، واستمر التحليل الداخلي دون توقف: {exc}")
                else:
                    st.markdown(f"### {evidence.title}")
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Evidence Score", f"{evidence.evidence_score:.0f}/100")
                    col_b.metric("آخر فترة", evidence.last_period or "غير محدد")
                    col_c.metric("عدد القيم", evidence.value_count)
                    st.write(f"**الفترة المتاحة:** {evidence.first_period or '?'} → {evidence.last_period or '?'}")
                    if evidence.variables:
                        st.write("**المتغيرات:** " + "، ".join(evidence.variables))
                    for line in evidence.interpretation:
                        st.write(f"• {line}")
                    st.link_button("فتح جدول SSB الرسمي", evidence.source_url)

                try:
                    trend = SSBTrendIntelligenceService().load_retail_trend()
                except (ValueError, RuntimeError) as exc:
                    st.warning(f"تعذر استخراج اتجاه SSB الآن: {exc}")
                else:
                    st.markdown("#### SSB Trend Intelligence — تحليل الاتجاه")
                    col_d, col_e, col_f = st.columns(3)
                    col_d.metric("Market Health", f"{trend.market_health_score:.0f}/100")
                    col_e.metric("الاتجاه", trend.direction)
                    latest_text = "غير متاح" if trend.latest_change_pct is None else f"{trend.latest_change_pct:+.2f}%"
                    col_f.metric("آخر تغير", latest_text)
                    if trend.cagr_pct is not None:
                        st.write(f"**النمو السنوي المركب التقريبي:** {trend.cagr_pct:+.2f}%")
                    if trend.periods:
                        st.write(f"**السلسلة المستخدمة:** {trend.periods[0]} → {trend.periods[-1]} ({len(trend.periods)} فترات)")
                    for line in trend.explanation:
                        st.write(f"• {line}")
                    st.caption("التحليل وصفي ومحافظ؛ لا يمثل توقع ربح أو ضمانًا لاتجاه المستقبل.")

            st.subheader("الفرص المرتبة")
            rows = []
            for item in result.ranked_opportunities:
                evidence_adjustment = None
                trend_adjustment = None
                score_after_evidence = item.final_score
                if evidence is not None:
                    evidence_adjustment = calculate_ssb_adjustment(
                        base_score=item.final_score,
                        category=item.opportunity.category,
                        evidence_score=evidence.evidence_score,
                    )
                    score_after_evidence = evidence_adjustment.final_score
                if trend is not None:
                    trend_adjustment = calculate_trend_adjustment(
                        base_score=score_after_evidence,
                        category=item.opportunity.category,
                        signal=trend,
                    )
                final_score = trend_adjustment.final_score if trend_adjustment else score_after_evidence
                rows.append({
                    "الترتيب الداخلي": item.rank,
                    "الفرصة": item.opportunity.title,
                    "الفئة": item.opportunity.category,
                    "الدرجة الأساسية": item.final_score,
                    "جودة دليل SSB": evidence_adjustment.adjustment if evidence_adjustment else 0.0,
                    "تعديل الاتجاه": trend_adjustment.adjustment if trend_adjustment else 0.0,
                    "الدرجة النهائية المدعومة": final_score,
                    "الثقة": round(item.opportunity.confidence * 100, 1),
                })
            rows.sort(key=lambda row: (-row["الدرجة النهائية المدعومة"], row["الترتيب الداخلي"]))
            for index, row in enumerate(rows, start=1):
                row["الترتيب بالدليل"] = index
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            if evidence is not None or trend is not None:
                st.caption("تعديلات SSB محدودة وشفافة. Business Blueprint أدناه ما زال مبنيًا على الترتيب الداخلي الأصلي حتى تُدمج البيانات الحية داخل Workflow نفسه.")

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

            st.markdown("**الفرضيات المطلوب اختبارها**")
            for value in blueprint.hypotheses:
                st.write(f"• {value}")

            validation = result.validation
            st.subheader("Validation Plan — خطة التحقق")
            st.metric("Validation Readiness", f"{validation.readiness_score:.0f}/100")
            st.markdown("**الفرضية الأخطر**")
            st.write(validation.highest_risk_assumption)
            st.markdown(f"**القرار الحالي:** {validation.recommended_decision}")
            for index, experiment in enumerate(validation.experiments, start=1):
                with st.expander(f"التجربة {index}: {experiment.hypothesis}", expanded=index == 1):
                    st.write(f"**الطريقة:** {experiment.method}")
                    st.write(f"**العينة المستهدفة:** {experiment.target_sample}")
                    st.write(f"**المدة:** {experiment.duration_days} أيام")
                    st.write(f"**معيار النجاح:** {experiment.success_criteria}")
                    st.write(f"**معيار الفشل:** {experiment.failure_criteria}")
                    st.write("**المؤشرات المطلوبة:**")
                    for metric in experiment.required_metrics:
                        st.write(f"• {metric}")

            with st.expander("سجل تشغيل ODS"):
                for event in result.session.audit_log:
                    st.code(event)
else:
    st.info("أدخل «أزياء» أو Fashion ثم اضغط «ابدأ التحليل». القطاعات الأخرى ستُضاف لاحقًا.")
