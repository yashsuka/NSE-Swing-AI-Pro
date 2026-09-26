import streamlit as st
import pandas as pd
from engine import scan, backtest

st.set_page_config(page_title="Nifty100 Swing Scanner — Final",page_icon="📈",layout="wide")
st.markdown("""<style>.block-container{max-width:1450px;padding-top:1.2rem}.hero{padding:28px 32px;border-radius:24px;background:linear-gradient(135deg,#0b1930,#132c4d);border:1px solid #27486d;margin-bottom:18px}.hero h1{font-size:40px;margin:0}.pill{display:inline-block;padding:6px 12px;border-radius:20px;background:#16395e;margin-right:7px;font-size:13px}</style>""",unsafe_allow_html=True)
st.markdown('<div class="hero"><span class="pill">NIFTY 100</span><span class="pill">PRICE-ONLY MODEL</span><span class="pill">CHUNKED DATA</span><span class="pill">WALK-FORWARD TEST</span><h1>📈 Swing Command Center — Final</h1><p>Simple by design: trend + momentum + breakout + relative strength + risk.</p></div>',unsafe_allow_html=True)
with st.sidebar:
    st.header("🎛 Controls")
    capital=st.number_input("Trading capital (₹)",10000.0,100000000.0,200000.0,10000.0)
    risk_pct=st.number_input("Risk per trade (%)",0.25,3.0,1.0,0.25)
    min_score=st.slider("Minimum model score",55,90,70)
    min_rr=st.slider("Minimum R:R",1.5,4.0,2.0,0.25)
    max_plans=st.slider("Maximum trade plans",1,5,5)
    run=st.button("🚀 RUN FINAL SCAN",type="primary",use_container_width=True)
if run:
    with st.spinner("Downloading Nifty 100 in small batches, validating data and calculating setups..."):
        st.session_state.result=scan(capital,risk_pct,min_score,min_rr,max_plans)
r=st.session_state.get("result")
if not r:
    st.info("Click **RUN FINAL SCAN**. The app intentionally does not invent prices or signals when the data provider fails.")
    st.stop()
reg=r["regime"]
a,b,c,d=st.columns(4); a.metric("Market regime",reg["label"]); b.metric("Regime score",f"{reg['score']}/100"); c.metric("Stocks analyzed",f"{r['analyzed']}/{r['universe']}"); d.metric("Risk / trade",f"₹{capital*risk_pct/100:,.0f}")
st.caption(reg["note"]+f" · Universe source: {r['source']} · Generated {r['generated']}")
if r["analyzed"]==0:
    st.error("🚨 No price histories were returned. This is a DATA problem, not a zero-trade signal. Open Data Health and use the exact provider error before trading.")
q=r["qualified"]
t1,t2,t3,t4,t5=st.tabs(["🟢 Trade Desk","🟠 Near Misses","📊 Market Map","🩺 Data Health","🧪 Backtest"])
with t1:
    if q:
        for i,x in enumerate(q,1):
            with st.container(border=True):
                st.markdown(f"### #{i} {x['symbol']} · 🟢 {x['setup']}")
                cols=st.columns(8)
                vals=[f"{x['score']}/100",f"₹{x['entry']:.2f}",f"₹{x['stop']:.2f}",f"₹{x['target1']:.2f}",f"₹{x['target2']:.2f}",f"{x['rr']:.2f}",str(x['qty']),f"₹{x['max_loss']:.0f}"]
                for col,label,val in zip(cols,["Score","Entry","Stop","T1","T2","R:R","Qty","Max loss"],vals): col.metric(label,val)
                st.caption(f"Trend {x['technical']}/30 · Momentum {x['momentum']}/25 · Breakout {x['breakout']}/20 · Relative strength {x['relative']}/15 · Risk/liquidity {x['risk']}/10 · RSI {x['rsi']:.1f} · 20D {x['ret20']*100:.1f}% · RelVol {x['relative_volume']:.2f}x · Data {x['last_date']}")
                st.warning("Manual execution only. Verify live quote, spread, liquidity, corporate actions and stop before placing an order.")
    else: st.warning("No setup currently passes both the score and R:R filters. That is an intentional no-trade result.")
with t2:
    if r["near"]: st.dataframe(pd.DataFrame(r["near"])[["symbol","score","rr","setup","entry","stop","target2","ret20","rsi","reason"]],use_container_width=True,hide_index=True)
    else: st.info("No near misses among analyzed stocks.")
with t3:
    if r["rows"]:
        st.dataframe(pd.DataFrame(r["rows"])[["symbol","score","rr","setup","ret20","ret60","rsi","relative_volume","atr_pct","status"]],use_container_width=True,hide_index=True)
with t4:
    st.write(f"**Returned usable histories:** {r['analyzed']} / {r['universe']}")
    if r["diagnostics"]: st.dataframe(pd.DataFrame(r["diagnostics"]),use_container_width=True,hide_index=True)
    if r["failures"]: st.dataframe(pd.DataFrame(r["failures"]),use_container_width=True,hide_index=True)
    else: st.success("All requested stocks returned sufficient history.")
with t5:
    st.write("This is a simple historical check of the same core idea: trend + momentum or breakout + momentum, entered on the next day's open, with a 1.5 ATR stop and 3R target, maximum 15 trading days. It is not a guarantee of future performance.")
    if r["rows"]:
        stats=[]
        # Only test the stocks that actually returned data; no look-ahead is used in the signal itself.
        # Backtests are calculated during the scan from the same downloaded data;
        # no second provider download is made here.
        stats = r.get("backtests", [])
        if stats:
            bt=pd.DataFrame(stats)
            m=st.columns(4); m[0].metric("Stocks with trades",len(bt)); m[1].metric("Median win rate",f"{bt.win_rate.median():.1f}%"); m[2].metric("Median avg R",f"{bt.avg_r.median():.2f}R"); m[3].metric("Median profit factor",f"{bt.profit_factor.replace([float('inf')],pd.NA).median():.2f}")
            st.dataframe(bt.sort_values("avg_r",ascending=False),use_container_width=True,hide_index=True)
        else: st.info("Not enough returned history to produce a backtest.")
    else: st.info("Run a successful scan first.")
with st.expander("Why this version is deliberately simpler"):
    st.markdown("""1. **No fundamentals/news calls during the scan.** They were adding provider failure points and the old app was falsely assigning placeholder points.\n2. **No single giant 100-ticker request.** History is downloaded in small sequential batches with retries.\n3. **No benchmark dependency.** Market regime is cross-sectional breadth of the same universe.\n4. **No fake 100-point fundamentals score.** Every point now comes from price/volume evidence.\n5. **No forced five trades.** Five is a maximum, not a quota.\n6. **No silent failure.** Every batch and failed symbol is shown in Data Health.""")
