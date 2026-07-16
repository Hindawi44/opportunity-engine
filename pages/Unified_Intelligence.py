"""Streamlit page for grounded unified ODS intelligence."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import streamlit as st

from opportunity_engine.ods.brreg import BrregClient
from opportunity_engine.ods.confidence import summarize_brreg_entities
from opportunity_engine.ods.runner import run_ods
from opportunity_engine.ods.ssb_market import SSBMarketEvidenceService
from opportunity_engine.ods.ssb_trends import SSBTrendIntelligenceService
from opportunity_engine.ods.unified_intelligence import (
    UnifiedIntelligenceInputs,
    build_unified_intelligence,
    rank_unified_reports,
)

st.set_page_config(page_title="ODS Unified Intelligence", page_icon="🧠", layout="wide")
st.title("🧠 ODS Unified Intelligence — الذكاء الموحد")
st.caption(
    "يوحد الترتيب الداخلي مع الأدلة الرسمية المتاحة. البيانات الناقصة لا تُخترع، "
    "بل تخفض اكتمال الأدلة وقد تمنع توصية PURSUE."
)

with st.form("unified-intelligence-form"):
    subject = st.text_input("القطاع أو المجال", value="أزياء")
    country = st.text_input("الدولة", value="Norway")
    shortlist_size = st.slider("عدد الفرص", min_value=1, max_value=10, value=5)
    include_ssb = st.checkbox("استخدام SSB", value=True)
    include_brreg = st.checkbox("استخدام Brreg", value=True)
    financial_known = st.checkbox("لدي تقييم مالي موثق", value=False)
    financial_score = st.slider("Financial potential", 0, 100, 50, disabled=not financial_known)
    competition_known = st.checkbox("لدي تقييم منافسة موثق", value=False)
    competition_score = st.slider("Competition attractiveness", 0, 100, 50, disabled=not competition_known)
    submitted = st.form_submit_button("احسب ODS Score", type="primary")

if submitted:
    try:
        analysis = run_ods(subject, country=country, shortlist_size=shortlist_size)
    except (RuntimeError, ValueError) as exc:
        st.error(str(exc))
    else:
        evidence = None
        trend = None
        brreg = None
        sources: list[str] = ["ODS internal"]

        if include_ssb:
            try:
                evidence = SSBMarketEvidenceService().load_retail_evidence()
                trend = SSBTrendIntelligenceService().load_retail_trend()
            except (RuntimeError, ValueError) as exc:
                st.warning(f"تعذر تحميل SSB: {exc}")
            else:
                sources.append("SSB")

        if include_brreg:
            query = "klær" if subject.strip().lower() in {"أزياء", "ازياء", "fashion", "apparel"} else subject
            try:
                brreg = summarize_brreg_entities(BrregClient().search_entities(name=query, page_size=20))
            except (RuntimeError, ValueError) as exc:
                st.warning(f"تعذر تحميل Brreg: {exc}")
            else:
                sources.append("Brreg")

        reports = []
        titles: dict[str, str] = {}
        for ranked in analysis.ranked_opportunities:
            candidate = ranked.opportunity
            titles[candidate.opportunity_id] = candidate.title
            report = build_unified_intelligence(
                UnifiedIntelligenceInputs(
                    internal_score=ranked.final_score,
                    candidate_confidence=candidate.confidence * 100.0,
                    evidence_quality=evidence.evidence_score if evidence else None,
                    market_health=trend.market_health_score if trend else None,
                    trend_confidence=trend.confidence if trend else None,
                    brreg_evidence=brreg.evidence_score if brreg else None,
                    financial_score=float(financial_score) if financial_known else None,
                    competition_score=float(competition_score) if competition_known else None,
                    source_names=tuple(sources),
                )
            )
            reports.append((candidate.opportunity_id, report))

        ordered = rank_unified_reports(reports)
        rows = []
        for rank, opportunity_id, report in ordered:
            rows.append(
                {
                    "الترتيب": rank,
                    "الفرصة": titles[opportunity_id],
                    "ODS Score": report.ods_score,
                    "التوصية": report.recommendation.value,
                    "اكتمال الأدلة": report.evidence_completeness,
                    "عدد المصادر": report.source_count,
                }
            )
        st.subheader("أفضل الفرص بالدرجة الموحدة")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if ordered:
            _, top_id, top = ordered[0]
            st.subheader("🏆 الفرصة الأولى")
            st.markdown(f"### {titles[top_id]}")
            c1, c2, c3 = st.columns(3)
            c1.metric("ODS Score", f"{top.ods_score:.1f}/100")
            c2.metric("Recommendation", top.recommendation.value)
            c3.metric("Evidence completeness", f"{top.evidence_completeness:.0f}%")
            st.dataframe(
                pd.DataFrame(top.component_scores, columns=["المكوّن", "الدرجة"]),
                use_container_width=True,
                hide_index=True,
            )
            if top.strengths:
                st.markdown("**نقاط القوة**")
                for item in top.strengths:
                    st.write(f"• {item}")
            if top.weaknesses:
                st.markdown("**نقاط الضعف**")
                for item in top.weaknesses:
                    st.write(f"• {item}")
            if top.missing_evidence:
                st.markdown("**الأدلة الناقصة**")
                for item in top.missing_evidence:
                    st.write(f"• {item}")
            if top.blockers:
                st.markdown("**عوائق PURSUE**")
                for item in top.blockers:
                    st.warning(item)
            st.caption("ODS Score أداة فرز مبنية على الأدلة المتاحة، وليس ضمان ربح أو توصية استثمارية.")
else:
    st.info("أدخل المجال ثم اضغط «احسب ODS Score».")
