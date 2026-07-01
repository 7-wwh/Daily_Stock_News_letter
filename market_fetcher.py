"""
market_fetcher.py

Fetches live price data and recent news for every ticker in your portfolio.
Takes the ticker list from portfolio_loader.py and outputs a structured
JSON file that the Hermes agents will use to build the daily brief.

What this fetches per ticker:
  - Current price, % change, volume
  - 52-week high / low
  - Simple moving averages (SMA 50, SMA 200)
  - RSI (14-day)
  - Recent news headlines + links

Usage:
    python market_fetcher.py

Output:
    market_data.json — stored in the same folder, ready for the agents.
"""

import json
import time
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import yfinance as yf

from portfolio_loader import load_portfolio

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
PORTFOLIO_FILE = "stock_portfolio.json"
OUTPUT_FILE    = "market_data.json"
NEWS_LIMIT     = 5       # max news articles per ticker
DELAY_SECONDS  = 1       # polite delay between API calls to avoid rate limiting


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def _compute_rsi(closes: list[float], period: int = 14) -> float | None:
    """
    Calculates RSI from a list of closing prices.
    RSI > 70 = overbought, RSI < 30 = oversold.
    Returns None if there isn't enough data.
    """
    if len(closes) < period + 1:
        return None

    gains, losses = [], []
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        (gains if change >= 0 else losses).append(abs(change))

    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _safe(value, decimals: int = 2):
    """Round a float safely; return None if the value is missing."""
    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────
# PRICE + TECHNICALS
# ─────────────────────────────────────────────
def fetch_price_data(ticker: str) -> dict:
    """
    Fetch current price snapshot and basic technicals for one ticker.
    """
    logger.info(f"Fetching price for {ticker}...")
    result = {
        "ticker":       ticker,
        "price":        None,
        "change_pct":   None,
        "volume":       None,
        "week52_high":  None,
        "week52_low":   None,
        "sma_50":       None,
        "sma_200":      None,
        "rsi_14":       None,
        "error":        None,
    }

    try:
        tk = yf.Ticker(ticker)

        # Current snapshot from .info
        info = tk.info
        if not info or ("currentPrice" not in info and "regularMarketPrice" not in info):
             logger.warning(f"Incomplete info for {ticker}, attempting fallback from history.")
             try:
                 hist = tk.history(period="5d")
                 last_price = hist["Close"].iloc[-1] if not hist.empty else None
             except Exception:
                 last_price = None
        else:
             last_price = info.get("currentPrice") or info.get("regularMarketPrice")
             
        result["price"]       = _safe(last_price)
        result["change_pct"]  = _safe(info.get("regularMarketChangePercent"), 4)
        result["volume"]      = info.get("regularMarketVolume")
        result["week52_high"] = _safe(info.get("fiftyTwoWeekHigh"))
        result["week52_low"]  = _safe(info.get("fiftyTwoWeekLow"))

        # Historical closes for SMA + RSI (fetch 1 year of daily data)
        hist = tk.history(period="1y", interval="1d")

        if not hist.empty:
            closes = hist["Close"].tolist()

            # SMA 50
            if len(closes) >= 50:
                result["sma_50"] = _safe(sum(closes[-50:]) / 50)

            # SMA 200
            if len(closes) >= 200:
                result["sma_200"] = _safe(sum(closes[-200:]) / 200)

            # RSI 14
            result["rsi_14"] = _compute_rsi(closes[-30:])  # last 30 days is enough

        logger.info(f"Successfully fetched price for {ticker}")

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Failed to fetch price for {ticker}: {e}")

    return result


# ─────────────────────────────────────────────
# NEWS
# ─────────────────────────────────────────────
def fetch_news(ticker: str, limit: int = NEWS_LIMIT) -> list[dict]:
    """
    Fetch recent news headlines for one ticker via yfinance.
    """
    logger.info(f"Fetching news for {ticker}...")
    articles = []

    try:
        tk = yf.Ticker(ticker)
        raw_news = tk.news or []

        for item in raw_news[:limit]:
            content = item.get("content", {})
            articles.append({
                "headline":     content.get("title", "N/A"),
                "publisher":    content.get("provider", {}).get("displayName", "N/A"),
                "link":         content.get("canonicalUrl", {}).get("url", "N/A"),
                "published_at": content.get("pubDate", "N/A"),
            })

        logger.info(f"Successfully fetched {len(articles)} news articles for {ticker}")

    except Exception as e:
        logger.error(f"Failed to fetch news for {ticker}: {e}")

    return articles


# ─────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────
def fetch_all(portfolio_file: str = PORTFOLIO_FILE) -> dict:
    """
    Loop over every ticker in the portfolio, fetch price + news,
    and return one consolidated dict ready to be saved as JSON.
    """
    portfolio = load_portfolio(portfolio_file)
    tickers   = portfolio["all_tickers"]

    logger.info(f"Starting fetch for {len(tickers)} tickers.")

    results = {}

    def _fetch_ticker_data(ticker):
        price_data = fetch_price_data(ticker)
        # No delay inside thread to allow concurrency, 
        # but yfinance itself has some inherent limits.
        news_data  = fetch_news(ticker)
        return ticker, price_data, news_data

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_fetch_ticker_data, ticker): ticker for ticker in tickers}
        
        for future in futures:
            ticker, price_data, news_data = future.result()
            results[ticker] = {
                "price":  price_data,
                "news":   news_data,
            }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source":       "yfinance",
        "tickers":      tickers,
        "data":         results,
    }

    return payload


def save(payload: dict, output_file: str = OUTPUT_FILE) -> None:
    """Write the payload to a JSON file."""
    path = Path(output_file)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Successfully saved market data to {path.resolve()}")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch stock market data for a portfolio.")
    parser.add_argument("--portfolio", default=PORTFOLIO_FILE, help="Path to portfolio file")
    parser.add_argument("--output", default=OUTPUT_FILE, help="Path to output JSON file")
    args = parser.parse_args()

    payload = fetch_all(args.portfolio)
    save(payload, args.output)
