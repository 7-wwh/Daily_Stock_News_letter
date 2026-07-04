"""
news_fetcher.py  —  Hermes Financial Intelligence Pipeline
─────────────────────────────────────────────────────────────
Two-layer news intelligence system:

    LAYER 1 — yfinance (ground truth)
        Structured, reliable ticker-level news direct from
        Yahoo Finance. Always runs first. Zero API cost.

    LAYER 2 — Tavily (internet context)
        Search → Extract pattern for deep article content.
        Budget-managed to stay within 1,000 searches/month.

        MICRO: 1 search per ticker → extract top 2 URLs
        MACRO: 5 consolidated theme queries → extract top 1 URL each

        Daily budget: ~17 searches/day = ~510/month
        Buffer remaining: ~490/month

Output:
    Writes to market_data.json under keys:
        "yf_news"     — yfinance headlines (ground truth)
        "micro_news"  — Tavily per-ticker deep articles
        "macro_news"  — Tavily macro theme articles

Usage:
    python news_fetcher.py

Setup:
    export TAVILY_API_KEY="tvly-xxxxxxxxxxxx"

Dependencies:
    pip install yfinance tavily-python
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

import yfinance as yf
from tavily import TavilyClient

from portfolio_loader import load_portfolio


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
MACRO_QUERIES_FILE = str(BASE_DIR / "News_Fetching" / "LLM_relay" / "macro_query.json")
TAVILY_API_KEY    = os.getenv("TAVILY_API_KEY", "YOUR_TAVILY_API_KEY_HERE")
PORTFOLIO_FILE    = str(BASE_DIR / "stock_portfolio.json")
OUTPUT_FILE       = str(BASE_DIR / "market_data.json")

# Budget controls
YF_NEWS_LIMIT     = 100     # headlines per ticker from yfinance (free)
MICRO_RESULTS     = 5     # search results per ticker (Tavily search)
MICRO_EXTRACT     = 2     # how many URLs to deep-extract per ticker (Tavily extract)
MACRO_RESULTS     = 5     # search results per macro theme
MACRO_EXTRACT     = 1     # URLs to extract per macro theme
DELAY_SECONDS     = 1.0   # polite delay between calls


# ─────────────────────────────────────────────
# MACRO THEME QUERIES
# Loaded dynamically from macro_queries.json
# Updated weekly by macro_query_updater.py
# ─────────────────────────────────────────────
def load_macro_queries(path: str = MACRO_QUERIES_FILE) -> list[dict]:
    """
    Load macro queries from macro_queries.json.
    Returns list of query dicts: {id, theme, query, rationale}
    Falls back to empty list with warning if file is missing.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        queries = data.get("queries", [])
        print(f"  Loaded {len(queries)} macro queries from {path}")
        return queries
    except FileNotFoundError:
        print(f"  ⚠️  {path} not found — run macro_query_updater.py first")
        return []
    except json.JSONDecodeError as e:
        print(f"  ⚠️  {path} is malformed: {e}")
        return []

MACRO_QUERIES = load_macro_queries(MACRO_QUERIES_FILE)

# ─────────────────────────────────────────────
# LAYER 1 — yfinance (ground truth, zero cost)
# ─────────────────────────────────────────────
def fetch_yf_news(tickers: list[str]) -> dict[str, list[dict]]:
    """
    Fetch structured news headlines from Yahoo Finance for all tickers.
    Fast, free, reliable. Always runs regardless of Tavily budget.
    """
    print(f"\n── LAYER 1: yfinance news (ground truth) {'─'*14}")
    results = {}

    for ticker in tickers:
        print(f"  [yfinance] {ticker} ...", end=" ", flush=True)
        articles = []

        try:
            raw = yf.Ticker(ticker).news or []
            for item in raw[:YF_NEWS_LIMIT]:
                content = item.get("content", {})
                articles.append({
                    "headline":     content.get("title", "N/A"),
                    "publisher":    content.get("provider", {}).get("displayName", "N/A"),
                    "url":          content.get("canonicalUrl", {}).get("url", "N/A"),
                    "published_at": content.get("pubDate", "N/A"),
                    "source":       "yfinance",
                })
            print(f"✓ ({len(articles)} headlines)")

        except Exception as e:
            print(f"✗ ({e})")

        results[ticker] = articles
        time.sleep(0.5)

    return results


# ─────────────────────────────────────────────
# LAYER 2a — Tavily MICRO news (per ticker)
# Pattern: search → extract top URLs for depth
# ─────────────────────────────────────────────
def fetch_micro_news(
    client: TavilyClient,
    ticker: str,
    name: str,
    extract_count: int = MICRO_EXTRACT,
) -> dict:
    """
    1. Search Tavily for the ticker's current catalyst news.
    2. Extract full body from top N result URLs.

    Returns a dict with:
        "search_results"  — headline + snippet from search
        "full_articles"   — extracted full-text from top URLs
    """
    print(f"  [micro search] {ticker} ...", end=" ", flush=True)

    # One rich, multi-angle query per ticker
    query = (
        f"{ticker} {name} stock catalyst news earnings analyst upgrade "
        f"downgrade regulatory SEC filing insider 2026"
    )

    search_results = []
    full_articles  = []

    # ── Step 1: Search ────────────────────────
    try:
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=MICRO_RESULTS,
            include_answer=False,
        )
        for r in response.get("results", []):
            search_results.append({
                "headline": r.get("title", "N/A"),
                "url":      r.get("url", "N/A"),
                "snippet":  r.get("content", "N/A")[:400],
                "source":   r.get("source", "N/A"),
                "score":    round(r.get("score", 0), 3),
            })
        print(f"✓ ({len(search_results)} results)", end=" ")

    except Exception as e:
        print(f"✗ search ({e})")
        return {"search_results": [], "full_articles": []}

    # ── Step 2: Extract top URLs ──────────────
    top_urls = [r["url"] for r in search_results[:extract_count] if r["url"] != "N/A"]

    if top_urls:
        print(f"→ extracting {len(top_urls)} URLs...", end=" ", flush=True)
        try:
            extracted = client.extract(urls=top_urls)
            for result in extracted.get("results", []):
                full_articles.append({
                    "url":          result.get("url", "N/A"),
                    "full_content": result.get("raw_content", "N/A")[:2000],  # cap at 2000 chars
                    "source":       "tavily_extract",
                })
            print(f"✓ ({len(full_articles)} extracted)")
        except Exception as e:
            print(f"✗ extract ({e})")
    else:
        print()

    return {
        "ticker":         ticker,
        "query":          query,
        "search_results": search_results,
        "full_articles":  full_articles,
    }


# ─────────────────────────────────────────────
# LAYER 2b — Tavily MACRO news (global themes)
# Pattern: search → extract top URL per theme
# ─────────────────────────────────────────────
def fetch_macro_news(
    client: TavilyClient,
    extract_count: int = MACRO_EXTRACT,
) -> list[dict]:
    """
    Run each macro theme query through Tavily search + extract.
    Tavily's AI summary (answer field) is preserved per theme —
    this is high-value pre-synthesised context for the agent.
    """
    print(f"\n── LAYER 2b: Tavily macro themes ({'─'*22})")
    results = []

    for q in MACRO_QUERIES:
        query = q.get("query", "")
        label = query[:55]
        print(f"  [macro search] {label}...", end=" ", flush=True)

        search_results = []
        full_articles  = []
        tavily_summary = None

        # ── Search ────────────────────────────
        try:
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=MACRO_RESULTS,
                include_answer=True,   # Tavily AI macro summary, free with search
            )
            tavily_summary = response.get("answer", None)
            for r in response.get("results", []):
                search_results.append({
                    "headline": r.get("title", "N/A"),
                    "url":      r.get("url", "N/A"),
                    "snippet":  r.get("content", "N/A")[:400],
                    "source":   r.get("source", "N/A"),
                    "score":    round(r.get("score", 0), 3),
                })
            print(f"✓ ({len(search_results)} results)", end=" ")

        except Exception as e:
            print(f"✗ search ({e})")
            results.append({"query": query, "error": str(e)})
            time.sleep(DELAY_SECONDS)
            continue

        # ── Extract top URL ───────────────────
        top_urls = [r["url"] for r in search_results[:extract_count] if r["url"] != "N/A"]
        if top_urls:
            print(f"→ extracting {len(top_urls)} URL...", end=" ", flush=True)
            try:
                extracted = client.extract(urls=top_urls)
                for result in extracted.get("results", []):
                    full_articles.append({
                        "url":          result.get("url", "N/A"),
                        "full_content": result.get("raw_content", "N/A")[:2000],
                        "source":       "tavily_extract",
                    })
                print(f"✓")
            except Exception as e:
                print(f"✗ extract ({e})")
        else:
            print()

        results.append({
            "query":          query,
            "theme":          q.get("theme", ""),
            "rationale":      q.get("rationale", ""),
            "tavily_summary": tavily_summary,
            "search_results": search_results,
            "full_articles":  full_articles,
        })

        time.sleep(DELAY_SECONDS)

    return results


# ─────────────────────────────────────────────
# BUDGET TRACKER
# ─────────────────────────────────────────────
def print_budget_summary(portfolio_size: int) -> None:
    """Print estimated daily Tavily search usage."""
    micro_searches = portfolio_size          # 1 per ticker
    macro_searches = len(MACRO_QUERIES)      # 1 per theme
    total          = micro_searches + macro_searches
    monthly        = total * 30

    print(f"\n── TAVILY BUDGET ESTIMATE {'─'*29}")
    print(f"  Micro searches  : {micro_searches} (1 per ticker)")
    print(f"  Macro searches  : {macro_searches} (theme queries)")
    print(f"  Daily total     : {total} searches")
    print(f"  Monthly est.    : {monthly} / 1000")
    print(f"  Buffer          : {1000 - monthly} remaining")
    if monthly > 900:
        print(f"  ⚠️  WARNING: approaching monthly limit — reduce queries")
    else:
        print(f"  ✓  Within safe budget")


# ─────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────
def run(portfolio_file: str = PORTFOLIO_FILE) -> tuple[dict, dict, list]:
    if TAVILY_API_KEY == "YOUR_TAVILY_API_KEY_HERE":
        raise EnvironmentError(
            "Tavily API key not set.\n"
            "Run: export TAVILY_API_KEY='tvly-xxxxxxxxxxxx'"
        )

    client    = TavilyClient(api_key=TAVILY_API_KEY)
    portfolio = load_portfolio(portfolio_file)
    holdings  = portfolio["holdings"]
    watchlist = portfolio["watchlist"]
    all_items = holdings + watchlist
    tickers   = [i["ticker"] for i in all_items]

    print(f"\n{'═'*55}")
    print(f"  NEWS FETCHER  |  yfinance + Tavily")
    print(f"  {len(tickers)} tickers  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═'*55}")

    print_budget_summary(len(tickers))

    # ── Layer 1: yfinance (always runs first) ─
    yf_news = fetch_yf_news(tickers)

    # ── Layer 2a: Tavily micro ─────────────────
    print(f"\n── LAYER 2a: Tavily micro news ({'─'*23})")
    micro_news = {}
    for item in all_items:
        micro_news[item["ticker"]] = fetch_micro_news(
            client, item["ticker"], item["name"]
        )
        time.sleep(DELAY_SECONDS)

    # ── Layer 2b: Tavily macro ─────────────────
    macro_news = fetch_macro_news(client)

    return yf_news, micro_news, macro_news


# ─────────────────────────────────────────────
# ENTRY POINT (standalone test)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    yf_news, micro, macro = run(PORTFOLIO_FILE)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source":       "yfinance + tavily",
        "yf_news":      yf_news,
        "micro_news":   micro,
        "macro_news":   macro,
    }

    output_path = Path(OUTPUT_FILE)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    yf_total    = sum(len(v) for v in yf_news.values())
    micro_total = len(micro)
    macro_total = len(macro)

    print(f"\n{'═'*55}")
    print(f"  Saved → {OUTPUT_FILE}")
    print(f"  yfinance headlines : {yf_total}")
    print(f"  Tavily micro       : {micro_total} tickers")
    print(f"  Tavily macro       : {macro_total} themes")
    print(f"  Generated at       : {datetime.now(timezone.utc).isoformat()}")
    print(f"{'═'*55}\n")