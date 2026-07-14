from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from opportunity_engine import Opportunity, evaluate_opportunity


st.set_page_config(page_title="Opportunity Engine", page_icon="📊", layout="centered")
st.title("📊 Opportunity Engine")
st.caption("تحليل محافظ لفرص المزادات وإعادة البيع في النرويج")

with st.form("auction_form"):
    title = st.text_input("اسم الفرصة", value="تجهيزات محل")
    auction_url = st.text_input("رابط المزاد")

    col1, col2 = st.columns(2)
    with col1:
        purchase_price = st.number_input("سعر المزايدة / الشراء (NOK)", min_value=0.0, step=500.0)
        buyer_fee = st.number_input("عمولة المزاد (NOK)", min_value=0.0, step=100.0)
        transport_cost = st.number_input("النقل (NOK)", min_value=0.0, step=100.0)
        dismantling_cost = st.number_input("الفك (NOK)", min_value=0.0, step=100.0)
    with col2:
        storage_cost = st.number_input("التخزين (NOK)", min_value=0.0, step=100.0)
        repair_cost = st.number_input("الإصلاح (NOK)", min_value=0.0, step=100.0)
        other_costs = st.number_input("تكاليف أخرى (NOK)", min_value=0.0, step=100.0)
        expected_resale_value = st.number_input("قيمة إعادة البيع المحافظة (NOK)", min_value=0.0, step=500.0)

    vat_applies_to_bid = st.checkbox("تُضاف MVA على سعر المزايدة", value=False)
    vat_percent = st.number_input("نسبة MVA (%)", min_value=0.0, max_value=100.0, value=25.0, step=1.0)
    risk_score = st.slider("مستوى المخاطرة", min_value=1, max_value=5, value=3)
    target_margin_percent = st.slider("هامش الربح المستهدف (%)", min_value=5, max_value=70, value=30)

    submitted = st.form_submit_button("تحليل الفرصة")

if submitted:
    item = Opportunity(
        title=title.strip() or "فرصة بدون اسم",
        auction_url=auction_url.strip(),
        purchase_price=purchase_price,
        buyer_fee=buyer_fee,
        transport_cost=transport_cost,
        dismantling_cost=dismantling_cost,
        storage_cost=storage_cost,
        repair_cost=repair_cost,
        other_costs=other_costs,
        expected_resale_value=expected_resale_value,
        risk_score=risk_score,
        vat_rate=vat_percent / 100,
        vat_applies_to_bid=vat_applies_to_bid,
    )

    result = evaluate_opportunity(item, target_margin=target_margin_percent / 100)

    st.divider()
    st.subheader(result.classification)
    st.write(result.reason)

    metric1, metric2 = st.columns(2)
    metric1.metric("التكلفة الكلية", f"{result.total_cost:,.0f} NOK")
    metric2.metric("الربح المتوقع", f"{result.expected_profit:,.0f} NOK")

    metric3, metric4 = st.columns(2)
    metric3.metric("العائد المتوقع", f"{result.return_percent:.1f}%")
    metric4.metric("الحد الأقصى للمزايدة", f"{result.maximum_bid:,.0f} NOK")

    st.write(f"**MVA المحسوبة:** {result.vat_cost:,.0f} NOK")
    st.write(f"**إجمالي التكاليف الإضافية:** {result.extra_costs:,.0f} NOK")

    if auction_url:
        st.link_button("فتح إعلان المزاد", auction_url)

st.info("هذه الأداة تساعد على التقييم الأولي ولا تستبدل فحص البضاعة والتحقق من شروط المزاد والتكاليف الفعلية.")
