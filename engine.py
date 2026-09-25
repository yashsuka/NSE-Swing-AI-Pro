import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone
import time

NIFTY100 = [
"ADANIENT","ADANIPORTS","APOLLOHOSP","ASIANPAINT","AXISBANK","BAJAJ-AUTO","BAJFINANCE","BAJAJFINSV","BEL","BHARTIARTL","CIPLA","COALINDIA","DRREDDY","EICHERMOT","ETERNAL","GRASIM","HCLTECH","HDFCBANK","HINDALCO","HINDUNILVR","ICICIBANK","INDUSINDBK","INFY","ITC","JIOFIN","JSWENERGY","JSWSTEEL","KOTAKBANK","LT","M&M","MARUTI","NESTLEIND","NTPC","ONGC","POWERGRID","RELIANCE","SBILIFE","SBIN","SHRIRAMFIN","SUNPHARMA","TATACONSUM","TATAMOTORS","TATASTEEL","TCS","TECHM","TITAN","TRENT","ULTRACEMCO","WIPRO","AMBUJACEM","BAJAJHLDNG","BANKBARODA","BERGEPAINT","BPCL","CANBK","CHOLAFIN","COLPAL","DABUR","DIVISLAB","DLF","DMART","GAIL","GODREJCP","GODREJPROP","HAVELLS","HINDPETRO","ICICIGI","ICICIPRULI","INDHOTEL","INDUSTOWER","IOC","IRCTC","JINDALSTEL","LICI","LUPIN","MARICO","MCDOWELL-N","MOTHERSON","NAUKRI","PIDILITIND","PNB","POLYCAB","RECLTD","SAIL","SBICARD","SHREECEM","SIEMENS","SRF","TATAPOWER","TORNTPHARM","TVSMOTOR","UBL","UNITEDPHOS","VEDL","VBL","ZOMATO","ZYDUSLIFE","TMCV","TMPV"]
NIFTY100=list(dict.fromkeys(NIFTY100))

def ys(s): return s+".NS"

def _extract(raw, ticker):
    if raw is None or raw.empty or not isinstance(raw.columns,pd.MultiIndex): return pd.DataFrame()
    levels=[raw.columns.get_level_values(i) for i in range(2)]
    for tl in range(2):
        try:
            if ticker in set(levels[tl]):
                d=raw.xs(ticker,axis=1,level=tl,drop_level=True)
                if "Close" in d.columns: return d.dropna(subset=["Close"])
        except Exception: pass
    return pd.DataFrame()

def batch_price_data(symbols):
    tickers=[ys(s) for s in symbols]+["^NSEI"]
    try:
        raw=yf.download(tickers=tickers,period="1y",interval="1d",auto_adjust=False,group_by="column",threads=False,progress=False,timeout=30)
        data={s:_extract(raw,ys(s)) for s in symbols}
        bench=_extract(raw,"^NSEI")
        return {k:v for k,v in data.items() if not v.empty},bench,None
    except Exception as e:
        return {},pd.DataFrame(),f"{type(e).__name__}: {e}"

def ind(d):
    x=d.copy(); c=x.Close; h=x.High; l=x.Low; v=x.Volume
    x["EMA20"]=c.ewm(span=20,adjust=False).mean(); x["EMA50"]=c.ewm(span=50,adjust=False).mean(); x["EMA200"]=c.ewm(span=200,adjust=False).mean()
    de=c.diff(); g=de.clip(lower=0).rolling(14).mean(); loss=(-de.clip(upper=0)).rolling(14).mean(); x["RSI"]=100-(100/(1+g/loss.replace(0,np.nan)))
    e12=c.ewm(span=12,adjust=False).mean(); e26=c.ewm(span=26,adjust=False).mean(); x["MACD"]=e12-e26; x["MACDsig"]=x.MACD.ewm(span=9,adjust=False).mean()
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1); x["ATR"]=tr.rolling(14).mean(); x["Vol20"]=v.rolling(20).mean(); x["High20"]=h.shift(1).rolling(20).max(); x["Low20"]=l.shift(1).rolling(20).min(); x["Turnover20"]=(c*v).rolling(20).mean(); x["Ret20"]=c.pct_change(20); x["Ret60"]=c.pct_change(60)
    return x.dropna()

def regime(b):
    if b is None or b.empty or len(b)<220: return {"label":"DATA UNAVAILABLE","score":0,"note":"Nifty benchmark history unavailable."}
    x=ind(b); z=x.iloc[-1]
    if z.Close>z.EMA50>z.EMA200:return {"label":"BULLISH / CONSTRUCTIVE","score":70,"note":"Benchmark above medium- and long-term trend."}
    if z.Close>z.EMA200:return {"label":"NEUTRAL / SELECTIVE","score":55,"note":"Benchmark above long-term trend but not fully aligned."}
    return {"label":"DEFENSIVE","score":35,"note":"Benchmark below long-term trend; marginal setups should be rejected."}

def technical(x):
    z=x.iloc[-1]; return int((8 if z.Close>z.EMA20 else 0)+(7 if z.EMA20>z.EMA50 else 0)+(5 if z.EMA50>z.EMA200 else 0)+(5 if 50<=z.RSI<=70 else (2 if 45<=z.RSI<50 else 0))+(5 if z.MACD>z.MACDsig else 0)+(5 if z.Close>z.High20 else 0))

def momentum(x):
    z=x.iloc[-1]; return int((5 if z.Ret20>.05 else (3 if z.Ret20>.02 else 0))+(5 if z.Ret60>.08 else (3 if z.Ret60>.03 else 0))+(5 if z.Volume>z.Vol20*1.2 else (2 if z.Volume>z.Vol20 else 0)))

def relscore(x,b):
    if b is None or b.empty:return 0
    bz=ind(b).iloc[-1]; z=x.iloc[-1]; rel=z.Ret20-bz.Ret20
    return int((5 if rel>.05 else (3 if rel>.02 else (1 if rel>0 else 0)))+(3 if bz.Close>bz.EMA50 else 0)+(2 if bz.EMA50>bz.EMA200 else 0))

def levels(x):
    z=x.iloc[-1]; entry=float(z.Close); atr=float(z.ATR)
    if not np.isfinite(atr) or atr<=0:return None
    lo=float(x.Low.tail(10).min()); hi=float(x.High.tail(20).max())
    if entry>float(z.High20): entry=max(entry,float(z.High20)+.1*atr); stop=entry-1.2*atr; setup="BREAKOUT"
    else: stop=min(entry-1.5*atr,lo-.2*atr); setup="TREND CONTINUATION"
    if stop<=0 or entry<=stop:return None
    risk=entry-stop; t1=max(hi,entry+1.5*risk); t2=max(entry+2.5*risk,t1+.5*risk)
    return entry,stop,t1,t2,(t2-entry)/risk,(t1-entry)/risk,setup

def price_analyze(symbol,d,bench,capital,risk_pct):
    try:
        x=ind(d)
        if len(x)<220:return None,"INSUFFICIENT_HISTORY"
        lev=levels(x)
        if not lev:return None,"INVALID_LEVELS"
        entry,stop,t1,t2,rr,rr1,setup=lev; z=x.iloc[-1]; tech=technical(x); mom=momentum(x); market=relscore(x,bench); qty=int((capital*risk_pct/100)/(entry-stop))
        if qty<=0:return None,"POSITION_SIZE_ZERO"
        return {"symbol":symbol,"technical":tech,"momentum":mom,"market":market,"fundamental":10,"catalyst":5,"score_base":tech+mom+market,"score":min(100,tech+mom+market+15),"setup":setup,"entry":entry,"stop":stop,"target1":t1,"target2":t2,"rr":rr,"rr_target1":rr1,"qty":qty,"risk_rupees":capital*risk_pct/100,"max_loss":qty*(entry-stop),"capital_used":qty*entry,"rsi":float(z.RSI),"relative_volume":float(z.Volume/z.Vol20) if z.Vol20 else 0,"ret20":float(z.Ret20),"ret60":float(z.Ret60),"avg_turnover20":float(z.Turnover20),"last_price":float(z.Close),"last_date":str(x.index[-1].date()),"data_quality":"PRICE VERIFIED / OPTIONAL LAYERS DEFERRED","fundamental_status":"DEFERRED","catalyst_status":"DEFERRED"},None
    except Exception as e:return None,f"{type(e).__name__}: {e}"

def optional_enrich(rows):
    # Only a small shortlist uses extra Yahoo endpoints. Failures never remove a row.
    for r in rows[:12]:
        try:
            news=yf.Ticker(ys(r["symbol"])).news or []
            pos={"upgrade","upgraded","buy","bullish","growth","strong","record","beat","beats","surge","order","contract","expansion","positive","outperform"}; neg={"downgrade","downgraded","sell","bearish","weak","miss","misses","fall","falls","cut","lawsuit","probe","loss","negative","warning"}; p=n=0
            for q in news[:8]:
                title=str(q.get("title","")).lower(); p+=sum(w in title for w in pos); n+=sum(w in title for w in neg)
            r["catalyst"]=10 if p>=3 and p>n else (7 if p>=2 and p>n else (4 if p==1 and p>n else 0)); r["catalyst_status"]="LOADED"
        except Exception:r["catalyst_status"]="UNAVAILABLE"
        # Do not call .info/.financials on 100 stocks. Keep a transparent neutral placeholder.
        r["fundamental_status"]="DEFERRED"; r["score"]=min(100,r["technical"]+r["momentum"]+r["market"]+r["fundamental"]+r["catalyst"]); time.sleep(.1)

def daily_scan(capital,risk_pct,min_score=75,min_rr=2,max_results=5):
    data,bench,bulk_error=batch_price_data(NIFTY100); rows=[]; failures=[]
    if bulk_error: failures=[{"symbol":s,"error":"BULK_PRICE_DOWNLOAD_FAILED: "+bulk_error} for s in NIFTY100]
    else:
        for s in NIFTY100:
            d=data.get(s)
            if d is None or d.empty: failures.append({"symbol":s,"error":"NO_PRICE_HISTORY"}); continue
            r,e=price_analyze(s,d,bench,capital,risk_pct)
            if r is None: failures.append({"symbol":s,"error":e}); continue
            rows.append(r)
    rows.sort(key=lambda r:(r["score_base"],r["rr"]),reverse=True); optional_enrich(rows)
    for r in rows:
        r["qualified"]=r["score"]>=min_score and r["rr"]>=min_rr and r["qty"]>0
        r["status"]="QUALIFIED" if r["qualified"] else ("NEAR MISS" if r["score"]>=min_score or r["rr"]>=min_rr else "REJECTED")
        r["reason"]=f"Score {r['score']}/100 vs {min_score}; R:R {r['rr']:.2f} vs {min_rr:.2f}; data {r['data_quality']}."
    q=[r for r in rows if r["qualified"]]; near=[r for r in rows if r["status"]=="NEAR MISS"]
    return {"top5":q[:max_results],"near_misses":near[:max_results],"all":rows,"failures":failures,"analyzed_count":len(rows),"qualified_count":len(q),"universe_size":len(NIFTY100),"bulk_error":bulk_error,"regime":regime(bench),"generated_utc":datetime.now(timezone.utc).isoformat(),"csv":pd.DataFrame(rows).to_csv(index=False) if rows else "No analyzable stocks.\n"}
