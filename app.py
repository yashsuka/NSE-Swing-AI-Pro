import streamlit as st
import pandas as pd
from engine import daily_scan, NIFTY100, batch_price_data, regime
st.set_page_config(page_title="Swing Command Center v5.3",page_icon="📈",layout="wide")
st.markdown("""<style>.block-container{max-width:1450px;padding-top:1.2rem}.hero{padding:28px 32px;border-radius:24px;background:linear-gradient(135deg,#0b1930,#132c4d);border:1px solid #27486d;margin-bottom:18px}.hero h1{font-size:42px;margin:0}.badge{display:inline-block;padding:6px 12px;border-radius:20px;background:#16395e;margin-right:8px;font-size:13px}</style>""",unsafe_allow_html=True)
st.markdown('<div class="hero"><span class="badge">NIFTY 100</span><span class="badge">5 TRADE PLANS</span><span class="badge">BULK PRICE DATA</span><span class="badge">NO SILENT FAILURES</span><h1>📈 Swing Command Center</h1><p>Scan → rank → validate → size → inspect near misses → execute manually.</p></div>',unsafe_allow_html=True)
with st.sidebar:
    st.header("🎛 Trading Controls"); capital=st.number_input("Trading capital (₹)",10000.0,100000000.0,200000.0,10000.0); risk_pct=st.number_input("Risk per trade (%)",.1,5.0,1.0,.1); min_score=st.slider("Minimum model score",50,95,75); min_rr=st.slider("Minimum R:R to T2",1.0,5.0,2.0,.1); max_plans=st.slider("Max trade plans",1,5,5)
    st.caption("The full universe is fetched with one bulk price request. Optional news is only checked on the shortlist.")
# Do not make 100 requests just to render the header.
if "scan" not in st.session_state:
    market={"label":"RUN SCAN","score":0,"note":"Run the scanner to load the benchmark."}
else: market=st.session_state.scan["regime"]
a,b,c,d=st.columns(4); a.metric("Market regime",market["label"]); b.metric("Regime score",f"{market['score']}/100"); c.metric("Universe","Nifty 100"); d.metric("Risk budget / trade",f"₹{capital*risk_pct/100:,.0f}")
st.info("🛠 v5.3 fixes the previous architecture: 100 individual Yahoo history calls were causing the 100 data failures. Price history is now downloaded in bulk; optional enrichment is limited to the shortlist.")
if st.button("🚀 RUN FULL NIFTY 100 SCAN",type="primary",use_container_width=True):
    with st.spinner("Downloading Nifty 100 history once and ranking the universe..."): st.session_state.scan=daily_scan(capital,risk_pct,min_score,min_rr,max_plans)
scan=st.session_state.get("scan")
if scan:
    m=st.columns(5); m[0].metric("Stocks analyzed",scan["analyzed_count"]); m[1].metric("Positive 20D",sum(r["ret20"]>0 for r in scan["all"])); m[2].metric("Breakouts",sum(r["setup"]=="BREAKOUT" for r in scan["all"])); m[3].metric("Qualified",scan["qualified_count"]); m[4].metric("Data failures",len(scan["failures"]))
    st.caption(f"Generated {scan['generated_utc']} · Universe requested {scan['universe_size']} · {scan['regime']['note']}")
    if scan["bulk_error"]: st.error("🚨 PRICE DATA PROVIDER FAILURE — this is not a zero-trade result."); st.code(scan["bulk_error"])
    t1,t2,t3,t4,t5=st.tabs(["🟢 Trade Desk","🟠 Near Misses","📊 Market Map","🩺 Data Health","📦 Export"])
    with t1:
        if scan["top5"]:
            for i,x in enumerate(scan["top5"],1):
                with st.container(border=True):
                    st.markdown(f"### #{i} {x['symbol']} · 🟢 QUALIFIED · {x['setup']}"); cols=st.columns(8)
                    for col,label,val in zip(cols,["Score","Entry","Stop","Target 1","Target 2","R:R","Qty","Max loss"],[f"{x['score']}/100",f"₹{x['entry']:.2f}",f"₹{x['stop']:.2f}",f"₹{x['target1']:.2f}",f"₹{x['target2']:.2f}",f"{x['rr']:.2f}",str(x['qty']),f"₹{x['max_loss']:.0f}"]): col.metric(label,val)
                    st.caption(f"Technical {x['technical']}/35 · Momentum {x['momentum']}/15 · Fundamental {x['fundamental']}/20 · Catalyst {x['catalyst']}/10 · Market/RS {x['market']}/10 · RSI {x['rsi']:.1f} · 20D {x['ret20']*100:.1f}% · RelVol {x['relative_volume']:.2f}x · {x['data_quality']}")
                    st.warning("Manual execution only. Verify the live quote, spread, liquidity and stop placement with your broker.")
        else: st.warning("🚫 NO QUALIFIED TRADE TODAY — no analyzed Nifty 100 stock passed all mandatory filters.")
    with t2:
        if scan["near_misses"]: st.dataframe(pd.DataFrame([{k:v for k,v in {"Symbol":x["symbol"],"Score":x["score"],"R:R":round(x["rr"],2),"Setup":x["setup"],"Entry":round(x["entry"],2),"Stop":round(x["stop"],2),"20D %":round(x["ret20"]*100,1),"Reason":x["reason"]}.items()} for x in scan["near_misses"]]),use_container_width=True,hide_index=True)
        else: st.info("No near misses. If Stocks analyzed is 0, inspect Data Health.")
    with t3:
        if scan["all"]: st.dataframe(pd.DataFrame(scan["all"])[["symbol","score","ret20","rr","setup","rsi","relative_volume","data_quality"]],use_container_width=True,hide_index=True)
    with t4:
        st.write(f"**Price-analyzed:** {scan['analyzed_count']} / {scan['universe_size']}"); st.write(f"**Failures:** {len(scan['failures'])}")
        if scan["failures"]: st.dataframe(pd.DataFrame(scan["failures"]),use_container_width=True,hide_index=True)
        else: st.success("All Nifty 100 symbols returned usable price history.")
    with t5:
        st.download_button("⬇️ Download full scan CSV",scan["csv"],"nifty100_full_scan.csv","text/csv",use_container_width=True)
        if scan["top5"]:
            tickets=pd.DataFrame([{ "Rank":i+1,"Symbol":x["symbol"],"Side":"BUY","Entry":round(x["entry"],2),"Stop":round(x["stop"],2),"Target1":round(x["target1"],2),"Target2":round(x["target2"],2),"Qty":x["qty"],"MaxLoss":round(x["max_loss"],2),"CapitalUsed":round(x["capital_used"],2),"Score":x["score"],"RR":round(x["rr"],2)} for i,x in enumerate(scan["top5"])])
            st.download_button("⬇️ Download execution tickets",tickets.to_csv(index=False),"execution_tickets.csv","text/csv",use_container_width=True)
else: st.info("Click **RUN FULL NIFTY 100 SCAN** to generate the first scan.")
