# Hermes Financial Intelligence Pipeline

> Automated, high-velocity research-to-print workflow for the modern quantitative trader.

Hermes ingests raw financial market data from multi-agent research swarms and compiles it into a professionally typeset, actionable daily briefing document — replacing dashboard "information overload" with a clean, F-pattern editorial layout built for rapid cognitive processing and high-conviction decisions.

---

## 🚀 Core Philosophy

**Speed to Intelligence.** In a volatile market, scrolling through news feeds is a tax on your cognitive capital. Hermes transforms raw data into a structured newspaper format built on three rules:

| Principle | What it means |
|---|---|
| **Actionability** | Every data point must link to a trade, a risk, or a sector shift — or it doesn't get surfaced. |
| **Visual Efficiency** | Classic editorial grid systems maximize reading speed over dashboard sprawl. |
| **Zero-Noise** | If no agent flagged it as a catalyst or risk, it never reaches the page. |
| **Regional Relevance** | Coverage universe is SGX + Bursa Malaysia + US equities — not a generic global feed. |

---

## 🏗️ System Architecture

```mermaid
flowchart LR
    subgraph Data
        P[Portfolio: stock_portfolio.json]
    end

    subgraph Fetchers["Fetcher Scripts"]
        M[market_fetcher.py<br/>Prices + Technicals]
        N[news_fetcher.py<br/>News (Tavily)]
    end

    subgraph Output
        D[market_data.json]
        T[template.html]
    end

    P --> M
    P --> N
    M --> D
    N --> D
    D --> T
```

---

## 🏛️ Tech Stack

| Layer | Technology | Role |
|---|---|---|
| Data | JSON | Portfolio holdings (`stock_portfolio.json`) and fetched data (`market_data.json`) |
| Fetching | Python | `market_fetcher.py` (yfinance, pandas-ta), `news_fetcher.py` (Tavily) |
| Rendering | HTML5 + Tailwind CSS | Editorial grid layout in `template.html` |
| Templating | Jinja2 | (Planned) Binds data to template |

---

## 📂 Project Structure

```
├── README.md                  # You are here
├── BUILD_PLAN.md              # Original architectural blueprint
├── market_fetcher.py          # Fetches price + technicals, computes verdict
├── news_fetcher.py            # Fetches news (Tavily)
├── portfolio_loader.py        # Loads stocks from portfolio JSON
├── stock_portfolio.json       # Input portfolio
├── market_data.json           # Output market data
└── template.html              # Frontend template
```

---

## ⚙️ Workflow

1.  **Portfolio Sync** — Define tickers in `stock_portfolio.json`.
2.  **Data Ingestion** — Run fetcher scripts to populate `market_data.json`:
    ```bash
    python market_fetcher.py
    python news_fetcher.py
    ```
3.  **Consumption** — Open `template.html` in a browser to review the brief.

---

## 🛠️ Customization

**Editing the layout** — `template.html` is pure Tailwind; adjust grid density, typography scale, or color palette by editing classes directly.

**Extending agent data** — to add a new field (e.g. a "Sector Sentiment" score):
1. Update the relevant fetcher script (`market_fetcher.py` or `news_fetcher.py`) to handle the new data.
2. Add the matching Jinja2 placeholder (`{{ new_data_key }}`) to `template.html`.

**Adjusting portfolio scope** — ticker coverage is injected dynamically. Update the source portfolio feed; the next orchestrator run picks it up automatically, no template edits needed.

---

## 📋 Roadmap

| Status | Item | Notes |
|---|---|---|
| ⬜ | Automated PDF rendering | Integrate `Playwright` into `compile_pdf.py` to save rendered HTML as high-res PDF |
| ⬜ | Real-time API hook | Connect compiler to a live data endpoint for intraday updates |
| ⬜ | Theme variants | Dark Mode + tablet-optimized CSS profile |
| ⬜ | Institutional report mode | Longer-form institutional-style PDF alongside the daily brief |
| ⬜ | Feedback loop | Log whether flagged catalysts/risks actually moved tickers, to tune agent signal quality over time |
---

*Built for the individual who treats market intelligence as an asset. Manage your input, manage your risk.*
