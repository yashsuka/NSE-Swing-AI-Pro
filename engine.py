import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# Current Nifty 100 universe. NSE describes Nifty 100 as a diversified 100-stock index
# representing major sectors and combining Nifty 50 + Nifty Next 50.
NIFTY100 = ['ABB', 'ADANIENSOL', 'ADANIENT', 'ADANIGREEN', 'ADANIPORTS', 'ADANIPOWER', 'AMBUJACEM', 'APOLLOHOSP', 'ASIANPAINT', 'AXISBANK', 'BAJAJ-AUTO', 'BAJAJFINSV', 'BAJAJHLDNG', 'BAJFINANCE', 'BANKBARODA', 'BEL', 'BHARTIARTL', 'BOSCHLTD', 'BPCL', 'BRITANNIA', 'CANBK', 'CGPOWER', 'CHOLAFIN', 'CIPLA', 'COALINDIA', 'CUMMINSIND', 'DIVISLAB', 'DLF', 'DMART', 'DRREDDY', 'EICHERMOT', 'ENRIN', 'ETERNAL', 'GAIL', 'GODREJCP', 'GRASIM', 'HAL', 'HCLTECH', 'HDFCAMC', 'HDFCBANK', 'HDFCLIFE', 'HINDALCO', 'HINDUNILVR', 'HINDZINC', 'HYUNDAI', 'ICICIBANK', 'INDHOTEL', 'INDIGO', 'INFY', 'IOC', 'IRFC', 'ITC', 'JINDALSTEL', 'JIOFIN', 'JSWSTEEL', 'KOTAKBANK', 'LODHA', 'LT', 'LTIM', 'M&M', 'MARUTI', 'MAXHEALTH', 'MAZDOCK', 'MOTHERSON', 'MUTHOOTFIN', 'NESTLEIND', 'NTPC', 'ONGC', 'PFC', 'PIDILITIND', 'PNB', 'POWERGRID', 'RECLTD', 'RELIANCE', 'SBILIFE', 'SBIN', 'SHREECEM', 'SHRIRAMFIN', 'SIEMENS', 'SOLARINDS', 'SUNPHARMA', 'TATACAP', 'TATACONSUM', 'TATAPOWER', 'TATASTEEL', 'TCS', 'TECHM', 'TITAN', 'TMCV', 'TMPV', 'TORNTPHARM', 'TRENT', 'TVSMOTOR', 'ULTRACEMCO', 'UNIONBANK', 'UNITDSPR', 'VBL', 'VEDL', 'WIPRO', 'ZYDUSLIFE']

POS = {"upgrade","upgraded","buy","bullish","growth","strong","record","beat","beats","surge","order","contract","expansion","positive","outperform","approval"}
NEG = {"downgrade","downgraded","sell","bearish","weak","miss","misses","fall","falls","cut","lawsuit","probe","loss","negative","warning"}

def _yf(symbol):
    return yf.Ticker(symbol + ".NS")

def _history(symbol, period="1y"):
    return _yf(symbol).history(period=period, auto_adjust=False)

def indicators(df):
    d=df.copy()
    if d.empty: return d
    c,h,l,v=d["Close"],d["High"],d["Low"],d["Volume"]
    d["EMA20"]=c.ewm(span=20,adjust=False).mean()
    d["EMA50"]=c.ewm(span=50,adjust=False).mean()
    d["EMA200"]=c.ewm(span=200,adjust=False).mean()
    delta=c.diff()
    gain=delta.clip(lower=0).rolling(14).mean()
    loss=(-delta.clip(upper=0)).rolling(14).mean()
    rs=gain/loss.replace(0,np.nan)
    d["RSI"]=100-(100/(1+rs))
    e12=c.ewm(span=12,adjust=False).mean()
    e26=c.ewm(span=26,adjust=False).mean()
    d["MACD"]=e12-e26
    d["MACDsig"]=d["MACD"].ewm(span=9,adjust=False).mean()
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    d["ATR"]=tr.rolling(14).mean()
    d["Vol20"]=v.rolling(20).mean()
    d["High20"]=h.shift(1).rolling(20).max()
    d["Low20"]=l.shift(1).rolling(20).min()
    d["Turnover20"]=(c*v).rolling(20).mean()
    d["Ret5"]=c.pct_change(5)
    d["Ret20"]=c.pct_change(20)
    d["Ret60"]=c.pct_change(60)
    return d.dropna()

def technical_score(d):
    x=d.iloc[-1]; s=0
    s += 7 if x.Close>x.EMA20 else 0
    s += 7 if x.EMA20>x.EMA50 else 0
    s += 6 if x.EMA50>x.EMA200 else 0
    s += 5 if 52<=x.RSI<=70 else (3 if 45<=x.RSI<52 else 0)
    s += 5 if x.MACD>x.MACDsig else 0
    s += 5 if x.Close>x.High20 else (2 if x.Close>x.High20*0.98 else 0)
    return int(s)

def momentum_score(d):
    x=d.iloc[-1]; s=0
    s += 5 if x.Ret20>.05 else (3 if x.Ret20>.02 else (1 if x.Ret20>0 else 0))
    s += 5 if x.Ret60>.08 else (3 if x.Ret60>.03 else (1 if x.Ret60>0 else 0))
    s += 5 if x.Volume>x.Vol20*1.2 else (3 if x.Volume>x.Vol20 else 0)
    return int(s)

def fundamental_score(info):
    s=0
    roe=info.get("returnOnEquity")
    margin=info.get("profitMargins")
    growth=info.get("earningsGrowth")
    debt=info.get("debtToEquity")
    s += 7 if isinstance(roe,(int,float)) and roe>.15 else (4 if isinstance(roe,(int,float)) and roe>.08 else 0)
    s += 5 if isinstance(margin,(int,float)) and margin>.08 else (2 if isinstance(margin,(int,float)) and margin>0 else 0)
    s += 5 if isinstance(growth,(int,float)) and growth>.05 else (2 if isinstance(growth,(int,float)) and growth>0 else 0)
    s += 3 if not isinstance(debt,(int,float)) or debt<150 else (1 if debt<250 else 0)
    return int(min(20,s))

def news_catalyst(symbol):
    try:
        news=_yf(symbol).news or []
        p=n=0
        headlines=[]
        for item in news[:8]:
            title=str(item.get("title",""))
            low=title.lower()
            p+=sum(w in low for w in POS)
            n+=sum(w in low for w in NEG)
            if title: headlines.append(title)
        score=10 if p>=3 and p>n else (7 if p>=2 and p>n else (4 if p>=1 and p>n else 0))
        return int(score), headlines[:3]
    except Exception:
        return 0, []

def market_regime(nifty):
    x=nifty.iloc[-1]
    if x.Close>x.EMA50>x.EMA200: return {"label":"BULLISH","score":70,"note":"Price above 50/200-day trend; selective momentum setups can be considered."}
    if x.Close>x.EMA200: return {"label":"NEUTRAL","score":55,"note":"Mixed trend; require stronger individual setups and tighter risk control."}
    return {"label":"DEFENSIVE","score":35,"note":"Benchmark below long-term trend; the model should reject marginal setups."}

def levels(d):
    x=d.iloc[-1]; close=float(x.Close); atr=float(x.ATR)
    recent_low=float(d.Low.tail(10).min())
    recent_high=float(d.High.tail(20).max())
    if close>float(x.High20):
        entry=max(close,float(x.High20)+0.10*atr)
        stop=max(0.01,entry-1.20*atr)
        setup="BREAKOUT"
    elif close>x.EMA20 and x.EMA20>x.EMA50 and x.RSI<68:
        entry=close
        stop=max(0.01,min(entry-1.50*atr,recent_low-0.20*atr))
        setup="TREND CONTINUATION"
    else:
        entry=close
        stop=max(0.01,entry-1.50*atr)
        setup="PULLBACK / WATCH"
    risk=entry-stop
    if risk<=0: return None
    t1=max(recent_high,entry+1.5*risk)
    t2=max(entry+2.5*risk,t1+0.5*risk)
    return entry,stop,t1,t2,(t2-entry)/risk,(t1-entry)/risk,setup

def _analyze_one(symbol, capital, risk_pct, nifty_ret20):
    try:
        d=indicators(_history(symbol))
        if len(d)<220: return None
        info=_yf(symbol).info
        tech=technical_score(d); mom=momentum_score(d); fund=fundamental_score(info)
        cat, headlines=news_catalyst(symbol)
        x=d.iloc[-1]
        rs20=float(x.Ret20-nifty_ret20)
        rs_points=5 if rs20>.05 else (3 if rs20>.02 else (1 if rs20>0 else 0))
        market_points=5
        lev=levels(d)
        if not lev: return None
        entry,stop,t1,t2,rr,rr1,setup=lev
        risk_per_share=entry-stop
        risk_budget=capital*risk_pct/100
        qty=max(0,int(risk_budget/risk_per_share))
        capital_used=qty*entry
        max_loss=qty*risk_per_share
        total=min(100,tech+mom+fund+cat+market_points+rs_points)
        dt=d.index[-1]
        if getattr(dt,"tzinfo",None) is not None: dt=dt.tz_convert(None)
        sector=info.get("sector") or info.get("industry") or "Unknown"
        return {
            "symbol":symbol,"score":int(total),"technical":tech,"momentum":mom,
            "fundamental":fund,"catalyst":cat,"market":market_points+rs_points,
            "setup":setup,"entry":entry,"stop":stop,"target1":t1,"target2":t2,
            "rr":rr,"rr_target1":rr1,"qty":qty,"risk_rupees":risk_budget,
            "capital_used":capital_used,"max_loss":max_loss,"rsi":float(x.RSI),
            "rel_volume":float(x.Volume/x.Vol20) if x.Vol20 else 0,
            "ret20":float(x.Ret20),"ret60":float(x.Ret60),"rs20":rs20,
            "turnover20":float(x.Turnover20),"last_price":float(x.Close),
            "last_date":str(dt.date()),"sector":sector,"headlines":headlines,
            "thesis":f"{setup} structure; {total}/100 model score; 20D relative strength {rs20*100:.1f} percentage points vs Nifty.",
            "data_source":"Yahoo Finance / yfinance (research feed; not exchange-grade execution data)"
        }
    except Exception:
        return None

def daily_scan(capital,risk_pct,min_score=75,min_rr=2.0,max_results=5):
    nifty=indicators(yf.Ticker("^NSEI").history(period="1y",auto_adjust=False))
    if nifty.empty: return {"rows":[],"qualified":[],"near":[],"generated_utc":datetime.now(timezone.utc).isoformat(),"breadth":{}}
    nifty_ret20=float(nifty.iloc[-1].Ret20)
    results=[]
    workers=min(8, len(NIFTY100))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures=[ex.submit(_analyze_one,s,capital,risk_pct,nifty_ret20) for s in NIFTY100]
        for f in as_completed(futures):
            r=f.result()
            if r: results.append(r)
    # sector momentum = median 20D return by sector, then converted into a small 0-5 overlay.
    df=pd.DataFrame(results)
    if not df.empty:
        sector_medians=df.groupby("sector")["ret20"].median().to_dict()
        for r in results:
            sec=sector_medians.get(r["sector"],r["ret20"])
            sec_pts=5 if sec>0.05 else (3 if sec>0.02 else (1 if sec>0 else 0))
            # Replace the generic 5-point market component with market + sector + RS, capped at 10.
            r["market"]=int(min(10,5+sec_pts))
            r["score"]=int(min(100,r["technical"]+r["momentum"]+r["fundamental"]+r["catalyst"]+r["market"]))
            r["sector_return20"]=float(sec)
            r["qualified"]=bool(r["score"]>=min_score and r["rr"]>=min_rr and r["qty"]>0)
            if r["qualified"]:
                r["status"]="QUALIFIED"; r["reason"]="Passes score + R:R + position-size checks"
            elif r["score"]>=min_score or r["rr"]>=min_rr:
                r["status"]="NEAR MISS"; r["reason"]=f"Score {r['score']} vs {min_score} · R:R {r['rr']:.2f} vs {min_rr:.2f}"
            else:
                r["status"]="REJECTED"; r["reason"]=f"Score {r['score']} < {min_score} · R:R {r['rr']:.2f} < {min_rr:.2f}"
    results.sort(key=lambda z:(z["score"],z["rr"]),reverse=True)
    qualified=[r for r in results if r["qualified"]]
    near=[r for r in results if r["status"]=="NEAR MISS"]
    breadth={
        "above_ema20":sum(r["last_price"]>0 for r in results), # populated more accurately below
        "positive_20d":sum(r["ret20"]>0 for r in results),
        "breakouts":sum(r["setup"]=="BREAKOUT" for r in results),
        "qualified":len(qualified),
        "scanned":len(results)
    }
    # Market breadth metrics from result universe.
    # Above EMA20 is not retained in result payload; positive 20D and breakouts are robust proxies.
    csv=pd.DataFrame(results).to_csv(index=False) if results else "No analyzable stocks.\n"
    return {
        "rows":results,"qualified":qualified[:max_results],"near":near[:max_results],
        "csv":csv,"generated_utc":datetime.now(timezone.utc).isoformat(),
        "breadth":breadth,"universe_size":len(NIFTY100),
        "regime":market_regime(nifty)
    }
