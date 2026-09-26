import io, time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import yfinance as yf
import requests

NIFTY100_FALLBACK = [
"ADANIENT","ADANIPORTS","APOLLOHOSP","ASIANPAINT","AXISBANK","BAJAJ-AUTO","BAJFINANCE","BAJAJFINSV","BEL","BHARTIARTL","CIPLA","COALINDIA","DRREDDY","EICHERMOT","ETERNAL","GRASIM","HCLTECH","HDFCBANK","HINDALCO","HINDUNILVR","ICICIBANK","INDUSINDBK","INFY","ITC","JIOFIN","JSWENERGY","JSWSTEEL","KOTAKBANK","LT","M&M","MARUTI","NESTLEIND","NTPC","ONGC","POWERGRID","RELIANCE","SBILIFE","SBIN","SHRIRAMFIN","SUNPHARMA","TATACONSUM","TATAMOTORS","TATASTEEL","TCS","TECHM","TITAN","TRENT","ULTRACEMCO","WIPRO","AMBUJACEM","BAJAJHLDNG","BANKBARODA","BERGEPAINT","BPCL","CANBK","CHOLAFIN","COLPAL","DABUR","DIVISLAB","DLF","DMART","GAIL","GODREJCP","GODREJPROP","HAVELLS","HINDPETRO","ICICIGI","ICICIPRULI","INDHOTEL","INDUSTOWER","IOC","IRCTC","JINDALSTEL","LICI","LUPIN","MARICO","MOTHERSON","NAUKRI","PIDILITIND","PNB","POLYCAB","RECLTD","SAIL","SBICARD","SHREECEM","SIEMENS","SRF","TATAPOWER","TORNTPHARM","TVSMOTOR","UBL","UNITEDPHOS","VEDL","VBL","ZOMATO","ZYDUSLIFE"
]


def load_universe():
    url = "https://www.niftyindices.com/IndexConstituent/ind_nifty100list.csv"
    try:
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0","Accept":"text/csv,*/*"}, timeout=15)
        r.raise_for_status()
        df = pd.read_csv(io.BytesIO(r.content))
        col = next((c for c in df.columns if str(c).strip().upper() in {"SYMBOL","SYMBOLS"}), None)
        if col is None:
            col = next((c for c in df.columns if "SYMBOL" in str(c).upper()), None)
        if col:
            syms = [str(x).strip().upper() for x in df[col].dropna()]
            syms = list(dict.fromkeys(syms))
            if len(syms) >= 95:
                return syms[:100], "LIVE NIFTY100 CONSTITUENT CSV"
    except Exception:
        pass
    return NIFTY100_FALLBACK, "FALLBACK NIFTY100 LIST"


def _clean_one(d):
    if d is None or len(d) == 0:
        return pd.DataFrame()
    x = d.copy()
    if isinstance(x.columns, pd.MultiIndex):
        # Flatten the common single-ticker shape.
        if x.columns.nlevels == 2:
            # Pick the level containing OHLCV field names.
            fields = {"Open","High","Low","Close","Adj Close","Volume"}
            for level in range(2):
                vals = [str(v) for v in x.columns.get_level_values(level)]
                if fields.intersection(vals):
                    x.columns = x.columns.get_level_values(level)
                    break
    x.columns = [str(c).strip() for c in x.columns]
    needed = [c for c in ["Open","High","Low","Close","Volume"] if c in x.columns]
    if "Close" not in x.columns:
        return pd.DataFrame()
    x = x[needed].copy()
    for c in needed:
        x[c] = pd.to_numeric(x[c], errors="coerce")
    x = x.replace([np.inf,-np.inf], np.nan).dropna(subset=["Close","High","Low"])
    if "Volume" not in x.columns:
        x["Volume"] = 0.0
    x.index = pd.to_datetime(x.index).tz_localize(None) if getattr(x.index, "tz", None) is not None else pd.to_datetime(x.index)
    return x.sort_index()


def _extract(raw, ticker):
    if raw is None or raw.empty:
        return pd.DataFrame()
    if not isinstance(raw.columns, pd.MultiIndex):
        return _clean_one(raw)
    cols = raw.columns
    for level in range(cols.nlevels):
        vals = set(str(v) for v in cols.get_level_values(level))
        if ticker in vals:
            try:
                d = raw.xs(ticker, axis=1, level=level, drop_level=True)
                return _clean_one(d)
            except Exception:
                pass
    # Some yfinance versions use the ticker without the exchange suffix in a level.
    short = ticker.replace(".NS", "")
    for level in range(cols.nlevels):
        vals = set(str(v) for v in cols.get_level_values(level))
        if short in vals:
            try:
                return _clean_one(raw.xs(short, axis=1, level=level, drop_level=True))
            except Exception:
                pass
    return pd.DataFrame()


def download_prices(symbols, chunk_size=20, retries=2):
    data = {}
    failures = []
    diagnostics = []
    for start in range(0, len(symbols), chunk_size):
        chunk = symbols[start:start+chunk_size]
        tickers = [s + ".NS" for s in chunk]
        ok = False
        last_err = ""
        for attempt in range(retries + 1):
            try:
                raw = yf.download(
                    tickers=tickers,
                    period="2y",
                    interval="1d",
                    auto_adjust=False,
                    group_by="column",
                    threads=False,
                    progress=False,
                    timeout=30,
                )
                found = 0
                for t, s in zip(tickers, chunk):
                    d = _extract(raw, t)
                    if len(d) >= 220:
                        data[s] = d
                        found += 1
                diagnostics.append({"batch": f"{start+1}-{start+len(chunk)}", "requested":len(chunk), "received":found, "attempt":attempt+1})
                if found:
                    ok = True
                    break
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
            time.sleep(1.5 * (attempt + 1))
        if not ok:
            for s in chunk:
                if s not in data:
                    failures.append({"symbol":s,"error":last_err or "NO_USABLE_HISTORY_RETURNED"})
    return data, failures, diagnostics


def indicators(d):
    x = d.copy()
    c,h,l,v = x.Close, x.High, x.Low, x.Volume
    x["EMA20"] = c.ewm(span=20, adjust=False).mean()
    x["EMA50"] = c.ewm(span=50, adjust=False).mean()
    x["EMA200"] = c.ewm(span=200, adjust=False).mean()
    delta = c.diff(); gain=delta.clip(lower=0); loss=-delta.clip(upper=0)
    ag=gain.ewm(alpha=1/14, adjust=False).mean(); al=loss.ewm(alpha=1/14, adjust=False).mean()
    x["RSI"] = 100 - (100/(1+(ag/al.replace(0,np.nan))))
    tr = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    x["ATR"] = tr.ewm(alpha=1/14, adjust=False).mean()
    x["ATRpct"] = x.ATR/c
    x["Vol20"] = v.rolling(20).mean()
    x["High20"] = h.shift(1).rolling(20).max()
    x["Ret20"] = c.pct_change(20)
    x["Ret60"] = c.pct_change(60)
    x["Turnover20"] = (c*v).rolling(20).mean()
    return x.dropna()


def market_regime(rows):
    if not rows:
        return {"label":"DATA UNAVAILABLE","score":0,"note":"No price histories were returned."}
    above50=np.mean([r["close"]>r["ema50"] for r in rows])
    above200=np.mean([r["close"]>r["ema200"] for r in rows])
    positive=np.mean([r["ret20"]>0 for r in rows])
    score=round(100*(0.4*above50+0.4*above200+0.2*positive))
    if score>=70: label="CONSTRUCTIVE"
    elif score>=50: label="SELECTIVE"
    else: label="DEFENSIVE"
    return {"label":label,"score":int(score),"note":f"{above50*100:.0f}% above EMA50 · {above200*100:.0f}% above EMA200 · {positive*100:.0f}% positive over 20D."}


def setup_for(x, rel_rank, capital, risk_pct):
    z=x.iloc[-1]; entry=float(z.Close); atr=float(z.ATR)
    if not np.isfinite(atr) or atr<=0:return None
    breakout = entry > float(z.High20)
    if breakout:
        stop=entry-1.4*atr; setup="BREAKOUT"
    else:
        stop=min(entry-1.6*atr, float(x.Low.tail(10).min())-0.15*atr); setup="TREND"
    if stop<=0 or entry<=stop:return None
    risk=entry-stop; t1=entry+1.5*risk; t2=entry+2.5*risk; rr=(t2-entry)/risk
    risk_rupees=capital*risk_pct/100; qty=int(risk_rupees/risk)
    if qty<=0:return None
    trend=(entry>z.EMA20>z.EMA50>z.EMA200)
    trend_score=30 if trend else (22 if entry>z.EMA50>z.EMA200 else (14 if entry>z.EMA200 else 5))
    mom_score=min(25,max(0, round((z.Ret20/0.10)*15 + (z.Ret60/0.20)*10)))
    break_score=20 if breakout and z.Volume>1.3*z.Vol20 else (14 if breakout else (8 if entry>z.EMA20 else 2))
    rs_score=round(15*rel_rank)
    atr_score=10 if 0.015<=z.ATRpct<=0.045 else (6 if z.ATRpct<0.06 else 2)
    score=int(min(100,max(0,trend_score+mom_score+break_score+rs_score+atr_score)))
    return {"technical":trend_score,"momentum":mom_score,"breakout":break_score,"relative":rs_score,"risk":atr_score,"score":score,"entry":entry,"stop":stop,"target1":t1,"target2":t2,"rr":rr,"qty":qty,"max_loss":qty*risk,"capital_used":qty*entry,"setup":setup,"rsi":float(z.RSI),"relative_volume":float(z.Volume/z.Vol20) if z.Vol20 else 0,"ret20":float(z.Ret20),"ret60":float(z.Ret60),"atr_pct":float(z.ATRpct),"last_price":entry,"last_date":str(x.index[-1].date())}


def scan(capital,risk_pct,min_score,min_rr,max_plans):
    symbols, source = load_universe()
    data, failures, diagnostics = download_prices(symbols)
    base=[]
    for s,d in data.items():
        x=indicators(d)
        if len(x)<220:
            failures.append({"symbol":s,"error":f"ONLY_{len(x)}_USABLE_ROWS"}); continue
        z=x.iloc[-1]
        base.append({"symbol":s,"close":float(z.Close),"ema50":float(z.EMA50),"ema200":float(z.EMA200),"ret20":float(z.Ret20)})
    base_sorted=sorted(base,key=lambda r:r["ret20"])
    n=max(1,len(base_sorted)-1)
    rank={r["symbol"]:i/n for i,r in enumerate(base_sorted)}
    rows=[]
    backtests=[]
    for s,d in data.items():
        x=indicators(d)
        if len(x)<220: continue
        r=setup_for(x,rank.get(s,0.5),capital,risk_pct)
        if r:
            bt=backtest(d)
            if bt and bt["trades"]:
                backtests.append({"symbol":s,**bt})
            r["symbol"]=s
            r["qualified"]=r["score"]>=min_score and r["rr"]>=min_rr
            r["status"]="QUALIFIED" if r["qualified"] else ("NEAR MISS" if r["score"]>=min_score or r["rr"]>=min_rr else "REJECTED")
            r["reason"]=f"Score {r['score']}/{min_score} · R:R {r['rr']:.2f}/{min_rr}"
            rows.append(r)
    rows.sort(key=lambda r:(r["score"],r["rr"]),reverse=True)
    q=[r for r in rows if r["qualified"]][:max_plans]
    near=[r for r in rows if r["status"]=="NEAR MISS"][:max_plans]
    regime=market_regime(base)
    return {"symbols":symbols,"source":source,"rows":rows,"qualified":q,"near":near,"failures":failures,"diagnostics":diagnostics,"regime":regime,"generated":datetime.now(timezone.utc).isoformat(),"analyzed":len(data),"universe":len(symbols),"backtests":backtests}


def backtest(d, min_score=70, hold=15):
    x=indicators(d)
    if len(x)<260:return None
    trades=[]
    # Simple walk-forward: signal at close; enter next day's open. Stop/target are ATR based.
    for i in range(220,len(x)-hold-1):
        z=x.iloc[i]
        trend=z.Close>z.EMA20>z.EMA50>z.EMA200
        breakout=z.Close>z.High20 and z.Volume>1.3*z.Vol20
        mom=z.Ret20>0.03 and z.Ret60>0.05
        if not ((trend and mom) or (breakout and mom)):
            continue
        entry=float(x.iloc[i+1].Open)
        atr=float(z.ATR)
        if not np.isfinite(entry) or not np.isfinite(atr) or atr<=0:continue
        stop=entry-1.5*atr; target=entry+3*1.5*atr
        exit_price=float(x.iloc[min(i+hold,len(x)-1)].Close); outcome="TIME"
        for j in range(i+1,min(i+hold+1,len(x))):
            lo=float(x.iloc[j].Low); hi=float(x.iloc[j].High)
            if lo<=stop and hi>=target:
                exit_price=stop; outcome="STOP_FIRST_CONSERVATIVE"; break
            if lo<=stop:
                exit_price=stop; outcome="STOP"; break
            if hi>=target:
                exit_price=target; outcome="TARGET"; break
            exit_price=float(x.iloc[j].Close)
        r=(exit_price-entry)/(entry-stop)
        trades.append(r)
    if not trades:return {"trades":0,"win_rate":0,"avg_r":0,"total_r":0,"profit_factor":0}
    wins=[r for r in trades if r>0]; gains=sum(r for r in trades if r>0); losses=-sum(r for r in trades if r<0)
    return {"trades":len(trades),"win_rate":100*len(wins)/len(trades),"avg_r":float(np.mean(trades)),"total_r":float(np.sum(trades)),"profit_factor":float(gains/losses) if losses else float("inf")}
