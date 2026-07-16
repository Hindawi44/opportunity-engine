"""Streamlit page for conservative opportunity decisions."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from opportunity_engine.ods.evidence_enrichment import enrich_feed
from opportunity_engine.ods.live_feed import FeedItem
from opportunity_engine.ods.opportunity_decision import decide_opportunities

st.set_page_config(page_title="ODS Opportunity Decisions", page_icon="⚖️", layout="wide")
st.title("⚖️ Opportunity Decision Engine — محرك قرار الفرص")
st.caption(
    "يصدر GO فقط عند وجود أدلة قوية ومتعددة المصادر تشمل إعلان أصول، أسعار سوق، "
    "وتكاليف موثقة. حالة Brreg وحدها لا تكفي لاتخاذ قرار شراء."
)

feed_path = ROOT / "data" / "live_opportunity_feed.json"
if not feed_path.exists():
    st.info("شغّل صفحة Live Opportunity Feed أولًا، ثم صفحة Evidence Enrichment.")
else:
    try:
        payload = json.loads(feed_path.read_text(encoding="utf-8"))
        records = payload.get("records", {})
        items = tuple(
            FeedItem(
                opportunity_id=str(record["opportunity_id"]),
                title=str(record["title"]),
                category=str(record["category"]),
                description=str(record["description"]),
                source=str(record["source"]),
                discovered_at=str(record["discovered_at"]),
                last_seen_at=str(record["last_seen_at"]),
                times_seen=int(record["times_seen"]),
                score=float(record["score"]) if record.get("score") is not None else None,
                status=str(record["status"]),
                evidence=tuple(str(value) for value in record.get("evidence", ())),
            )
            for record in records.values()
            if bool(record.get("active", True))
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        st.error(f"تعذر قراءة التغذية الحية: {exc}")
    else:
        reports = decide_opportunities(enrich_feed(items))
        if not reports:
            st.info("لا توجد فرص نشطة لاتخاذ قرار بشأنها.")
        else:
            go_count = sum(report.decision.value == "GO" for report in reports)
            watch_count = sum(report.decision.value == "WATCH" for report in reports)
            reject_count = sum(report.decision.value == "REJECT" for report in reports)
            a, b, c = st.columns(3)
            a.metric("GO", go_count)
            b.metric("WATCH", watch_count)
            c.metric("REJECT", reject_count)

            rows = [
                {
                    "الفرصة": report.title,
                    "القرار": report.decision.value,
                    "درجة القرار": report.decision_score,
                    "درجة الأدلة": report.evidence_score,
                    "اكتمال الأدلة %": report.evidence_completeness,
                    "المصادر المستقلة": report.independent_sources,
                }
                for report in reports
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            st.subheader("تفاصيل القرار")
            for report in reports:
                with st.expander(f"{report.decision.value} — {report.title}"):
                    x, y, z = st.columns(3)
                    x.metric("Decision Score", f"{report.decision_score:.1f}/100")
                    y.metric("Evidence", f"{report.evidence_score:.1f}/100")
                    z.metric("Completeness", f"{report.evidence_completeness:.1f}%")
                    st.markdown("**أسباب القرار**")
                    for reason in report.reasons:
                        st.write(f"• {reason}")
                    if report.blockers:
                        st.markdown("**العوائق**")
                        for blocker in report.blockers:
                            st.warning(blocker)
                    st.markdown("**الخطوات التالية**")
                    for action in report.next_actions:
                        st.write(f"• {action}")

st.caption("هذه أداة فرز وتحكم بالمخاطر، وليست ضمان ربح أو توصية استثمارية ملزمة.")
