"""
macro_query_updater.py  —  Hermes Financial Intelligence Pipeline
─────────────────────────────────────────────────────────────────
Weekly macro query maintenance tool. Handles all data work —
scouting, prompt building, validation, and file management.

The LLM call is intentionally NOT here. The Hermes orchestrator
owns all agent calls and passes the response back via
apply_proposal(response_text).

HOW THE ORCHESTRATOR USES THIS:

    from macro_query_updater import prepare_proposal, apply_proposal

    # Step 1 — Scout + build prompt (this file does it)
    prompt, scout_context = prepare_proposal()

    # Step 2 — LLM call (orchestrator does it)
    response = hermes_agent.call(prompt)

    # Step 3 — Validate + save proposal (this file does it)
    success, issues = apply_proposal(response)

MANUAL APPROVAL (you run these after reviewing):

    python macro_query_updater.py --approve
    python macro_query_updater.py --reject

CRON SCHEDULE (Sunday 8pm — triggers orchestrator, not this file directly):
    0 20 * * 0 cd /path/to/hermes && python cron_orchestrator.py --task update_macro_queries

Budget: 3 Tavily scout searches per weekly run = ~12 searches/month
"""

import argparse
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from tavily import TavilyClient

from portfolio_loader import load_portfolio


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "YOUR_TAVILY_API_KEY_HERE")

QUERIES_FILE   = "macro_queries.json"
PROPOSED_FILE  = "macro_queries_proposed.json"
BACKUP_FILE    = "macro_queries_backup.json"
PROMPT_FILE    = "macro_queries_prompt.txt"    # saved so orchestrator can read it

MAX_QUERIES    = 5     # hard budget ceiling — agent can never exceed this
SCOUT_SEARCHES = 3
SCOUT_RESULTS  = 5


# ─────────────────────────────────────────────
# SCOUT QUERIES
# Broad, timeless — these never change.
# Only the macro_queries.json contents change.
# ─────────────────────────────────────────────
SCOUT_QUERIES = [
    "biggest market moving themes investors watching this week",
    "global macro economic risks opportunities investors 2026",
    "Southeast Asia Singapore Malaysia market catalysts this week",
]


# ─────────────────────────────────────────────
# STEP 1 — SCOUT
# ─────────────────────────────────────────────
def scout_market_themes() -> str:
    """
    Run 3 broad Tavily searches to surface what's actually
    moving markets this week. Returns combined context string
    for the agent prompt.

    Cost: 3 Tavily searches.
    """
    if TAVILY_API_KEY == "YOUR_TAVILY_API_KEY_HERE":
        raise EnvironmentError("Set TAVILY_API_KEY environment variable")

    client   = TavilyClient(api_key=TAVILY_API_KEY)
    combined = []

    print(f"\n── STEP 1: Scouting market themes ({SCOUT_SEARCHES} searches) ──")

    for query in SCOUT_QUERIES:
        print(f"  [scout] {query[:55]}...", end=" ", flush=True)
        try:
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=SCOUT_RESULTS,
                include_answer=True,
            )
            summary   = response.get("answer", "No summary available")
            headlines = [r.get("title", "") for r in response.get("results", [])]

            combined.append(
                f"QUERY: {query}\n"
                f"SUMMARY: {summary}\n"
                f"HEADLINES:\n" + "\n".join(f"  - {h}" for h in headlines)
            )
            print("✓")

        except Exception as e:
            print(f"✗ ({e})")

        time.sleep(1.0)

    return "\n\n".join(combined)


# ─────────────────────────────────────────────
# STEP 2 — BUILD PROMPT
# Returns the full prompt string for the
# Hermes orchestrator to pass to the agent.
# ─────────────────────────────────────────────
def build_prompt(scout_context: str, current_queries: list[dict], portfolio_context: str) -> str:
    """
    Build the full agent prompt. The orchestrator passes this
    to the Hermes agent and receives the response.
    """
    current_queries_text = json.dumps(current_queries, indent=2)

    return f"""You are the Hermes Macro Intelligence Agent. Your job is to maintain a lean, high-signal set of macro search queries used to fetch daily market news for a retail investor's portfolio briefing.

PORTFOLIO CONTEXT (what this investor holds):
{portfolio_context}

CURRENT MACRO QUERIES (what we are currently searching for):
{current_queries_text}

MARKET SCOUT RESULTS (what is actually relevant in markets this week):
{scout_context}

YOUR TASK:
1. Evaluate each current query — is it still relevant and high-signal this week?
2. Identify important themes the scout results reveal that are NOT covered by current queries.
3. Propose an updated set of EXACTLY {MAX_QUERIES} macro queries that:
   - Cover the most important themes for THIS investor's specific holdings
   - Replace stale queries with emerging relevant themes from scout results
   - Keep queries that are still highly relevant
   - Always include at least one SEA/SGX/Bursa query given M14.SI, D05.SI, KLCCSS exposure
   - Are specific enough to return high-quality Tavily search results (8-15 words)
   - Are written in natural language for web search

RESPONSE FORMAT:
Respond ONLY with a valid JSON array of exactly {MAX_QUERIES} objects.
No preamble. No explanation. No markdown fences. Raw JSON only.

Each object must have exactly these keys:
  "id"        : "q1" through "q{MAX_QUERIES}"
  "theme"     : short label, 2-4 words
  "query"     : the search query string, 8-15 words
  "rationale" : one sentence — why this query matters to this portfolio right now
  "replaces"  : the id of the query it replaces, or "new" if entirely new"""


# ─────────────────────────────────────────────
# STEP 3 — PARSE AGENT RESPONSE
# ─────────────────────────────────────────────
def parse_response(response_text: str) -> list[dict]:
    """
    Parse the agent's raw response into a list of query dicts.
    Strips markdown fences if the agent included them.
    """
    raw = response_text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        parts = raw.split("```")
        raw   = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


# ─────────────────────────────────────────────
# STEP 4 — VALIDATE
# Hard enforcement before any file is touched.
# ─────────────────────────────────────────────
def validate(proposed: list[dict]) -> tuple[bool, list[str]]:
    """
    Enforces hard rules. Returns (is_valid, issues).
    The orchestrator should abort if is_valid is False.
    """
    issues        = []
    required_keys = {"id", "theme", "query", "rationale", "replaces"}

    if len(proposed) > MAX_QUERIES:
        issues.append(f"Too many queries: {len(proposed)} proposed, max is {MAX_QUERIES}")

    if len(proposed) == 0:
        issues.append("Agent returned zero queries")

    for i, q in enumerate(proposed):
        missing = required_keys - q.keys()
        if missing:
            issues.append(f"Query {i+1} missing keys: {missing}")

        words = len(q.get("query", "").split())
        if words < 5:
            issues.append(f"Query {i+1} too short ({words} words): '{q.get('query')}'")
        if words > 20:
            issues.append(f"Query {i+1} too long ({words} words): '{q.get('query')}'")

    sea_keywords = ["singapore", "sgx", "malaysia", "bursa", "sea", "southeast asia"]
    has_sea      = any(
        any(kw in q.get("query", "").lower() for kw in sea_keywords)
        for q in proposed
    )
    if not has_sea:
        issues.append("No SEA/SGX/Bursa query found — required for M14.SI, D05.SI, KLCCSS")

    return (len(issues) == 0), issues


# ─────────────────────────────────────────────
# PREPARE PROPOSAL
# Called by orchestrator to kick off the flow.
# Returns the prompt + scout context.
# ─────────────────────────────────────────────
def prepare_proposal(portfolio_file: str = "portfolio.md") -> tuple[str, str]:
    """
    Entry point for the orchestrator.

    1. Loads current queries
    2. Scouts market themes via Tavily
    3. Builds and returns the agent prompt

    Returns:
        (prompt_text, scout_context)
        Orchestrator passes prompt_text to the Hermes agent.
        Scout context is returned for logging/debugging.
    """
    print(f"\n{'═'*60}")
    print(f"  MACRO QUERY UPDATER — prepare_proposal()")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═'*60}")

    # Load current queries
    current_data    = json.loads(Path(QUERIES_FILE).read_text(encoding="utf-8"))
    current_queries = current_data.get("queries", [])
    print(f"\n  Current queries: {len(current_queries)}")

    # Portfolio context
    try:
        portfolio         = load_portfolio(portfolio_file)
        tickers           = portfolio["all_tickers"]
        portfolio_context = (
            f"Holdings: {', '.join(tickers[:10])}\n"
            f"Watchlist: {', '.join(tickers[10:])}"
        )
    except Exception:
        portfolio_context = "Holdings: NVDA, PLTR, SOFI, AAPL, MSFT, NFLX, NOW, VOO, M14.SI, D05.SI"

    # Scout
    scout_context = scout_market_themes()

    # Build prompt
    prompt = build_prompt(scout_context, current_queries, portfolio_context)

    # Save prompt to file so orchestrator can also read it from disk if needed
    Path(PROMPT_FILE).write_text(prompt, encoding="utf-8")
    print(f"\n  Prompt saved → {PROMPT_FILE}")
    print(f"  Hand off to Hermes agent for LLM call.\n")

    return prompt, scout_context


# ─────────────────────────────────────────────
# APPLY PROPOSAL
# Called by orchestrator after agent responds.
# ─────────────────────────────────────────────
def apply_proposal(response_text: str) -> tuple[bool, list[str]]:
    """
    Entry point for the orchestrator after the agent call.

    1. Parses agent response
    2. Validates against hard rules
    3. Saves to macro_queries_proposed.json if valid
    4. Prints diff for human review

    Returns:
        (success, issues)
    """
    print(f"\n── Parsing agent response ──")

    try:
        proposed = parse_response(response_text)
    except json.JSONDecodeError as e:
        print(f"  ✗ JSON parse failed: {e}")
        print(f"  Raw (first 300 chars): {response_text[:300]}")
        return False, [f"JSON parse error: {e}"]

    print(f"  Parsed {len(proposed)} proposed queries")

    # Validate
    print(f"\n── Validating proposed queries ──")
    is_valid, issues = validate(proposed)

    if not is_valid:
        print(f"  ✗ Validation failed:")
        for issue in issues:
            print(f"     - {issue}")
        return False, issues

    print(f"  ✓ Validation passed")

    # Load current for diff
    current_data    = json.loads(Path(QUERIES_FILE).read_text(encoding="utf-8"))
    current_queries = current_data.get("queries", [])

    # Save proposal
    proposal = {
        "proposed_at": datetime.now(timezone.utc).isoformat(),
        "status":      "pending_approval",
        "queries":     proposed,
    }
    Path(PROPOSED_FILE).write_text(json.dumps(proposal, indent=2, ensure_ascii=False))

    # Show diff
    _print_diff(current_queries, proposed)

    return True, []


# ─────────────────────────────────────────────
# APPROVE / REJECT
# ─────────────────────────────────────────────
def approve() -> None:
    """Promote proposed queries → macro_queries.json"""
    if not Path(PROPOSED_FILE).exists():
        print("  No proposal found. Run the orchestrator's weekly task first.")
        return

    # Backup current
    if Path(QUERIES_FILE).exists():
        shutil.copy(QUERIES_FILE, BACKUP_FILE)
        print(f"  Backed up → {BACKUP_FILE}")

    proposed_data    = json.loads(Path(PROPOSED_FILE).read_text())
    proposed_queries = proposed_data["queries"]

    new_data = {
        "_meta": {
            "description":    "Macro theme queries used by news_fetcher.py. Managed by macro_query_updater.py.",
            "max_queries":    MAX_QUERIES,
            "last_updated":   datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "last_updated_by":"macro_query_updater (approved)",
            "next_review":    "next Sunday",
        },
        "queries": proposed_queries,
    }

    Path(QUERIES_FILE).write_text(json.dumps(new_data, indent=2, ensure_ascii=False))
    Path(PROPOSED_FILE).unlink()
    if Path(PROMPT_FILE).exists():
        Path(PROMPT_FILE).unlink()

    print(f"\n  ✅ Approved — {QUERIES_FILE} updated ({len(proposed_queries)} queries)")
    print(f"  Backup: {BACKUP_FILE}\n")


def reject() -> None:
    """Discard proposed queries — current file unchanged."""
    if not Path(PROPOSED_FILE).exists():
        print("  No proposal found. Nothing to reject.")
        return

    Path(PROPOSED_FILE).unlink()
    if Path(PROMPT_FILE).exists():
        Path(PROMPT_FILE).unlink()

    print(f"\n  ❌ Rejected — proposal discarded. {QUERIES_FILE} unchanged.\n")


# ─────────────────────────────────────────────
# DIFF PRINTER
# ─────────────────────────────────────────────
def _print_diff(current: list[dict], proposed: list[dict]) -> None:
    current_map = {q["id"]: q for q in current}

    print(f"\n{'═'*60}")
    print(f"  PROPOSED CHANGES — review before approving")
    print(f"{'═'*60}")

    for q in proposed:
        replaces = q.get("replaces", q["id"])
        old      = current_map.get(replaces)

        if not old or replaces == "new":
            print(f"\n  🆕 NEW      [{q['id']}] {q['theme']}")
            print(f"     QRY: {q['query']}")
            print(f"     WHY: {q['rationale']}")
        elif old["query"] != q["query"]:
            print(f"\n  🔄 CHANGED  [{q['id']}] {q['theme']}")
            print(f"     OLD: {old['query']}")
            print(f"     NEW: {q['query']}")
            print(f"     WHY: {q['rationale']}")
        else:
            print(f"\n  ✓  KEPT     [{q['id']}] {q['theme']}")
            print(f"     QRY: {q['query']}")

    print(f"\n{'═'*60}")
    print(f"  python macro_query_updater.py --approve")
    print(f"  python macro_query_updater.py --reject")
    print(f"{'═'*60}\n")


# ─────────────────────────────────────────────
# CLI — manual approve/reject only
# Proposal is triggered via orchestrator
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hermes Macro Query Updater")
    parser.add_argument("--approve", action="store_true", help="Approve and apply proposed queries")
    parser.add_argument("--reject",  action="store_true", help="Reject and discard proposed queries")
    parser.add_argument("--diff",    action="store_true", help="Show current proposal diff without approving")
    args = parser.parse_args()

    if args.approve:
        approve()
    elif args.reject:
        reject()
    elif args.diff:
        if Path(PROPOSED_FILE).exists():
            proposed_data = json.loads(Path(PROPOSED_FILE).read_text())
            current_data  = json.loads(Path(QUERIES_FILE).read_text())
            _print_diff(current_data.get("queries", []), proposed_data["queries"])
        else:
            print("  No pending proposal found.")
    else:
        print("\n  This script is driven by the Hermes orchestrator.")
        print("  The orchestrator calls prepare_proposal() and apply_proposal().")
        print("\n  Manual commands:")
        print("    --approve   Apply the pending proposal")
        print("    --reject    Discard the pending proposal")
        print("    --diff      View the pending proposal diff\n")