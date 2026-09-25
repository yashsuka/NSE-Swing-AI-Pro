import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import yfinance as yf

# Nifty 100 universe used for the current scan window (before the 30-Sep-2026
# announced rebalance becomes effective). NSE says Nifty 100 is the top 100
# companies by full market capitalisation from Nifty 500.
NIFTY100 = ['ABB','ADANIENSOL','ADANIENT','ADANIGREEN','ADANIPORTS','ADANIPOWER','AMBUJACEM','APOLLOHOSP','ASIANPAINT','AXISBANK','BAJAJ-AUTO','BAJAJFINSV','BAJAJHLDNG','BAJFINANCE','BANKBARODA','BEL','BHARTIARTL','BOSCHLTD','BPCL','BRITANNIA','CANBK','CGPOWER','CHOLAFIN','CIPLA','COALINDIA','CUMMINSIND','DIVISLAB','DLF','DMART','DRREDDY','EICHERMOT','ENRIN','ETERNAL','GAIL','GODREJCP','GRASIM','HAL','HCLTECH','HDFCAMC','HDFCBANK','HDFCLIFE','HINDALCO','HINDUNILVR','HINDZINC','HYUNDAI','ICICIBANK','INDHOTEL','INDIGO','INFY','IOC','IRFC','ITC','JINDALSTEL','JIOFIN','JSWSTEEL','KOTAKBANK','LODHA','LT','LTIM','M&M','MARUTI','MAXHEALTH','MAZDOCK','MOTHERSON','MUTHOOTFIN','NESTLEIND','NTPC','ONGC','PFC','PIDILITIND','PNB','POWERGRID','RECLTD','RELIANCE','SBILIFE','SBIN','SHREECEM','SHRIRAMFIN','SIEMENS','SOLARINDS','SUNPHARMA','TATACAP','TATACONSUM','TATAPOWER','TATASTEEL','TCS','TECHM','TITAN','TORNTPHARM','TRENT','TVSMOTOR','ULTRACEMCO','UNIONBANK','UNITDSPR','VBL','VEDL','WIPRO','ZYDUSLIFE']

# Announced changes effective after the 29-Sep-2026 close. These are kept
# separate so the scanner does not silently mix future constituents into the
# current-date universe.
UPCOMING_ADDITIONS = ["BSE","HITACHIENERGY","POLYCAB","VEDLALUM","IDEA"]
UPCOMING_REMOVALS = ["INDHOTEL","LODHA","RECLTD","SHREECEM","UNITDSPR"]

POS={"upgrade","upgraded","buy","bullish","growth","strong","record","beat","beats","surge","order","contract","expansion","positive","outperform","approval"}
NEG={"downgrade","downgraded","sell","bearish","weak","miss","misses","fall","falls","cut","lawsuit","probe","loss","negative","warning"}

SECTOR_HINTS={
"ABB":"Industrials","ADANIENSOL":"Power","ADANIENT":"Metals & Mining","ADANIGREEN":"Power","ADANIPORTS":"Services","ADANIPOWER":"Power",
"AMBUJACEM":"Construction Materials","APOLLOHOSP":"Healthcare","ASIANPAINT":"Consumer","AXISBANK":"Financial Services","BAJAJ-AUTO":"Automobile",
"BAJAJFINSV":"Financial Services","BAJAJHLDNG":"Financial Services","BAJFINANCE":"Financial Services","BANKBARODA":"Financial Services",
"BEL":"Industrials","BHARTIARTL":"Telecommunication","BOSCHLTD":"Automobile","BPCL":"Oil Gas","BRITANNIA":"FMCG","CANBK":"Financial Services",
"CGPOWER":"Industrials","CHOLAFIN":"Financial Services","CIPLA":"Healthcare","COALINDIA":"Metals & Mining","CUMMINSIND":"Industrials",
"DIVISLAB":"Healthcare","DLF":"Real Estate","DMART":"Consumer","DRREDDY":"Healthcare","EICHERMOT":"Automobile","ENRIN":"Power","ETERNAL":"Consumer",
"GAIL":"Oil Gas","GODREJCP":"FMCG","GRASIM":"Industrials","HAL":"Industrials","HCLTECH":"IT","HDFCAMC":"Financial Services","HDFCBANK":"Financial Services",
"HDFCLIFE":"Financial Services","HINDALCO":"Metals & Mining","HINDUNILVR":"FMCG","HINDZINC":"Metals & Mining","HYUNDAI":"Automobile","ICICIBANK":"Financial Services",
"INDHOTEL":"Consumer","INDIGO":"Services","INFY":"IT","IOC":"Oil Gas","IRFC":"Financial Services","ITC":"FMCG","JINDALSTEL":"Metals & Mining","JIOFIN":"Financial Services",
"JSWSTEEL":"Metals & Mining","KOTAKBANK":"Financial Services","LODHA":"Real Estate","LT":"Industrials","LTIM":"IT","M&M":"Automobile","MARUTI":"Automobile",
"MAXHEALTH":"Healthcare","MAZDOCK":"Industrials","MOTHERSON":"Automobile","MUTHOOTFIN":"Financial Services","NESTLEIND":"FMCG","NTPC":"Power","ONGC":"Oil Gas",
"PFC":"Financial Services","PIDILITIND":"Chemicals","PNB":"Financial Services","POWERGRID":"Power","RECLTD":"Financial Services","RELIANCE":"Oil Gas",
"SBILIFE":"Financial Services","SBIN":"Financial Services","SHREECEM":"Construction Materials","SHRIRAMFIN":"Financial Services","SIEMENS":"Industrials",
"SOLARINDS":"Chemicals","SUNPHARMA":"Healthcare","TATACAP":"Financial Services","TATACONSUM":"FMCG","TATAPOWER":"Power","TATASTEEL":"Metals & Mining",
"TCS":"IT","TECHM":"IT","TITAN":"Consumer","TORNTPHARM":"Healthcare","TRENT":"Consumer","TVSMOTOR":"Automobile","ULTRACEMCO":"Construction Materials",
"UNIONBANK":"Financial Services","UNITDSPR":"Consumer","VBL":"FMCG","VEDL":"Metals & Mining","WIPRO":"IT","ZYDUSLIFE":"Healthcare"
}

def _ticker(symbol):
    return yf.Ticker(symbol + ".NS")

def _history(symbol, retries=2):
    last=None
    for attempt in range(retries+1):
        try:
            d=_ticker(symbol).history(period="1y", auto_adjust=False)
            if d is not None and not d.empty:
                return d, ""
            last="empty history"
        except Exception as e:
            last=f"{type(e).__name__}: {str(e)[:100]}"
        if attempt < retries:
            time.sleep(0.4*(attempt+1))
    return pd.DataFrame(), last or "unknown history error"

def indicators(df):
    if df is None or df.empty: return pd.DataFrame()
    d=df.copy()
    c,h,l,v=d["Close"],d["High"],d["Low"],d["Volume"]
    d["EMA20"]=c.ewm(span=20,adjust=False).mean()
    d["EMA50"]=c.ewm(span=50,adjust=False).mean()
    d["EMA200"]=c.ewm(span=200,adjust=False).mean()
    delta=c.diff()
    gain=delta.clip(lower=0).rolling(14).mean()
    loss=(-delta.clip(upper=0)).rolling(14).mean()
    d["RSI"]=100-(100/(1+(gain/loss.replace(0,np.nan))))
    e12=c.ewm(span=12,adjust=False).mean(); e26=c.ewm(span=26,adjust=False).mean()
    d["MACD"]=e12-e26; d["MACDsig"]=d["MACD"].ewm(span=9,adjust=False).mean()
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    d["ATR"]=tr.rolling(14).mean()
    d["Vol20"]=v.rolling(20).mean()
    d["High20"]=h.shift(1).rolling(20).max()
    d["Low20"]=l.shift(1).rolling(20).min()
    d["Turnover20"]=(c*v).rolling(20).mean()
    d["Ret5"]=c.pct_change(5); d["Ret20"]=c.pct_change(20); d["Ret60"]=c.pct_change(60)
    return d.dropna()

def technical_score(d):
    x=d.iloc[-1]; s=0
    s+=7 if x.Close>x.EMA20 else 0
    s+=7 if x.EMA20>x.EMA50 else 0
    s+=6 if x.EMA50>x.EMA200 else 0
    s+=5 if 52<=x.RSI<=70 else (3 if 45<=x.RSI<52 else 0)
    s+=5 if x.MACD>x.MACDsig else 0
    s+=5 if x.Close>x.High20 else (2 if x.Close>x.High20*0.98 else 0)
    return int(s)

def momentum_score(d):
    x=d.iloc[-1]; s=0
    s+=5 if x.Ret20>.05 else (3 if x.Ret20>.02 else (1 if x.Ret20>0 else 0))
    s+=5 if x.Ret60>.08 else (3 if x.Ret60>.03 else (1 if x.Ret60>0 else 0))
    s+=5 if x.Volume>x.Vol20*1.2 else (3 if x.Volume>x.Vol20 else 0)
    return int(s)

def safe_info(symbol):
    try:
        return _ticker(symbol).info or {}, ""
    except Exception as e:
        return {}, f"{type(e).__name__}: {str(e)[:100]}"

def fundamental_score(info):
    s=0
    roe=info.get("returnOnEquity"); margin=info.get("profitMargins"); growth=info.get("earningsGrowth"); debt=info.get("debtToEquity")
    s+=7 if isinstance(roe,(int,float)) and roe>.15 else (4 if isinstance(roe,(int,float)) and roe>.08 else 0)
    s+=5 if isinstance(margin,(int,float)) and margin>.08 else (2 if isinstance(margin,(int,float)) and margin>0 else 0)
    s+=5 if isinstance(growth,(int,float)) and growth>.05 else (2 if isinstance(growth,(int,float)) and growth>0 else 0)
    s+=3 if not isinstance(debt,(int,float)) or debt<150 else (1 if debt<250 else 0)
    return int(min(20,s))

def news_catalyst(symbol):
    try:
        news=_ticker(symbol).news or []
        p=n=0; headlines=[]
        for item in news[:8]:
            title=str(item.get("title","")); low=title.lower()
            p+=sum(w in low for w in POS); n+=sum(w in low for w in NEG)
            if title: headlines.append(title)
        score=10 if p>=3 and p>n else (7 if p>=2 and p>n else (4 if p>=1 and p>n else 0))
        return int(score),headlines[:3],""
    except Exception as e:
        return 0,[],f"{type(e).__name__}: {str(e)[:100]}"

def market_regime(nifty):
    if nifty is None or nifty.empty:
        return {"label":"DATA UNAVAILABLE","score":0,"note":"Benchmark history could not be loaded."}
    x=nifty.iloc[-1]
    if x.Close>x.EMA50>x.EMA200: return {"label":"BULLISH","score":70,"note":"Price above 50/200-day trend; selective momentum setups can be considered."}
    if x.Close>x.EMA200: return {"label":"NEUTRAL","score":55,"note":"Mixed trend; require stronger individual setups and tighter risk control."}
    return {"label":"DEFENSIVE","score":35,"note":"Benchmark below long-term trend; marginal setups should be rejected."}

def levels(d):
    x=d.iloc[-1]; close=float(x.Close); atr=float(x.ATR)
    recent_low=float(d.Low.tail(10).min()); recent_high=float(d.High.tail(20).max())
    if close>float(x.High20):
        entry=max(close,float(x.High20)+0.10*atr); stop=max(0.01,entry-1.20*atr); setup="BREAKOUT"
    elif close>x.EMA20 and x.EMA20>x.EMA50 and x.RSI<68:
        entry=close; stop=max(0.01,min(entry-1.50*atr,recent_low-0.20*atr)); setup="TREND CONTINUATION"
    else:
        entry=close; stop=max(0.01,entry-1.50*atr); setup="PULLBACK / WATCH"
    risk=entry-stop
    if risk<=0: return None
    t1=max(recent_high,entry+1.5*risk); t2=max(entry+2.5*risk,t1+0.5*risk)
    return entry,stop,t1,t2,(t2-entry)/risk,(t1-entry)/risk,setup

def _analyze_one(symbol,capital,risk_pct,nifty_ret20):
    d_raw,hist_err=_history(symbol)
    d=indicators(d_raw)
    if len(d)<220:
        return {"error":hist_err or f"only {len(d)} usable rows","symbol":symbol,"stage":"history"}
    # Fundamental/news data are optional. A provider failure must NOT delete a valid
    # technical candidate from the scan.
    info,info_err=safe_info(symbol)
    cat,headlines,news_err=news_catalyst(symbol)
    try:
        tech=technical_score(d); mom=momentum_score(d); fund=fundamental_score(info)
        x=d.iloc[-1]; rs20=float(x.Ret20-nifty_ret20)
        rs_points=5 if rs20>.05 else (3 if rs20>.02 else (1 if rs20>0 else 0))
        sector=info.get("sector") or SECTOR_HINTS.get(symbol,"Unknown")
        lev=levels(d)
        if not lev: return {"error":"invalid risk levels","symbol":symbol,"stage":"levels"}
        entry,stop,t1,t2,rr,rr1,setup=lev
        risk_per_share=entry-stop
        risk_budget=capital*risk_pct/100
        qty=max(0,int(risk_budget/risk_per_share))
        capital_used=qty*entry; max_loss=qty*risk_per_share
        total=int(min(100,tech+mom+fund+cat+5+rs_points))
        dt=d.index[-1]
        if getattr(dt,"tzinfo",None) is not None: dt=dt.tz_convert(None)
        quality=[]
        if info_err: quality.append("fundamentals unavailable")
        if news_err: quality.append("news unavailable")
        quality_label="GOOD" if not quality else "PARTIAL"
        return {
            "symbol":symbol,"score":total,"technical":tech,"momentum":mom,"fundamental":fund,"catalyst":cat,
            "market":int(min(10,5+rs_points)),"setup":setup,"entry":entry,"stop":stop,"target1":t1,"target2":t2,
            "rr":rr,"rr_target1":rr1,"qty":qty,"risk_rupees":risk_budget,"capital_used":capital_used,"max_loss":max_loss,
            "rsi":float(x.RSI),"rel_volume":float(x.Volume/x.Vol20) if x.Vol20 else 0,"ret20":float(x.Ret20),"ret60":float(x.Ret60),
            "rs20":rs20,"turnover20":float(x.Turnover20),"last_price":float(x.Close),"last_date":str(dt.date()),
            "sector":sector,"headlines":headlines,"data_quality":quality_label,"data_notes":", ".join(quality) or "price + model inputs available",
            "thesis":f"{setup} structure; {total}/100 model score; 20D relative strength {rs20*100:.1f} pts vs Nifty.",
            "data_source":"Yahoo Finance / yfinance research feed; verify live price/order details at broker."
        }
    except Exception as e:
        return {"error":f"{type(e).__name__}: {str(e)[:120]}","symbol":symbol,"stage":"scoring"}

def daily_scan(capital,risk_pct,min_score=75,min_rr=2.0,max_results=5):
    nifty_raw,_=_history("^NSEI")
    nifty=indicators(nifty_raw)
    if nifty.empty:
        return {"rows":[],"qualified":[],"near":[],"generated_utc":datetime.now(timezone.utc).isoformat(),"breadth":{"scanned":0,"positive_20d":0,"breakouts":0,"qualified":0},"universe_size":len(NIFTY100),"regime":market_regime(nifty),"diagnostics":{"history_ok":0,"history_failed":len(NIFTY100),"fundamental_partial":0,"news_partial":0,"failures":[{"symbol":s,"stage":"benchmark","error":"NIFTY benchmark unavailable"} for s in NIFTY100]}}
    nifty_ret20=float(nifty.iloc[-1].Ret20)
    results=[]; failures=[]
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs={ex.submit(_analyze_one,s,capital,risk_pct,nifty_ret20):s for s in NIFTY100}
        for f in as_completed(futs):
            try:
                r=f.result()
            except Exception as e:
                r={"symbol":futs[f],"stage":"worker","error":f"{type(e).__name__}: {str(e)[:120]}"}
            if "error" in r: failures.append(r)
            else: results.append(r)
    # Sector overlay uses the median 20D return of successfully analyzed names.
    df=pd.DataFrame(results)
    sector_medians=df.groupby("sector")["ret20"].median().to_dict() if not df.empty else {}
    for r in results:
        sec=sector_medians.get(r["sector"],r["ret20"])
        sec_pts=5 if sec>.05 else (3 if sec>.02 else (1 if sec>0 else 0))
        r["market"]=int(min(10,5+sec_pts))
        r["sector_return20"]=float(sec)
        r["score"]=int(min(100,r["technical"]+r["momentum"]+r["fundamental"]+r["catalyst"]+r["market"]))
        r["qualified"]=bool(r["score"]>=min_score and r["rr"]>=min_rr and r["qty"]>0)
        if r["qualified"]: r["status"]="QUALIFIED"; r["reason"]="Passes score + R:R + position-size checks"
        elif r["score"]>=min_score or r["rr"]>=min_rr: r["status"]="NEAR MISS"; r["reason"]=f"Score {r['score']} vs {min_score} · R:R {r['rr']:.2f} vs {min_rr:.2f}"
        else: r["status"]="REJECTED"; r["reason"]=f"Score {r['score']} < {min_score} · R:R {r['rr']:.2f} < {min_rr:.2f}"
    results.sort(key=lambda z:(z["score"],z["rr"]),reverse=True)
    qualified=[r for r in results if r["qualified"]]
    near=[r for r in results if r["status"]=="NEAR MISS"]
    breadth={"scanned":len(results),"positive_20d":sum(r["ret20"]>0 for r in results),"breakouts":sum(r["setup"]=="BREAKOUT" for r in results),"qualified":len(qualified)}
    partial_f=sum(r["data_quality"]=="PARTIAL" and "fundamentals unavailable" in r["data_notes"] for r in results)
    partial_n=sum(r["data_quality"]=="PARTIAL" and "news unavailable" in r["data_notes"] for r in results)
    return {
        "rows":results,"qualified":qualified[:max_results],"near":near[:max_results],"csv":df.to_csv(index=False) if not df.empty else "No analyzable stocks.\n",
        "generated_utc":datetime.now(timezone.utc).isoformat(),"breadth":breadth,"universe_size":len(NIFTY100),"regime":market_regime(nifty),
        "diagnostics":{"history_ok":len(results),"history_failed":len(failures),"fundamental_partial":partial_f,"news_partial":partial_n,"failures":failures[:30]}
    }
