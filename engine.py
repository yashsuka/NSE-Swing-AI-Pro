import io
import pandas as pd
import numpy as np
import yfinance as yf

NIFTY50 = [
    "ADANIENT","ADANIPORTS","APOLLOHOSP","ASIANPAINT","AXISBANK",
    "BAJAJ-AUTO","BAJFINANCE","BAJAJFINSV","BEL","BHARTIARTL",
    "CIPLA","COALINDIA","DRREDDY","EICHERMOT","ETERNAL","GRASIM",
    "HCLTECH","HDFCBANK","HINDALCO","HINDUNILVR","ICICIBANK",
    "INDUSINDBK","INFY","ITC","JIOFIN","JSWSTEEL","KOTAKBANK",
    "LT","M&M","MARUTI","NESTLEIND","NTPC","ONGC","POWERGRID",
    "RELIANCE","SBILIFE","SBIN","SHRIRAMFIN","SUNPHARMA",
    "TATACONSUM","TATAMOTORS","TATASTEEL","TCS","TECHM","TITAN",
    "TRENT","ULTRACEMCO","WIPRO"
]

def ticker(symbol):
    return yf.Ticker(symbol + ".NS")

def history(symbol, period="1y"):
    return ticker(symbol).history(period=period, auto_adjust=False)

def add_indicators(df):
    d = df.copy()
    close = d["Close"]
    high = d["High"]
    low = d["Low"]
    volume = d["Volume"]

    d["EMA20"] = close.ewm(span=20, adjust=False).mean()
    d["EMA50"] = close.ewm(span=50, adjust=False).mean()
    d["EMA200"] = close.ewm(span=200, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    d["RSI"] = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    d["MACD"] = ema12 - ema26
    d["MACDsig"] = d["MACD"].ewm(span=9, adjust=False).mean()

    true_range = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    d["ATR"] = true_range.rolling(14).mean()
    d["Vol20"] = volume.rolling(20).mean()
    d["High20"] = high.shift(1).rolling(20).max()

    return d.dropna()

def technical_score(d):
    x = d.iloc[-1]
    score = 0
    if x["Close"] > x["EMA20"]:
        score += 8
    if x["EMA20"] > x["EMA50"]:
        score += 7
    if x["EMA50"] > x["EMA200"]:
        score += 5
    if 50 <= x["RSI"] <= 70:
        score += 5
    elif 45 <= x["RSI"] < 50:
        score += 2
    if x["MACD"] > x["MACDsig"]:
        score += 5
    if x["Close"] > x["High20"]:
        score += 5
    return score

def momentum_score(d):
    x = d.iloc[-1]
    score = 0

    ret20 = float(d["Close"].iloc[-1] / d["Close"].iloc[-21] - 1)
    ret60 = float(d["Close"].iloc[-1] / d["Close"].iloc[-61] - 1)

    if ret20 > 0.05:
        score += 5
    elif ret20 > 0.02:
        score += 3

    if ret60 > 0.08:
        score += 5
    elif ret60 > 0.03:
        score += 3

    if x["Volume"] > x["Vol20"] * 1.2:
        score += 5
    elif x["Volume"] > x["Vol20"]:
        score += 2

    return score

def fundamental_score(info):
    score = 0
    roe = info.get("returnOnEquity")
    margin = info.get("profitMargins")
    growth = info.get("earningsGrowth")
    debt = info.get("debtToEquity")

    if isinstance(roe, (int, float)):
        if roe > 0.15:
            score += 7
        elif roe > 0.08:
            score += 3

    if isinstance(margin, (int, float)):
        if margin > 0.08:
            score += 5
        elif margin > 0:
            score += 2

    if isinstance(growth, (int, float)):
        if growth > 0.05:
            score += 5
        elif growth > 0:
            score += 2

    if not isinstance(debt, (int, float)) or debt < 150:
        score += 3

    return score

def market_regime():
    try:
        d = add_indicators(yf.Ticker("^NSEI").history(period="1y", auto_adjust=False))
        if len(d) < 200:
            return {"label": "Data unavailable", "score": 0}
        x = d.iloc[-1]
        if x["Close"] > x["EMA50"] > x["EMA200"]:
            return {"label": "Bullish / constructive", "score": 70}
        if x["Close"] > x["EMA200"]:
            return {"label": "Neutral / selective", "score": 55}
        return {"label": "Defensive", "score": 35}
    except Exception:
        return {"label": "Data unavailable", "score": 0}

def analyze(symbol, capital, risk_pct):
    try:
        raw = history(symbol)
        if raw.empty:
            return None

        d = add_indicators(raw)
        if len(d) < 220:
            return None

        x = d.iloc[-1]
        info = ticker(symbol).info

        technical = technical_score(d)
        momentum = momentum_score(d)
        fundamentals = fundamental_score(info)
        catalyst = 5 if info.get("recommendationKey") else 0
        market = 5 if x["Close"] > x["EMA50"] else 0

        score = min(100, technical + momentum + fundamentals + catalyst + market)

        entry = float(x["Close"])
        atr = float(x["ATR"])
        stop = entry - 1.5 * atr

        if stop <= 0 or entry <= stop:
            return None

        target1 = entry + 2 * (entry - stop)
        target2 = entry + 3 * (entry - stop)
        rr = (target2 - entry) / (entry - stop)

        risk_rupees = capital * risk_pct / 100
        qty = max(0, int(risk_rupees / (entry - stop)))

        setup = "BREAKOUT" if x["Close"] > x["High20"] else "TREND_CONTINUATION"

        return {
            "symbol": symbol,
            "score": int(score),
            "setup": setup,
            "entry": entry,
            "stop": stop,
            "target1": target1,
            "target2": target2,
            "rr": float(rr),
            "qty": qty,
            "rsi": float(x["RSI"]),
            "thesis": (
                f"{symbol} shows {setup.lower()} characteristics "
                f"with a model score of {int(score)}/100."
            ),
            "risk": (
                "Invalidation below the stop. Model does not account for "
                "overnight gaps, slippage, taxes or execution delays."
            ),
        }
    except Exception:
        return None

def daily_scan(capital, risk_pct, min_score=75, min_rr=2.0):
    rows = []

    for symbol in NIFTY50:
        result = analyze(symbol, capital, risk_pct)
        if result is None:
            continue
        if result["score"] >= min_score and result["rr"] >= min_rr:
            rows.append(result)

    rows.sort(key=lambda item: (item["score"], item["rr"]), reverse=True)
    top3 = rows[:3]

    if rows:
        csv = pd.DataFrame(rows).to_csv(index=False)
    else:
        csv = "No qualified setups today.\n"

    return {"top3": top3, "all": rows, "csv": csv}
