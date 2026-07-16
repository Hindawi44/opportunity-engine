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
    BrregClient,
    ExecutiveWorkflowInputs,
    FinancialInputs,
    SSBMarketEvidenceService,
    SSBTrendIntelligenceService,
    build_decision_from_analysis,
    build_financial_report,
    calculate_opportunity_confidence,
    calculate_ssb_adjustment,
    calculate_trend_adjustment,
    run_ods,
    summarize_brreg_entities,
    track_workflow_opportunities,
)

st.set_page_config(page_title="ODS — Opportunity Development System", page_icon="🔎", layout="wide")
st.title("🔎 ODS — Opportunity Development System")
st.caption("نسخة Alpha: اكتشاف الفرص، دمج الأدلة الرسمية، تحليل الثقة، الذاكرة، النموذج المالي، والقرار التنفيذي.")

with st.form("ods-analysis-form"):
    subject = st.text_input("القطاع أو المجال", value="أزياء")
    country = st.text_input("الدولة", value="Norway")
    shortlist_size = st.slider("عدد الفرص النهائية", min_value=1, max_value=10, value=5)
    include_ssb = st.checkbox("إضافة دليل واتجاه سوق حي من SSB", value=True)
    include_brreg = st.checkbox("إضافة دليل هيكل الشركات من Brreg", value=True)
    submitted = st.form_submit_button("ابدأ التحليل", type="primary")

if submitted:
    with st.spinner("ODS يعمل الآن: Discovery → Ranking → Evidence → Confidence → Memory → Financial → Executive Decision → BDNA → Validation"):
        try:
            result = run_ods(subject, country=country, shortlist_size=shortlist_size)
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
        else:
            st.success(f"اكتشف النظام {result.discovered_count} فرص، ثم اختار أفضل {len(result.ranked_opportunities)}.")
            evidence = None
            trend = None
            brreg_summary = None

            if include_ssb:
                st.subheader("Live Intelligence from SSB — ذكاء السوق الرسمي")
                try:
                    evidence = SSBMarketEvidenceService().load_retail_evidence()
                    trend = SSBTrendIntelligenceService().load_retail_trend()
                except (ValueError, RuntimeError) as exc:
                    st.warning(f"تعذر تحميل أو تحليل SSB الآن، واستمر التحليل الداخلي: {exc}")
                else:
                    st.markdown(f"### {evidence.title}")
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Evidence Score", f"{evidence.evidence_score:.0f}/100")
                    col_b.metric("Market Health", f"{trend.market_health_score:.0f}/100")
                    col_c.metric("الاتجاه", trend.direction)
                    latest_text = "غير متاح" if trend.latest_change_pct is None else f"{trend.latest_change_pct:+.2f}%"
                    st.write(f"**آخر تغير:** {latest_text}")
                    for line in trend.explanation:
                        st.write(f"• {line}")
                    st.link_button("فتح جدول SSB الرسمي", evidence.source_url)

            if include_brreg:
                st.subheader("Business Structure from Brreg — هيكل الشركات الرسمي")
                brreg_query = "klær" if subject.strip().lower() in {"أزياء", "ازياء", "fashion", "apparel"} else subject
                try:
                    entities = BrregClient().search_entities(name=brreg_query, page_size=20)
                    brreg_summary = summarize_brreg_entities(entities)
                except (ValueError, RuntimeError) as exc:
                    st.warning(f"تعذر تحميل Brreg الآن، واستمر التحليل دون توقف: {exc}")
                else:
                    col_d, col_e, col_f = st.columns(3)
                    col_d.metric("السجلات المسترجعة", brreg_summary.entity_count)
                    col_e.metric("إفلاس/تصفية", brreg_summary.bankrupt_count + brreg_summary.liquidation_count)
                    col_f.metric("Brreg Evidence", f"{brreg_summary.evidence_score:.0f}/100")
                    if brreg_summary.municipalities:
                        st.write("**البلديات الظاهرة في العينة:** " + "، ".join(brreg_summary.municipalities))
                    st.caption("هذه عينة بحث محدودة وليست تعدادًا كاملًا للسوق.")

            st.subheader("الفرص المرتبة ودرجة الثقة")
            rows = []
            confidence_by_id = {}
            for item in result.ranked_opportunities:
                score_after_evidence = item.final_score
                if evidence is not None:
                    score_after_evidence = calculate_ssb_adjustment(
                        base_score=item.final_score,
                        category=item.opportunity.category,
                        evidence_score=evidence.evidence_score,
                    ).final_score
                if trend is not None:
                    supported_score = calculate_trend_adjustment(
                        base_score=score_after_evidence,
                        category=item.opportunity.category,
                        signal=trend,
                    ).final_score
                else:
                    supported_score = score_after_evidence
                confidence = calculate_opportunity_confidence(
                    internal_score=supported_score,
                    candidate_confidence=item.opportunity.confidence,
                    validation_readiness=result.validation.readiness_score,
                    ssb_evidence_score=evidence.evidence_score if evidence else None,
                    market_health_score=trend.market_health_score if trend else None,
                    trend_confidence=trend.confidence if trend else None,
                    brreg=brreg_summary,
                )
                confidence_by_id[item.opportunity.opportunity_id] = confidence
                rows.append({
                    "الترتيب الداخلي": item.rank,
                    "الفرصة": item.opportunity.title,
                    "الفئة": item.opportunity.category,
                    "الدرجة الأساسية": item.final_score,
                    "الدرجة المدعومة": supported_score,
                    "الثقة النهائية": confidence.final_score,
                    "القرار": confidence.decision_band,
                })
            rows.sort(key=lambda row: (-row["الثقة النهائية"], row["الترتيب الداخلي"]))
            for index, row in enumerate(rows, start=1):
                row["الترتيب النهائي"] = index
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            st.subheader("Opportunity Memory — ذاكرة الفرص")
            memory_path = ROOT / "data" / "opportunity_history.json"
            try:
                memory = track_workflow_opportunities(
                    (item.opportunity for item in result.ranked_opportunities),
                    storage_path=memory_path,
                    country=country,
                )
            except (OSError, RuntimeError, ValueError) as exc:
                st.warning(f"تعذر تحديث ذاكرة الفرص في هذا التشغيل: {exc}")
            else:
                mem_a, mem_b, mem_c, mem_d = st.columns(4)
                mem_a.metric("NEW", memory.new_count)
                mem_b.metric("UPDATED", memory.updated_count)
                mem_c.metric("UNCHANGED", memory.unchanged_count)
                mem_d.metric("REMOVED", memory.removed_count)
                history_rows = [{
                    "الفرصة": record.title,
                    "الفئة": record.category,
                    "أول ظهور": record.first_seen,
                    "آخر ظهور": record.last_seen,
                    "مرات الظهور": record.times_seen,
                    "الثقة": round(record.confidence * 100, 1),
                    "نشطة": record.active,
                } for record in sorted(memory.records, key=lambda item: item.last_seen, reverse=True)[:30]]
                if history_rows:
                    st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)
                st.caption("التخزين الحالي JSON محلي. على الاستضافة السحابية قد لا يكون دائمًا بين عمليات إعادة تشغيل الخادم.")

            blueprint = result.blueprint
            top_confidence = confidence_by_id[blueprint.opportunity.opportunity_id]
            st.subheader("Opportunity Confidence — تفسير القرار")
            col_g, col_h = st.columns(2)
            col_g.metric("Final Confidence", f"{top_confidence.final_score:.1f}/100")
            col_h.metric("Decision Band", top_confidence.decision_band)
            if top_confidence.strengths:
                st.markdown("**نقاط القوة**")
                for value in top_confidence.strengths:
                    st.write(f"• {value}")
            if top_confidence.weaknesses:
                st.markdown("**نقاط الضعف**")
                for value in top_confidence.weaknesses:
                    st.write(f"• {value}")
            if top_confidence.missing_evidence:
                st.markdown("**الأدلة الناقصة**")
                for value in top_confidence.missing_evidence:
                    st.write(f"• {value}")

            st.subheader("Financial Intelligence — النموذج المالي الافتراضي")
            st.caption("أدخل افتراضاتك أنت. النظام لا يخترع الإيرادات أو التكاليف، والنتائج ليست توقع ربح.")
            financial = None
            with st.expander("إدخال الافتراضات المالية", expanded=True):
                f1, f2, f3 = st.columns(3)
                startup_cost = f1.number_input("تكلفة البداية (NOK)", min_value=0.0, value=100000.0, step=10000.0)
                monthly_fixed = f2.number_input("التكاليف الثابتة الشهرية", min_value=0.0, value=20000.0, step=1000.0)
                working_months = f3.number_input("احتياطي رأس المال العامل/أشهر", min_value=0.0, value=3.0, step=1.0)
                f4, f5, f6 = st.columns(3)
                unit_price = f4.number_input("سعر الوحدة أو العملية", min_value=1.0, value=1000.0, step=100.0)
                unit_variable = f5.number_input("التكلفة المتغيرة للوحدة", min_value=0.0, value=400.0, step=50.0)
                monthly_units = f6.number_input("عدد الوحدات/العمليات شهريًا", min_value=0.0, value=50.0, step=5.0)
                try:
                    financial = build_financial_report(FinancialInputs(
                        startup_cost=startup_cost,
                        monthly_fixed_cost=monthly_fixed,
                        unit_price=unit_price,
                        unit_variable_cost=unit_variable,
                        monthly_units=monthly_units,
                        working_capital_months=working_months,
                    ))
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("رأس المال المطلوب", f"{financial.required_capital:,.0f} NOK")
                    m2.metric("نقطة التعادل/وحدة شهريًا", f"{financial.break_even_units_monthly:,.1f}")
                    m3.metric("هامش المساهمة", f"{financial.contribution_margin_pct:.1f}%")
                    scenario_rows = [{
                        "السيناريو": scenario.name,
                        "الوحدات الشهرية": scenario.monthly_units,
                        "الإيراد الشهري": scenario.monthly_revenue,
                        "الربح التشغيلي الشهري": scenario.monthly_operating_profit,
                        "الربح التشغيلي السنوي": scenario.annual_operating_profit,
                        "استرداد رأس المال/شهر": scenario.payback_months if scenario.payback_months is not None else "لا يوجد",
                    } for scenario in financial.scenarios]
                    st.dataframe(pd.DataFrame(scenario_rows), use_container_width=True, hide_index=True)
                    for warning in financial.warnings:
                        st.warning(warning)

            executive = build_decision_from_analysis(
                ExecutiveWorkflowInputs(
                    analysis=result,
                    financial_report=financial,
                    evidence_quality=evidence.evidence_score if evidence else None,
                    market_health=trend.market_health_score if trend else None,
                    trend_confidence=trend.confidence if trend else None,
                    brreg=brreg_summary,
                )
            )
            st.subheader("🏛️ Executive Decision — القرار التنفيذي")
            decision_col, score_col = st.columns(2)
            decision_col.metric("Decision", executive.decision.value)
            score_col.metric("Executive Score", f"{executive.score:.1f}/100")
            st.dataframe(
                pd.DataFrame(executive.component_scores, columns=["المكوّن", "الدرجة"]),
                use_container_width=True,
                hide_index=True,
            )
            st.markdown("**لماذا صدر هذا القرار؟**")
            for reason in executive.reasons:
                st.write(f"• {reason}")
            if executive.blockers:
                st.markdown("**العوائق قبل الالتزام برأس المال**")
                for blocker in executive.blockers:
                    st.warning(blocker)
            if executive.missing_evidence:
                st.markdown("**الأدلة الناقصة**")
                for missing_item in executive.missing_evidence:
                    st.write(f"• {missing_item}")
            plan_7, plan_30, plan_90 = st.columns(3)
            with plan_7:
                st.markdown("### أول 7 أيام")
                for action in executive.first_7_days:
                    st.write(f"• {action}")
            with plan_30:
                st.markdown("### أول 30 يومًا")
                for action in executive.first_30_days:
                    st.write(f"• {action}")
            with plan_90:
                st.markdown("### أول 90 يومًا")
                for action in executive.first_90_days:
                    st.write(f"• {action}")
            st.caption("القرار أداة فرز وتحكم بالمخاطر، وليس ضمان ربح أو نصيحة استثمارية.")

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
