import streamlit as st
from engine import daily_scan, market_regime
from db import init_db, save_scan

st.set_page_config(page_title="NSE Swing AI Pro", page_icon="📈", layout="wide")
init_db()

st.title("📈 NSE Swing AI Pro")
st.caption("AI-assisted NSE swing-trading research dashboard — decision support, not guaranteed returns.")

with st.sidebar:
    capital = st.number_input("Trading capital (₹)", min_value=10000.0, value=200000.0, step=10000.0)
    risk_pct = st.number_input("Risk per trade (%)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
    min_score = st.slider("Minimum model score", 50, 95, 75)
    min_rr = st.slider("Minimum R:R", 1.0, 5.0, 2.0, 0.1)

reg = market_regime()
c1,c2,c3 = st.columns(3)
c1.metric("Market regime", reg["label"])
c2.metric("Regime score", f'{reg["score"]}/100')
c3.metric("Model threshold", f"{min_score}/100")

if st.button("🔎 Run Daily Scan", type="primary"):
    with st.spinner("Scanning the NSE starter universe..."):
        result = daily_scan(capital, risk_pct, min_score, min_rr)
        st.session_state["scan"] = result
        save_scan(result)

scan = st.session_state.get("scan")
if scan:
    st.subheader("🏆 Today's Top 3")
    for i, x in enumerate(scan["top3"], 1):
        with st.container(border=True):
            st.markdown(f"### #{i} — {x['symbol']} · {x['setup']}")
            cols = st.columns(7)
            cols[0].metric("Score", x["score"])
            cols[1].metric("Entry", f"₹{x['entry']:.2f}")
            cols[2].metric("Stop", f"₹{x['stop']:.2f}")
            cols[3].metric("Target 1", f"₹{x['target1']:.2f}")
            cols[4].metric("Target 2", f"₹{x['target2']:.2f}")
            cols[5].metric("R:R", f"{x['rr']:.2f}")
            cols[6].metric("Qty", x["qty"])
            st.write(x["thesis"])
            st.caption("Risk:", x["risk"])

    st.download_button(
        "⬇️ Download today's scan CSV",
        data=scan["csv"],
        file_name="nse_swing_daily_scan.csv",
        mime="text/csv"
    )
else:
    st.info("Click **Run Daily Scan** to generate today's ranked setups.")
