import pandas as pd
import streamlit as st
import yfinance as yf
from engine import daily_scan, market_regime, indicators, NIFTY100, UPCOMING_ADDITIONS, UPCOMING_REMOVALS

st.set_page_config(page_title="NSE Swing AI Pro", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:linear-gradient(180deg,#07111f 0%,#0b1525 48%,#101827 100%);}
[data-testid="stHeader"]{background:rgba(0,0,0,0);}
.block-container{max-width:1450px;padding-top:1.2rem;}
.hero{padding:26px 28px;border:1px solid rgba(255,255,255,.10);border-radius:24px;background:linear-gradient(135deg,rgba(25,43,70,.95),rgba(10,21,37,.92));box-shadow:0 16px 50px rgba(0,0,0,.22);margin-bottom:18px;}
.hero h1{font-size:38px;line-height:1.05;margin:0 0 8px;font-weight:800}.hero p{color:#a9bbd2;font-size:15px;margin:0}
.pill{display:inline-block;padding:5px 10px;border-radius:999px;background:#162b45;color:#a9d8ff;font-size:12px;margin-right:6px}
.card{background:rgba(16,29,47,.90);border:1px solid rgba(255,255,255,.09);border-radius:18px;padding:18px 20px;margin-bottom:14px}
.trade{background:linear-gradient(145deg,rgba(18,37,58,.98),rgba(12,24,40,.98));border:1px solid rgba(90,180,255,.18);border-radius:20px;padding:20px;margin:12px 0}
.no-trade{background:linear-gradient(135deg,#251b16,#171a22);border:1px solid #6c4c2c;border-radius:20px;padding:26px;text-align:center}
.near{background:linear-gradient(145deg,rgba(42,33,19,.96),rgba(27,24,20,.96));border:1px solid rgba(230,180,70,.25);border-radius:18px;padding:18px;margin:10px 0}
.buy{color:#6ee7b7;font-weight:800}.muted{color:#91a5bd}.small{font-size:12px;color:#8297af}
</style>
""", unsafe_allow_html=True)

def money(x): return f"₹{x:,.0f}"
def pct(x): return f"{x*100:.1f}%"

st.markdown("""<div class="hero"><div><span class="pill">NIFTY 100</span><span class="pill">5 TRADE PLANS</span><span class="pill">DATA-HEALTH AWARE</span></div><h1>📈 Swing Command Center</h1><p>Scan → rank → validate → size → execute manually. Weak or unavailable data never gets silently counted as a rejected trade.</p></div>""",unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🎛️ Trading Controls")
    capital=st.number_input("Trading capital (₹)",min_value=10000.0,value=200000.0,step=10000.0)
    risk_pct=st.number_input("Risk per trade (%)",min_value=.1,max_value=3.0,value=1.0,step=.1)
    max_portfolio_risk=st.number_input("Max portfolio risk (%)",min_value=.5,max_value=10.0,value=5.0,step=.5)
    min_score=st.slider("Minimum model score",50,95,75)
    min_rr=st.slider("Minimum R:R to T2",1.0,5.0,2.0,.1)
    max_trades=st.slider("Max trade plans",1,5,5)
    st.divider()
    st.caption("Model: Technical 35 · Momentum 15 · Fundamentals 20 · Catalyst 10 · Market/Sector/RS 10")
    st.caption("Price history is the critical scan input. Fundamentals/news are optional and visibly flagged if unavailable.")

reg_data=indicators(yf.Ticker("^NSEI").history(period="1y",auto_adjust=False))
reg=market_regime(reg_data)
c=st.columns(4)
c[0].metric("Market regime",reg["label"])
c[1].metric("Regime score",f"{reg['score']}/100")
c[2].metric("Universe","Nifty 100")
c[3].metric("Risk budget / trade",money(capital*risk_pct/100))

st.markdown("<div class='card'><b>Today’s workflow</b><br><span class='muted'>1. Scan 100 names → 2. reject weak setups → 3. calculate entry/SL/targets → 4. size by risk → 5. inspect near misses → 6. export execution tickets.</span></div>",unsafe_allow_html=True)

if st.button("🚀 RUN FULL NIFTY 100 SCAN",type="primary",use_container_width=True):
    with st.spinner("Scanning 100 constituents with resilient data handling..."):
        st.session_state.scan=daily_scan(capital,risk_pct,min_score,min_rr,max_trades)

scan=st.session_state.get("scan")
if not scan:
    st.markdown("<div class='no-trade'><h3>Ready for the opening bell 🔭</h3><p class='muted'>Run the full Nifty 100 scan to populate your trade desk.</p></div>",unsafe_allow_html=True)
    st.stop()

b=scan["breadth"]; d=scan["diagnostics"]
c1,c2,c3,c4,c5=st.columns(5)
c1.metric("Stocks analyzed",b["scanned"])
c2.metric("Positive 20D",b["positive_20d"])
c3.metric("Breakouts",b["breakouts"])
c4.metric("Qualified",len(scan["qualified"]))
c5.metric("Data failures",d["history_failed"])

st.caption(f"Generated: {scan['generated_utc']} · Universe requested: {scan['universe_size']} · Market note: {scan['regime']['note']}")

if d["history_failed"] > 0:
    st.warning(f"⚠️ {d['history_failed']} symbols could not be analyzed from price history. They are excluded from the score rather than being treated as low-score stocks. Open **Data Health** below to inspect them.")

with st.expander("🩺 Data Health — diagnose missing stocks"):
    h1,h2,h3=st.columns(3)
    h1.metric("Price-history OK",d["history_ok"])
    h2.metric("Fundamentals partial",d["fundamental_partial"])
    h3.metric("News partial",d["news_partial"])
    if d["failures"]:
        st.dataframe(pd.DataFrame(d["failures"])[["symbol","stage","error"]],use_container_width=True,hide_index=True)
    st.caption("Provider note: yfinance is a research feed. A temporary provider/rate-limit error should not be interpreted as a bearish stock signal.")

st.info(f"📅 Universe note: the scan is using the current constituent window. NSE has announced Nifty 100 changes effective after the 29-Sep-2026 close; additions/removals will be reflected in a later universe refresh. See Data Health / README for the distinction.")

tab1,tab2,tab3,tab4=st.tabs(["🟢 Trade Desk","🟠 Near Misses","📊 Market Map","🧮 Risk & Export"])

with tab1:
    if scan["qualified"]:
        st.subheader("🟢 Qualified Trade Desk")
        st.caption("Only setups passing score + R:R + position-size checks appear here. No forced fifth trade.")
        tickets=[]
        for i,x in enumerate(scan["qualified"],1):
            with st.container(border=True):
                st.markdown(f"### #{i} — {x['symbol']} <span class='buy'>QUALIFIED</span>",unsafe_allow_html=True)
                m=st.columns(8)
                for col,label,value in zip(m,["Score","Entry","Stop","Target 1","Target 2","R:R","Qty","Max loss"],[f"{x['score']}/100",money(x["entry"]),money(x["stop"]),money(x["target1"]),money(x["target2"]),f"{x['rr']:.2f}R",str(x["qty"]),money(x["max_loss"])]): col.metric(label,value)
                st.write(f"**Trade thesis:** {x['thesis']}")
                st.caption(f"{x['sector']} · 20D {pct(x['ret20'])} · RS vs Nifty {x['rs20']*100:.1f} pts · RSI {x['rsi']:.1f} · RelVol {x['rel_volume']:.2f}x · Data {x['data_quality']}")
                with st.expander("🔬 Score breakdown"):
                    st.write(f"Technical {x['technical']}/35 · Momentum {x['momentum']}/15 · Fundamental {x['fundamental']}/20 · Catalyst {x['catalyst']}/10 · Market/Sector/RS {x['market']}/10")
                    st.caption(x["data_notes"])
                tickets.append({"Rank":i,"Symbol":x["symbol"],"Side":"BUY","Setup":x["setup"],"Entry":round(x["entry"],2),"Stop":round(x["stop"],2),"Target1":round(x["target1"],2),"Target2":round(x["target2"],2),"Qty":x["qty"],"MaxLoss":round(x["max_loss"],2),"CapitalUsed":round(x["capital_used"],2),"Score":x["score"],"RR":round(x["rr"],2),"PriceDate":x["last_date"]})
        st.download_button("⬇️ Download execution tickets",pd.DataFrame(tickets).to_csv(index=False),"nse100_execution_tickets.csv","text/csv",use_container_width=True)
    else:
        st.markdown("<div class='no-trade'><h2>🚫 NO QUALIFIED TRADE TODAY</h2><p>No analyzed Nifty 100 stock passed all mandatory filters. The engine will not manufacture a trade.</p></div>",unsafe_allow_html=True)

with tab2:
    st.subheader("🟠 Near Miss Watchlist")
    st.caption("These are the strongest non-qualified names. They are research watchlist items, not trade signals.")
    if scan["near"]:
        for i,x in enumerate(scan["near"],1):
            st.markdown(f"""<div class="near"><b>#{i} · {x['symbol']}</b> · Score <b>{x['score']}/100</b> · R:R <b>{x['rr']:.2f}R</b><br><span class="muted">{x['setup']} · {x['sector']} · {x['reason']} · Data {x['data_quality']}</span></div>""",unsafe_allow_html=True)
            cols=st.columns(6)
            for col,label,value in zip(cols,["Entry","Stop","T1","T2","RSI","20D"],[money(x["entry"]),money(x["stop"]),money(x["target1"]),money(x["target2"]),f"{x['rsi']:.1f}",pct(x["ret20"])]): col.metric(label,value)
    else:
        st.info("No near misses were generated. If 'Stocks analyzed' is zero, open Data Health — the issue is data availability, not market quality.")

with tab3:
    st.subheader("📊 Market Map")
    df=pd.DataFrame(scan["rows"])
    if not df.empty:
        top=df.head(20)[["symbol","score","rr","ret20","sector","setup","data_quality"]].copy()
        top.columns=["Symbol","Score","R:R","20D Return","Sector","Setup","Data"]
        top["20D Return"]=(top["20D Return"]*100).round(1).astype(str)+"%"
        top["R:R"]=top["R:R"].round(2)
        st.dataframe(top,use_container_width=True,hide_index=True)
        st.bar_chart(df.set_index("symbol")["score"].head(20))
        sec=df.groupby("sector").agg(Stocks=("symbol","count"),Median_20D=("ret20","median"),Avg_Score=("score","mean")).sort_values("Median_20D",ascending=False)
        sec["Median_20D"]=(sec["Median_20D"]*100).round(1).astype(str)+"%"; sec["Avg_Score"]=sec["Avg_Score"].round(1)
        st.dataframe(sec,use_container_width=True)
    else:
        st.warning("No rows available for Market Map. Check Data Health.")

with tab4:
    st.subheader("🧮 Risk & Export")
    r1,r2,r3=st.columns(3)
    per_trade=capital*risk_pct/100; total_risk=max_trades*per_trade
    r1.metric("₹ risk / trade",money(per_trade)); r2.metric("Portfolio cap",money(capital*max_portfolio_risk/100)); r3.metric("Max quota risk",money(total_risk))
    if total_risk>capital*max_portfolio_risk/100: st.warning("Your maximum number of simultaneous plans can exceed the portfolio-risk cap.")
    st.download_button("📥 Download full Nifty 100 scan",scan.get("csv","No scan data available.\n"),"nse100_full_scan.csv","text/csv",use_container_width=True)
    st.markdown(f"<div class='card'><b>Data architecture</b><br>Universe: Nifty 100 · Price/fundamental/news: Yahoo Finance/yfinance research feed.<br>Current Nifty 100 is reviewed periodically; this build keeps announced future changes separate from the current scan window.<br><br><b>Important:</b> Manual execution only. Verify live price, liquidity, order status and stop placement at your broker.</div>",unsafe_allow_html=True)

st.divider()
st.caption("⚠️ Research tool, not a guarantee of returns. Validate prices and order details at your broker before placing any trade.")
