import io, math
import pandas as pd
import numpy as np
import yfinance as yf

NIFTY50 = [
"ADANIENT","ADANIPORTS","APOLLOHOSP","ASIANPAINT","AXISBANK","BAJAJ-AUTO",
"BAJFINANCE","BAJAJFINSV","BEL","BHARTIARTL","CIPLA","COALINDIA","DRREDDY",
"EICHERMOT","ETERNAL","GRASIM","HCLTECH","HDFCBANK","HINDALCO","HINDUNILVR",
"ICICIBANK","INDUSINDBK","INFY","ITC","JIOFIN","JSWSTEEL","KOTAKBANK",
"LT","M&M","MARUTI","NESTLEIND","NTPC","ONGC","POWERGRID","RELIANCE",
"SBILIFE","SBIN","SHRIRAMFIN","SUNPHARMA","TATACONSUM","TATAMOTORS",
"TATASTEEL","TCS","TECHM","TITAN","TRENT","ULTRACEMCO","WIPRO"
]

def _ticker(symbol):
    return yf.Ticker(symbol + ".NS")

def _history(symbol, period="1y"):
    return _ticker(symbol).history(period=period, auto_adjust=False)

def indicators(df):
    d=df.copy()
    close=d["Close"]
    high=d["High"]; low=d["Low"]; vol=d["Volume"]
    d["EMA20"]=close.ewm(span=20, adjust=False).mean()
    d["EMA50"]=close.ewm(span=50, adjust=False).mean()
    d["EMA200"]=close.ewm(span=200, adjust=False).mean()
    delta=close.diff()
    gain=delta.clip(lower=0).rolling(14).mean()
    loss=(-delta.clip(upper=0)).rolling(14).mean()
    rs=gain/loss.replace(0,np.nan)
    d["RSI"]=100-(100/(1+rs))
    ema12=close.ewm(span=12,adjust=False).mean()
    ema26=close.ewm(span=26,adjust=False).mean()
    d["MACD"]=ema12-ema26
    d["MACDsig"]=d["MACD"].ewm(span=9,adjust=False).mean()
    tr=pd.concat([high-low,(high-close.shift()).abs(),(low-close.shift()).abs()],axis=1).max(axis=1)
    d["ATR"]=tr.rolling(14).mean()
    d["Vol20"]=vol.rolling(20).mean()
    d["High20"]=high.shift(1).rolling(20).max()
    return d.dropna()

def technical_score(d):
    x=d.iloc[-1]; score=0
    score += 8 if x.Close>x.EMA20 else 0
    score += 7 if x.EMA20>x.EMA50 else 0
    score += 5 if x.EMA50>x.EMA200 else 0
    score += 5 if 50<=x.RSI<=70 else (2 if 45<=x.RSI<50 else 0)
    score += 5 if x.MACD>x.MACDsig else 0
    score += 5 if x.Close>x.High20 else 0
    return score

def momentum_score(d):
    x=d.iloc[-1]; score=0
    score += 5 if x.Close>x.Close.shift if False else 0
    ret20=(d.Close.iloc[-1]/d.Close.iloc[-21]-1)
    ret60=(d.Close.iloc[-1]/d.Close.iloc[-61]-1) if len(d)>61 else 0
    score += 5 if ret20>0.05 else (3 if ret20>0.02 else 0)
    score += 5 if ret60>0.08 else (3 if ret60>0.03 else 0)
    score += 5 if x.Volume>x.Vol20*1.2 else (2 if x.Volume>x.Vol20 else 0)
    return score

def fundamental_score(info):
    score=0
    roe=info.get("returnOnEquity")
    margin=info.get("profitMargins")
    growth=info.get("earningsGrowth")
    debt=info.get("debtToEquity")
    score += 7 if isinstance(roe,(int,float)) and roe>0.15 else 3 if isinstance(roe,(int,float)) and roe>0.08 else 0
    score += 5 if isinstance(margin,(int,float)) and margin>0.08 else 2 if isinstance(margin,(int,float)) and margin>0 else 0
    score += 5 if isinstance(growth,(int,float)) and growth>0.05 else 2 if isinstance(growth,(int,float)) and growth>0 else 0
    score += 3 if not isinstance(debt,(int,float)) or debt<150 else 0
    return score

def market_regime():
    try:
        d=indicators(_history("^NSEI".replace("^NSEI","^NSEI")))
        x=d.iloc[-1]
        score=70 if x.Close>x.EMA50 and x.EMA50>x.EMA200 else 40
        return {"label":"Bullish / constructive" if score>=60 else "Neutral / defensive","score":score}
    except Exception:
        return {"label":"Data unavailable","score":0}

def analyze(symbol, capital, risk_pct):
    try:
        raw=_history(symbol)
        d=indicators(raw)
        if len(d)<220: return None
        x=d.iloc[-1]
        t=technical_score(d)
        m=momentum_score(d)
        info=_ticker(symbol).info
        f=fundamental_score(info)
        catalyst=5 if info.get("recommendationKey") else 0
        market=5 if x.Close>x.EMA50 else 0
        total=min(100,t+m+f+catalyst+market)
        entry=float(x.Close)
        atr=float(x.ATR)
        stop=entry-1.5*atr
        target1=entry+2*(entry-stop)
        target2=entry+3*(entry-stop)
        rr=(target2-entry)/(entry-stop) if entry>stop else 0
        risk_rupees=capital*risk_pct/100
        qty=max(0,int(risk_rupees/(entry-stop))) if entry>stop else 0
        setup="BREAKOUT" if x.Close>x.High20 else "TREND_CONTINUATION"
        return {
            "symbol":symbol,"score":int(total),"setup":setup,"entry":entry,
            "stop":stop,"target1":target1,"target2":target2,"rr":rr,"qty":qty,
            "rsi":float(x.RSI),"thesis":f"{symbol} shows {setup.lower()} characteristics with a model score of {int(total)}/100.",
            "risk":"Invalidation below the stop; model does not account for overnight gaps or execution slippage."
        }
    except Exception:
        return None

def daily_scan(capital, risk_pct, min_score=75, min_rr=2.0):
    rows=[]
    for s in NIFTY50:
        a=analyze(s,capital,risk_pct)
        if a and a["score"]>=min_score and a["rr"]>=min_rr:
            rows.append(a)
    rows=sorted(rows,key=lambda z:(z["score"],z["rr"]),reverse=True)
    top3=rows[:3]
    df=pd.DataFrame(rows)
    csv=df.to_csv(index=False) if len(df) else "No qualified setups today.\n"
    return {"top3":top3,"all":rows,"csv":csv}
