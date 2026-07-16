"""Streamlit page for conservative evidence enrichment of the live feed."""
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

st.set_page_config(page_title="ODS Evidence Enrichment", page_icon="🧾", layout="wide")
st.title("🧾 Opportunity Evidence Enrichment — إثراء أدلة الفرص")
st.caption(
    "يقيّم فقط الأدلة الموجودة فعليًا في التغذية الحية. لا يفترض وجود أصول للبيع، "
    "ولا يحسب ربحًا دون أسعار وتكاليف موثقة."
)

feed_path = ROOT / "data" / "live_opportunity_feed.json"
if not feed_path.exists():
    st.info("شغّل صفحة Live Opportunity Feed أولًا لإنشاء بيانات التغذية.")
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
        enriched = enrich_feed(items)
        if not enriched:
            st.info("لا توجد فرص نشطة في التغذية الحالية.")
        else:
            rows = [
                {
                    "الفرصة": value.item.title,
                    "حالة التغذية": value.item.status,
                    "درجة الأدلة": value.evidence_score,
                    "اكتمال الأدلة %": value.completeness,
                    "المصادر المستقلة": value.independent_sources,
                    "التقييم": value.band.value,
                    "الأدلة الناقصة": " | ".join(value.missing_evidence),
                }
                for value in enriched
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            st.subheader("تفاصيل كل فرصة")
            for value in enriched:
                with st.expander(f"{value.band.value} — {value.item.title}"):
                    a, b, c = st.columns(3)
                    a.metric("Evidence Score", f"{value.evidence_score:.0f}/100")
                    b.metric("Completeness", f"{value.completeness:.0f}%")
                    c.metric("Independent Sources", value.independent_sources)
                    if value.facts:
                        st.markdown("**الأدلة المسجلة**")
                        for fact in value.facts:
                            st.write(f"• {fact.source} — {fact.kind}: {fact.value}")
                    if value.missing_evidence:
                        st.markdown("**الأدلة الناقصة**")
                        for missing in value.missing_evidence:
                            st.write(f"• {missing}")
                    if value.blockers:
                        st.markdown("**عوائق القرار**")
                        for blocker in value.blockers:
                            st.warning(blocker)

st.caption("هذه الصفحة أداة ضبط جودة للأدلة، وليست توصية شراء أو ضمان ربح.")
