"""Streamlit page for running the bounded live Brreg opportunity collector."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import streamlit as st

from opportunity_engine.ods import (
    BrregOpportunityCollector,
    BrregSearchSlice,
    OpportunityChangeType,
)

st.set_page_config(page_title="ODS Live Collector", page_icon="📡", layout="wide")
st.title("📡 ODS Live Collector — جامع الفرص الحية")
st.caption(
    "يشغّل عمليات بحث محدودة في Brønnøysund، ويعرض فقط السجلات التي تحمل علم إفلاس أو تصفية رسميًا. "
    "النتائج إشارات للتحقق وليست إثباتًا بأن أصول الشركة معروضة للبيع."
)


def _clean_optional(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def _parse_subjects(raw: str) -> tuple[str, ...]:
    values = []
    seen = set()
    for line in raw.replace(",", "\n").splitlines():
        value = line.strip()
        key = value.casefold()
        if value and key not in seen:
            values.append(value)
            seen.add(key)
    if not values:
        raise ValueError("أدخل عبارة بحث واحدة على الأقل")
    return tuple(values)


with st.form("live-collector-form"):
    subjects_text = st.text_area(
        "عبارات البحث — عبارة في كل سطر",
        value="klær\nbutikk\ninteriør",
        help="كل عبارة تشكل شريحة بحث مستقلة ومحدودة في سجل Brønnøysund.",
        height=120,
    )
    left, middle, right = st.columns(3)
    municipality = left.text_input("البلدية (اختياري)", value="")
    industry_code = middle.text_input("كود النشاط NACE (اختياري)", value="")
    page_size = right.slider("حجم عينة كل شريحة", min_value=1, max_value=100, value=50)
    shortlist_size = st.slider("عدد النتائج المرتبة", min_value=1, max_value=50, value=20)
    submitted = st.form_submit_button("ابدأ الفحص الحي", type="primary")

if submitted:
    try:
        subjects = _parse_subjects(subjects_text)
        slices = tuple(
            BrregSearchSlice(
                subject=subject,
                municipality=_clean_optional(municipality),
                industry_code=_clean_optional(industry_code),
                page_size=page_size,
            )
            for subject in subjects
        )
        memory_path = ROOT / "data" / "brreg_opportunity_history.json"
        collector = BrregOpportunityCollector(
            memory_path,
            shortlist_size=shortlist_size,
        )
        with st.spinner("يجري الآن فحص Brreg وتجميع النتائج وإزالة التكرار..."):
            result = collector.collect(slices)
    except (OSError, RuntimeError, ValueError) as exc:
        st.error(f"تعذر إكمال الفحص: {exc}")
    else:
        st.success("اكتمل الفحص الحي.")
        a, b, c, d, e = st.columns(5)
        a.metric("الشرائح المطلوبة", result.slices_requested)
        b.metric("الشرائح المكتملة", result.slices_completed)
        c.metric("الشرائح الفاشلة", result.slices_failed)
        d.metric("السجلات المفحوصة", len(result.snapshot.documents))
        e.metric("الفرص الفريدة", len(result.snapshot.opportunities))

        if result.errors:
            st.subheader("أخطاء الشرائح")
            for error in result.errors:
                st.warning(error)

        st.subheader("حالة الذاكرة")
        new_count = sum(
            change.change_type is OpportunityChangeType.NEW
            for change in result.memory.changes
        )
        updated_count = sum(
            change.change_type is OpportunityChangeType.UPDATED
            for change in result.memory.changes
        )
        unchanged_count = sum(
            change.change_type is OpportunityChangeType.UNCHANGED
            for change in result.memory.changes
        )
        removed_count = sum(
            change.change_type is OpportunityChangeType.REMOVED
            for change in result.memory.changes
        )
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("NEW", new_count)
        m2.metric("UPDATED", updated_count)
        m3.metric("UNCHANGED", unchanged_count)
        m4.metric("REMOVED", removed_count)

        if not result.ranked_opportunities:
            st.info(
                "لم تحمل العينة الحالية أي علم إفلاس أو تصفية رسمي. "
                "هذا لا يعني عدم وجود حالات أخرى خارج عينة البحث."
            )
        else:
            changes_by_id = {
                change.opportunity_id: change.change_type.value
                for change in result.memory.changes
            }
            rows = []
            for ranked in result.ranked_opportunities:
                candidate = ranked.opportunity
                official_url = next(
                    (item for item in candidate.evidence if item.startswith("https://")),
                    None,
                )
                status = next(
                    (
                        item.split(":", 1)[1]
                        for item in candidate.evidence
                        if item.startswith("official-status:")
                    ),
                    "unknown",
                )
                orgnr = next(
                    (
                        item.split(":", 1)[1]
                        for item in candidate.evidence
                        if item.startswith("organisation-number:")
                    ),
                    "",
                )
                municipality_value = next(
                    (
                        item.split(":", 1)[1]
                        for item in candidate.evidence
                        if item.startswith("municipality:")
                    ),
                    "",
                )
                rows.append(
                    {
                        "الترتيب": ranked.rank,
                        "الشركة/الإشارة": candidate.title,
                        "الحالة الرسمية": status,
                        "رقم المؤسسة": orgnr,
                        "البلدية": municipality_value,
                        "درجة الترتيب": ranked.final_score,
                        "تغيير الذاكرة": changes_by_id.get(candidate.opportunity_id, ""),
                        "الرابط الرسمي": official_url,
                    }
                )
            st.subheader("الفرص المرتبة")
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "الرابط الرسمي": st.column_config.LinkColumn("الرابط الرسمي")
                },
            )

            st.subheader("القرار التنفيذي المحافظ")
            if result.decision is None:
                st.info("لا يوجد قرار لأن قائمة الفرص فارغة.")
            else:
                decision_col, score_col = st.columns(2)
                decision_col.metric("Decision", result.decision.decision.value)
                score_col.metric("Executive Score", f"{result.decision.score:.1f}/100")
                if result.decision.reasons:
                    st.markdown("**أسباب القرار**")
                    for reason in result.decision.reasons:
                        st.write(f"• {reason}")
                if result.decision.blockers:
                    st.markdown("**العوائق قبل الالتزام المالي**")
                    for blocker in result.decision.blockers:
                        st.write(f"• {blocker}")

        st.caption(
            "Brreg Collector يجمع شرائح بحث محدودة فقط. لا يفترض توفر مخزون أو معدات للبيع، "
            "ولا يصدر تقدير ربح دون أدلة سعرية ومالية مستقلة."
        )
