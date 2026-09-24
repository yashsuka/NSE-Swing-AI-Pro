import pandas as pd
import numpy as np
import yfinance as yf

NIFTY50=["ADANIENT","ADANIPORTS","APOLLOHOSP","ASIANPAINT","AXISBANK","BAJAJ-AUTO","BAJFINANCE","BAJAJFINSV","BEL","BHARTIARTL","CIPLA","COALINDIA","DRREDDY","EICHERMOT","ETERNAL","GRASIM","HCLTECH","HDFCBANK","HINDALCO","HINDUNILVR","ICICIBANK","INDUSINDBK","INFY","ITC","JIOFIN","JSWSTEEL","KOTAKBANK","LT","M&M","MARUTI","NESTLEIND","NTPC","ONGC","POWERGRID","RELIANCE","SBILIFE","SBIN","SHRIRAMFIN","SUNPHARMA","TATACONSUM","TATAMOTORS","TATASTEEL","TCS","TECHM","TITAN","TRENT","ULTRACEMCO","WIPRO"]
POS={"upgrade","upgraded","buy","bullish","growth","strong","record","beat","beats","surge","order","contract","expansion","positive","outperform"}
NEG={"downgrade","downgraded","sell","bearish","weak","miss","misses","fall","falls","cut","lawsuit","probe","loss","negative","warning"}

def ticker(s): return yf.Ticker(s+".NS")
def history(s): return ticker(s).history(period="1y",auto_adjust=False)

def add_indicators(df):
    d=df.copy(); c=d.Close; h=d.High; l=d.Low; v=d.Volume
    d["EMA20"]=c.ewm(span=20,adjust=False).mean(); d["EMA50"]=c.ewm(span=50,adjust=False).mean(); d["EMA200"]=c.ewm(span=200,adjust=False).mean()
    delta=c.diff(); gain=delta.clip(lower=0).rolling(14).mean(); loss=(-delta.clip(upper=0)).rolling(14).mean()
    d["RSI"]=100-(100/(1+(gain/loss.replace(0,np.nan))))
    e12=c.ewm(span=12,adjust=False).mean(); e26=c.ewm(span=26,adjust=False).mean()
    d["MACD"]=e12-e26; d["MACDsig"]=d.MACD.ewm(span=9,adjust=False).mean()
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    d["ATR"]=tr.rolling(14).mean(); d["Vol20"]=v.rolling(20).mean(); d["High20"]=h.shift(1).rolling(20).max(); d["Low20"]=l.shift(1).rolling(20).min()
    return d.dropna()

def technical_score(d):
    x=d.iloc[-1]; s=0
    s+=8 if x.Close>x.EMA20 else 0; s+=7 if x.EMA20>x.EMA50 else 0; s+=5 if x.EMA50>x.EMA200 else 0
    s+=5 if 50<=x.RSI<=70 else (2 if 45<=x.RSI<50 else 0); s+=5 if x.MACD>x.MACDsig else 0; s+=5 if x.Close>x.High20 else 0
    return int(s)

def momentum_score(d):
    x=d.iloc[-1]; r20=d.Close.iloc[-1]/d.Close.iloc[-21]-1; r60=d.Close.iloc[-1]/d.Close.iloc[-61]-1; s=0
    s+=5 if r20>.05 else (3 if r20>.02 else 0); s+=5 if r60>.08 else (3 if r60>.03 else 0)
    s+=5 if x.Volume>x.Vol20*1.2 else (2 if x.Volume>x.Vol20 else 0)
    return int(s)

def fundamental_score(info):
    s=0; roe=info.get("returnOnEquity"); margin=info.get("profitMargins"); growth=info.get("earningsGrowth"); debt=info.get("debtToEquity")
    s+=7 if isinstance(roe,(int,float)) and roe>.15 else (3 if isinstance(roe,(int,float)) and roe>.08 else 0)
    s+=5 if isinstance(margin,(int,float)) and margin>.08 else (2 if isinstance(margin,(int,float)) and margin>0 else 0)
    s+=5 if isinstance(growth,(int,float)) and growth>.05 else (2 if isinstance(growth,(int,float)) and growth>0 else 0)
    s+=3 if not isinstance(debt,(int,float)) or debt<150 else 0
    return int(s)

def catalyst_score(symbol):
    try:
        news=ticker(symbol).news or []; p=n=0
        for item in news[:10]:
            title=str(item.get("title","")).lower()
            p+=sum(w in title for w in POS); n+=sum(w in title for w in NEG)
        return 10 if p>=3 and p>n else (7 if p>=2 and p>n else (4 if p==1 and p>n else 0))
    except Exception: return 0

def market_sector_score(d,n):
    s=0; x=d.iloc[-1]; nx=n.iloc[-1]
    s+=3 if nx.Close>nx.EMA50 else 0; s+=2 if nx.EMA50>nx.EMA200 else 0
    rel=(d.Close.iloc[-1]/d.Close.iloc[-21]-1)-(n.Close.iloc[-1]/n.Close.iloc[-21]-1)
    s+=5 if rel>.05 else (3 if rel>.02 else (1 if rel>0 else 0))
    return int(s)

def market_regime():
    try:
        d=add_indicators(yf.Ticker("^NSEI").history(period="1y",auto_adjust=False)); x=d.iloc[-1]
        if x.Close>x.EMA50>x.EMA200: return {"label":"Bullish / constructive","score":70}
        if x.Close>x.EMA200: return {"label":"Neutral / selective","score":55}
        return {"label":"Defensive","score":35}
    except Exception: return {"label":"Data unavailable","score":0}

def levels(d):
    x=d.iloc[-1]; entry=float(x.Close); atr=float(x.ATR); recent_low=float(d.Low.tail(10).min()); recent_high=float(d.High.tail(20).max())
    if entry>float(x.High20):
        stop=max(.01,min(entry-1.2*atr,float(x.High20)-.5*atr)); base=max(atr,float(x.High20)-float(d.Low20.iloc[-1]))
        t1=entry+.8*base; t2=entry+1.4*base; setup="BREAKOUT"
    else:
        stop=max(.01,min(entry-1.5*atr,recent_low-.2*atr)); risk=entry-stop
        t1=max(recent_high,entry+1.5*risk); t2=max(entry+2.5*risk,t1+.5*risk); setup="TREND_CONTINUATION"
    risk=entry-stop
    return entry,stop,t1,t2,(t2-entry)/risk,(t1-entry)/risk,setup

def analyze(symbol,capital,risk_pct,nifty):
    try:
        d=add_indicators(history(symbol))
        if len(d)<220:return None
        info=ticker(symbol).info; tech=technical_score(d); mom=momentum_score(d); fund=fundamental_score(info); cat=catalyst_score(symbol); market=market_sector_score(d,nifty)
        entry,stop,t1,t2,rr,rr1,setup=levels(d); risk=entry-stop
        if risk<=0:return None
        qty=max(0,int((capital*risk_pct/100)/risk)); total=min(100,tech+mom+fund+cat+market)
        return {"symbol":symbol,"score":int(total),"technical":tech,"momentum":mom,"fundamental":fund,"catalyst":cat,"market":market,"setup":setup,"entry":entry,"stop":stop,"target1":t1,"target2":t2,"rr":rr,"rr_target1":rr1,"qty":qty,"rsi":float(d.iloc[-1].RSI),"relative_volume":float(d.iloc[-1].Volume/d.iloc[-1].Vol20) if d.iloc[-1].Vol20 else 0,"thesis":f"{symbol} has a {setup.lower()} structure with a {int(total)}/100 model score.","risk":"Research output only; gaps, slippage, liquidity, taxes and data errors can change actual execution."}
    except Exception:return None

def daily_scan(capital,risk_pct,min_score=75,min_rr=2.0):
    nifty=add_indicators(yf.Ticker("^NSEI").history(period="1y",auto_adjust=False)); rows=[]
    for s in NIFTY50:
        r=analyze(s,capital,risk_pct,nifty)
        if not r: continue
        r["qualified"]=r["score"]>=min_score and r["rr"]>=min_rr
        if r["qualified"]: r["status"]="QUALIFIED"; r["reason"]="Passes score and R:R filters"
        elif r["score"]>=min_score: r["status"]="NEAR MISS"; r["reason"]=f"Score passes; R:R {r['rr']:.2f} < {min_rr:.2f}"
        elif r["rr"]>=min_rr: r["status"]="NEAR MISS"; r["reason"]=f"R:R passes; score {r['score']} < {min_score}"
        else: r["status"]="REJECTED"; r["reason"]=f"Score {r['score']} < {min_score}; R:R {r['rr']:.2f} < {min_rr:.2f}"
        rows.append(r)
    rows.sort(key=lambda z:(z["score"],z["rr"]),reverse=True); q=[r for r in rows if r["qualified"]]
    return {"top3":q[:3],"candidates":rows[:3],"all":rows,"csv":pd.DataFrame(rows).to_csv(index=False) if rows else "No analyzable stocks today.\n","qualified_count":len(q)}
