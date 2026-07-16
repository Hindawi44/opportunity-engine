"""Streamlit page for the ODS executive decision engine."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from opportunity_engine.ods import (  # noqa: E402
    DecisionInputs,
    FinancialInputs,
    build_executive_decision,
    build_financial_report,
)

st.set_page_config(page_title="ODS Executive Decision", page_icon="🏛️", layout="wide")
st.title("🏛️ Executive Decision Engine")
st.caption("قرار محافظ ومفسر مبني فقط على الدرجات والأرقام التي تدخلها أنت أو تنتجها محركات ODS.")

c1, c2, c3, c4 = st.columns(4)
confidence = c1.number_input("Opportunity Confidence", 0.0, 100.0, 75.0)
validation = c2.number_input("Validation Readiness", 0.0, 100.0, 70.0)
evidence = c3.number_input("Evidence Quality", 0.0, 100.0, 80.0)
market = c4.number_input("Market Health", 0.0, 100.0, 70.0)

st.subheader("Financial assumptions")
f1, f2, f3 = st.columns(3)
startup = f1.number_input("Startup cost (NOK)", min_value=0.0, value=100000.0, step=10000.0)
fixed = f2.number_input("Monthly fixed cost", min_value=0.0, value=20000.0, step=1000.0)
working = f3.number_input("Working-capital months", min_value=0.0, value=3.0, step=1.0)
f4, f5, f6 = st.columns(3)
price = f4.number_input("Unit price", min_value=1.0, value=1000.0, step=100.0)
variable = f5.number_input("Variable cost/unit", min_value=0.0, value=400.0, step=50.0)
units = f6.number_input("Monthly units", min_value=0.0, value=50.0, step=5.0)

if st.button("احسب القرار التنفيذي", type="primary"):
    try:
        financial = build_financial_report(
            FinancialInputs(
                startup_cost=startup,
                monthly_fixed_cost=fixed,
                unit_price=price,
                unit_variable_cost=variable,
                monthly_units=units,
                working_capital_months=working,
            )
        )
        report = build_executive_decision(
            DecisionInputs(
                opportunity_confidence=confidence,
                validation_readiness=validation,
                evidence_quality=evidence,
                market_health=market,
                financial_report=financial,
            )
        )
    except ValueError as exc:
        st.error(str(exc))
    else:
        d1, d2 = st.columns(2)
        d1.metric("Decision", report.decision.value)
        d2.metric("Executive Score", f"{report.score:.1f}/100")

        st.subheader("Decision breakdown")
        st.dataframe(
            pd.DataFrame(report.component_scores, columns=["Component", "Score"]),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("**لماذا؟**")
        for reason in report.reasons:
            st.write(f"• {reason}")

        if report.blockers:
            st.markdown("**العوائق قبل الاستثمار**")
            for blocker in report.blockers:
                st.warning(blocker)

        if report.missing_evidence:
            st.markdown("**الأدلة الناقصة**")
            for item in report.missing_evidence:
                st.write(f"• {item}")

        p1, p2, p3 = st.columns(3)
        with p1:
            st.markdown("### أول 7 أيام")
            for item in report.first_7_days:
                st.write(f"• {item}")
        with p2:
            st.markdown("### أول 30 يومًا")
            for item in report.first_30_days:
                st.write(f"• {item}")
        with p3:
            st.markdown("### أول 90 يومًا")
            for item in report.first_90_days:
                st.write(f"• {item}")

        st.caption("القرار أداة فرز وتحكم بالمخاطر، وليس ضمان ربح أو نصيحة استثمارية.")
