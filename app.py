import streamlit as st
from engine import daily_scan, market_regime
from db import init_db, save_scan
st.set_page_config(page_title="NSE Swing AI Pro",page_icon="📈",layout="wide"); init_db()
st.title("📈 NSE Swing AI Pro"); st.caption("AI-assisted NSE swing-trading research dashboard — decision support, not guaranteed returns.")
with st.sidebar:
    capital=st.number_input("Trading capital (₹)",min_value=10000.0,value=200000.0,step=10000.0)
    risk_pct=st.number_input("Risk per trade (%)",min_value=.1,max_value=5.0,value=1.0,step=.1)
    min_score=st.slider("Minimum model score",50,95,75)
    min_rr=st.slider("Minimum R:R (Target 2)",1.0,5.0,2.0,.1)
reg=market_regime(); c1,c2,c3=st.columns(3); c1.metric("Market regime",reg["label"]); c2.metric("Regime score",f'{reg["score"]}/100'); c3.metric("Model threshold",f"{min_score}/100")
if st.button("🔎 Run Daily Scan",type="primary"):
    with st.spinner("Scanning and calculating the 100-point model..."):
        st.session_state["scan"]=daily_scan(capital,risk_pct,min_score,min_rr); save_scan(st.session_state["scan"])
scan=st.session_state.get("scan")
if scan:
    st.caption("100-point model: Technical 35 + Momentum 15 + Fundamentals 20 + Catalyst 10 + Market/Relative Strength 10.")
    if scan["top3"]:
        st.subheader("🏆 Today's Top Qualified Setups")
        for i,x in enumerate(scan["top3"],1):
            with st.container(border=True):
                st.markdown(f"### #{i} — {x['symbol']} · 🟢 QUALIFIED · {x['setup']}")
                cols=st.columns(7)
                for col,label,value in zip(cols,["Score","Entry","Stop","Target 1","Target 2","R:R","Qty"],[f"{x['score']}/100",f"₹{x['entry']:.2f}",f"₹{x['stop']:.2f}",f"₹{x['target1']:.2f}",f"₹{x['target2']:.2f}",f"{x['rr']:.2f}",x["qty"]]): col.metric(label,value)
                st.write(x["thesis"]); st.caption(f"Technical {x['technical']}/35 · Momentum {x['momentum']}/15 · Fundamental {x['fundamental']}/20 · Catalyst {x['catalyst']}/10 · Market/RS {x['market']}/10 · RSI {x['rsi']:.1f} · Rel. volume {x['relative_volume']:.2f}x · R:R T1 {x['rr_target1']:.2f}"); st.warning(x["risk"])
    else: st.warning("No setup currently passes BOTH the 100-point score and R:R filters. The system is not forcing a trade.")
    st.subheader("🔎 Top 3 Candidates / Near Misses")
    display=[]
    for x in scan["candidates"]:
        display.append({"Symbol":x["symbol"],"Status":x["status"],"Score":x["score"],"Technical":f"{x['technical']}/35","Momentum":f"{x['momentum']}/15","Fundamental":f"{x['fundamental']}/20","Catalyst":f"{x['catalyst']}/10","Market/RS":f"{x['market']}/10","Entry":round(x["entry"],2),"Stop":round(x["stop"],2),"Target 1":round(x["target1"],2),"Target 2":round(x["target2"],2),"R:R T2":round(x["rr"],2),"RSI":round(x["rsi"],1),"Reason":x["reason"]})
    st.dataframe(display,use_container_width=True,hide_index=True); st.metric("Qualified setups today",scan["qualified_count"])
    st.download_button("⬇️ Download full scan CSV",scan["csv"],"nse_swing_daily_scan.csv","text/csv")
else: st.info("Click **Run Daily Scan** to generate today's ranked setups.")
