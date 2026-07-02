"""
market_fetcher.py  —  Hermes Financial Intelligence Pipeline
─────────────────────────────────────────────────────────────
Fetches live price data and computes technical indicators for
every ticker in your portfolio. News is handled separately by
news_fetcher.py via Tavily.

What this fetches per ticker:
    - Current price, % change, volume
    - 52-week high / low
    - SMA 50, SMA 200, EMA 20, EMA 50
    - RSI 14, MACD, Bollinger Bands, ADX, Stochastic, ATR
    - Pre-computed verdict (Strong Buy → Strong Sell)

Output:
    Writes to market_data.json under key "prices"

Usage:
    python market_fetcher.py

Dependencies:
    pip install yfinance pandas pandas-ta
"""

import json
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas_ta_classic as ta
import yfinance as yf

from portfolio_loader import load_portfolio

warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
PORTFOLIO_FILE = "stock_portfolio.json"
OUTPUT_FILE    = "market_data.json"
DELAY_SECONDS  = 1.5
HISTORY_PERIOD = "1y"


# ─────────────────────────────────────────────
# VERDICT ENGINE
# ─────────────────────────────────────────────
def _compute_verdict(indicators: dict) -> dict:
    """
    Votes across all indicators → one pre-computed signal.

    Each indicator casts one vote:
        +1 = Bullish  |  0 = Neutral  |  -1 = Bearish

    Final label:
        >= +4  → Strong Buy   |  <= -4  → Strong Sell
        +2/+3  → Buy          |  -2/-3  → Sell
        -1/+1  → Neutral
    """
    votes = []
    price  = indicators.get("price")
    rsi    = indicators.get("rsi_14")
    sma50  = indicators.get("sma_50")
    sma200 = indicators.get("sma_200")
    ema20  = indicators.get("ema_20")
    ema50  = indicators.get("ema_50")

    # RSI
    if rsi is not None:
        votes.append(1 if rsi < 30 else -1 if rsi > 70 else 0)

    # MACD crossover
    macd = indicators.get("macd")
    macd_sig = indicators.get("macd_signal")
    if macd is not None and macd_sig is not None:
        votes.append(1 if macd > macd_sig else -1)

    # Price vs SMA 50
    if price and sma50:
        votes.append(1 if price > sma50 else -1)

    # Price vs SMA 200
    if price and sma200:
        votes.append(1 if price > sma200 else -1)

    # Bollinger Bands
    bb_upper = indicators.get("bb_upper")
    bb_lower = indicators.get("bb_lower")
    if price and bb_upper and bb_lower:
        votes.append(1 if price < bb_lower else -1 if price > bb_upper else 0)

    # ADX trend strength
    adx = indicators.get("adx")
    if adx is not None and price and sma50:
        votes.append((1 if price > sma50 else -1) if adx > 25 else 0)

    # Stochastic %K
    stoch_k = indicators.get("stoch_k")
    if stoch_k is not None:
        votes.append(1 if stoch_k < 20 else -1 if stoch_k > 80 else 0)

    # EMA crossover
    if ema20 and ema50:
        votes.append(1 if ema20 > ema50 else -1)

    total = sum(votes)
    count = len(votes)

    label = (
        "Strong Buy"  if total >= 4  else
        "Buy"         if total >= 2  else
        "Strong Sell" if total <= -4 else
        "Sell"        if total <= -2 else
        "Neutral"
    )

    return {"label": label, "score": total, "max_score": count}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def _r(value, decimals: int = 2):
    """Safely round a float; return None if missing."""
    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────
# PRICE + TECHNICALS
# ─────────────────────────────────────────────
def fetch_price_and_technicals(ticker: str) -> dict:
    """Fetch OHLCV + compute all indicators for one ticker."""
    print(f"  [technicals] {ticker} ...", end=" ", flush=True)

    result = {
        "ticker":       ticker,
        "price":        None,
        "change_pct":   None,
        "volume":       None,
        "week52_high":  None,
        "week52_low":   None,
        "sma_50":       None,
        "sma_200":      None,
        "ema_20":       None,
        "ema_50":       None,
        "rsi_14":       None,
        "macd":         None,
        "macd_signal":  None,
        "macd_hist":    None,
        "bb_upper":     None,
        "bb_mid":       None,
        "bb_lower":     None,
        "adx":          None,
        "stoch_k":      None,
        "stoch_d":      None,
        "atr":          None,
        "verdict":      None,
        "error":        None,
    }

    try:
        tk   = yf.Ticker(ticker)
        info = tk.info
        
        # Check if the ticker is valid by checking if we get info back
        if not info or "regularMarketPrice" not in info and "currentPrice" not in info:
             result["error"] = "Ticker not found or no data"
             print("✗ (ticker not found or no data)")
             return result

        hist = tk.history(period=HISTORY_PERIOD, interval="1d")

        if hist.empty:
            result["error"] = "No historical data returned"
            print("✗ (no data)")
            return result

        # Current snapshot
        result["price"]       = _r(info.get("currentPrice") or info.get("regularMarketPrice"))
        result["change_pct"]  = _r(info.get("regularMarketChangePercent"), 4)
        result["volume"]      = info.get("regularMarketVolume")
        result["week52_high"] = _r(info.get("fiftyTwoWeekHigh"))
        result["week52_low"]  = _r(info.get("fiftyTwoWeekLow"))

        # pandas-ta indicators
        df = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]

        df.ta.sma(length=50,  append=True)
        df.ta.sma(length=200, append=True)
        df.ta.ema(length=20,  append=True)
        df.ta.ema(length=50,  append=True)
        df.ta.rsi(length=14,  append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.stoch(k=14, d=3, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.atr(length=14,   append=True)
        df.ta.adx(length=14,   append=True)

        last = df.iloc[-1]

        result["sma_50"]      = _r(last.get("SMA_50"))
        result["sma_200"]     = _r(last.get("SMA_200"))
        result["ema_20"]      = _r(last.get("EMA_20"))
        result["ema_50"]      = _r(last.get("EMA_50"))
        result["rsi_14"]      = _r(last.get("RSI_14"))
        result["macd"]        = _r(last.get("MACD_12_26_9"))
        result["macd_signal"] = _r(last.get("MACDs_12_26_9"))
        result["macd_hist"]   = _r(last.get("MACDh_12_26_9"))
        result["bb_upper"]    = _r(last.get("BBU_20_2.0"))
        result["bb_mid"]      = _r(last.get("BBM_20_2.0"))
        result["bb_lower"]    = _r(last.get("BBL_20_2.0"))
        result["adx"]         = _r(last.get("ADX_14"))
        result["stoch_k"]     = _r(last.get("STOCHk_14_3_3"))
        result["stoch_d"]     = _r(last.get("STOCHd_14_3_3"))
        result["atr"]         = _r(last.get("ATRr_14"))
        result["verdict"]     = _compute_verdict(result)

        print("✓")

    except Exception as e:
        result["error"] = str(e)
        print(f"✗ ({e})")

    return result


# ─────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────
def run(portfolio_file: str = PORTFOLIO_FILE) -> dict:
    portfolio = load_portfolio(portfolio_file)
    tickers   = portfolio["all_tickers"]

    print(f"\n{'═'*55}")
    print(f"  MARKET FETCHER  |  prices + technicals")
    print(f"  {len(tickers)} tickers  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═'*55}\n")

    results = {}
    for ticker in tickers:
        results[ticker] = fetch_price_and_technicals(ticker)
        v = results[ticker].get("verdict")
        if v:
            print(f"  → {ticker} verdict: {v['label']} (score {v['score']}/{v['max_score']})")
        time.sleep(DELAY_SECONDS)

    return results


# ─────────────────────────────────────────────
# ENTRY POINT (standalone test)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    data = run(PORTFOLIO_FILE)

    # Merge into market_data.json under "prices" key
    output_path = Path(OUTPUT_FILE)
    existing = json.loads(output_path.read_text()) if output_path.exists() else {}
    existing["prices"]       = data
    existing["generated_at"] = datetime.now(timezone.utc).isoformat()
    output_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))

    print(f"\n  Saved → {OUTPUT_FILE}  (key: prices)\n")