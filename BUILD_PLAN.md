# 🏗️ Hermes Financial Intelligence Pipeline: Engineering Blueprint

This document serves as the master execution plan for transforming the Hermes Financial Intelligence conceptual design into a fully operational research-to-print pipeline.

## 🎯 Mission Objective
To replace "dashboard fatigue" with a high-conviction, editorial-grade daily dossier. The system must move from raw ticker lists to actionable intelligence with zero noise, delivered in a print-ready A4 format.

---

## 🗺️ Architectural Breakdown

### 1. The Behavioral Core (`soul.md`)
Before any code is written, we define the "Intellectual DNA" of the system. `soul.md` is not a simple prompt; it is a behavioral constraint framework.
- **Persona:** A senior quantitative analyst with a bias toward "signal" and a hatred for "narrative."
- **Discipline Rules:** 
    - **Constraint:** Max 15 words for directives.
    - **Logic:** Every catalyst must follow the `Event ➔ Impact ➔ Action` chain.
    - **Filtering:** If a data point doesn't link to a trade or risk, it is discarded (Zero-Noise policy).
- **Tone:** Cold, precise, institutional.

### 2. The Orchestration Layer (`cron_orchestrator.py`)
The "Brain" that manages the lifecycle of the daily run.
- **Portfolio Sync:** Parses `Stock_portfolio.md` to extract the current "Watch Universe."
- **Async Swarm Dispatch:** Uses `asyncio` to fire all four research agents in parallel to minimize latency.
- **Payload Aggregation:** Collects disparate JSON responses and validates them against the master schema defined in `template.html`.
- **Error Handling:** Implements "graceful degradation"—if the Technical Reader fails, the system still renders the rest of the brief with a "Data Unavailable" tag rather than crashing.

### 3. The Agent Swarm (Deep-Dive Logic)
Each agent is a specialized module with a distinct research methodology:

#### 🔍 Catalyst Scanner (`catalyst_scanner.py`)
- **Focus:** Dominant capital drivers.
- **Logic:** Scans high-velocity news feeds $\rightarrow$ Identifies the "Main Story" $\rightarrow$ Extracts the "So What" (Impact) $\rightarrow$ Formulates the "Now What" (Action).
- **Possibility:** Implement "Cross-Source Verification" where the agent must find the same catalyst in two independent sources before flagging it as "High Conviction."

#### 🚩 Risk Flagger (`risk_flagger.py`)
- **Focus:** Systemic headwinds and "Black Swans."
- **Logic:** Identifies macro/micro risks $\rightarrow$ Assigns a **Horizon Tag** (`48H` = Urgent, `5D` = Tactical, `30D` = Structural).
- **Possibility:** Integrate a "Risk Correlation Matrix" to show how a macro risk (e.g., Fed Rate Hike) specifically impacts the current portfolio holdings.

#### 📈 Technical Reader (`technical_reader.py`)
- **Focus:** Price action and structural floors.
- **Logic:** Queries current price $\rightarrow$ Identifies key Support/Resistance levels $\rightarrow$ Determines "Technical State" (e.g., *Approaching Support*, *Range Bound*).
- **Possibility:** Use a vision-capable model to "read" actual chart screenshots to identify patterns (Head & Shoulders, Bull Flags) that text-based data misses.

#### 🌐 Sector Sentiment (`sector_sentiment.py`)
- **Focus:** Long-term capital rotations.
- **Logic:** Analyzes sector-wide volume shifts $\rightarrow$ Differentiates between "Short-term Noise" and "Secular Rotation."
- **Possibility:** Track "Smart Money" flow by analyzing institutional filing trends (13F) to predict where the next rotation is heading.

### 4. The Rendering Forge (`compile_pdf.py`)
The bridge between raw JSON and the aesthetic experience.
- **Jinja2 Engine:** Binds the validated JSON payload to the HTML placeholders in `template.html`.
- **Tailwind Injection:** Dynamically adjusts CSS classes (e.g., changing a P&L value to `text-red-600` if `up: false`).
- **PDF Compilation:** Uses **Playwright** (Headless Chromium) to render the HTML and execute a `pdf()` print command, ensuring perfect A4 margins and typography.

---

## 🚀 Advanced Build Possibilities

To elevate this from a "script" to a "professional platform," the following can be implemented:

| Feature | Description | Impact |
| :--- | :--- | :--- |
| **The Critic Agent** | A 5th "Editor" agent that reviews the final JSON payload for "AI-isms" or fluff before it hits the template. | $\text{Quality} \uparrow$ |
| **Multi-Model Routing** | Routing Technicals to a Vision model, Risks to a reasoning-heavy model (O1/Claude), and News to a fast model. | $\text{Precision} \uparrow$ |
| **Dynamic Universe** | If the Catalyst Scanner finds a massive trend in "Liquid Cooling," the orchestrator automatically adds the top 3 peers to the watchlist for that day. | $\text{Alpha} \uparrow$ |
| **Confidence Scoring** | Every data point is assigned a confidence score (0-100%). Low-confidence items are rendered in a lighter grey font. | $\text{Trust} \uparrow$ |
| **Interactive HTML** | Delivery of an HTML version with tooltips (already in template) that link directly to the source articles. | $\text{UX} \uparrow$ |

---

## 📅 Execution Roadmap

1. **Phase 1: Identity** $\rightarrow$ Author `soul.md` and setup directory structure.
2. **Phase 2: The Swarm** $\rightarrow$ Develop the 4 agent scripts + JSON validation.
3. **Phase 3: The Brain** $\rightarrow$ Build `cron_orchestrator.py` for portfolio sync and async execution.
4. **Phase 4: The Forge** $\rightarrow$ Build `compile_pdf.py` with Jinja2 and Playwright.
5. **Phase 5: Automation** $\rightarrow$ Schedule via `cronjob` for daily 08:00 AM delivery.
