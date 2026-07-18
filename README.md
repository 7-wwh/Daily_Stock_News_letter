# Hermes — Daily Stock Newsletter (v1)

Data ingestion toolkit + editorial HTML template for a daily financial briefing. Covers SGX, Bursa Malaysia, and US equities.

---

## What's been built (v1)

| Component | What it does |
|---|---|
| `portfolio_loader.py` | Loads and validates `stock_portfolio.json` (holdings + watchlist) |
| `market_fetcher.py` | Fetches live prices and 13 technical indicators via yfinance + pandas-ta; computes a consensus verdict per ticker |
| `news_fetcher.py` | Two-layer news pipeline: Layer 1 = yfinance free tier, Layer 2 = Tavily search+extract (micro + macro) |
| `macro_query_updater.py` | Weekly macro query maintenance: scout → build prompt → validate → propose → approve/reject |
| `template.html` | Polished 2-page editorial HTML brief with Tailwind CSS, canvas charts, tooltips, and a trading-ticket card layout (currently renders embedded demo data) |

---

## How to run

```bash
# 1. Load portfolio
python portfolio_loader.py

# 2. Fetch market data (prices + technicals)
python market_fetcher.py

# 3. Fetch news (requires TAVILY_API_KEY)
python news_fetcher.py

# 4. Update macro queries
python macro_query_updater.py

# 5. Open the briefing template
open template.html
```

---

## Project structure

```
hermes/
├── portfolio_loader.py        # Load & validate portfolio JSON
├── market_fetcher.py          # yfinance + pandas-ta pipeline
├── market_data.json           # Last fetched market snapshot
├── stock_portfolio.json       # Portfolio definition (10 holdings + 2 watchlist)
├── template.html              # Editorial HTML briefing template
├── News_Fetching/
│   ├── news_fetcher.py        # Two-layer news (yfinance + Tavily)
│   ├── news_data.json         # (placeholder)
│   ├── macro_query_updater.py # Weekly macro query maintenance
│   ├── macro_queries.json     # Active macro queries
│   └── LLM_relay/             # (stubs for LLM proposal pipeline)
├── .github/workflows/opencode.yml
└── README.md
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Data fetching | Python, yfinance, pandas-ta |
| News | Tavily API, yfinance |
| Presentation | HTML5, Tailwind CSS, Google Fonts |
| Portfolio | JSON |
