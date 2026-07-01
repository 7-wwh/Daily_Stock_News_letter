import json
from pathlib import Path
from typing import Any

def load_portfolio(filepath: str | Path = "stock_portfolio.json") -> dict[str, Any]:
    """Loads a portfolio directly from a JSON file and processes it."""
    path = Path(filepath)
    
    # 1. Error check: Does the file actually exist?
    if not path.exists():
        raise FileNotFoundError(f"Portfolio file not found: {path}")

    # 2. Read the file and decode the JSON
    try:
        portfolio_data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"The file {path} is not valid JSON: {e}") from e

    # 3. Safe extraction with fallback defaults
    holdings = portfolio_data.get("holdings", [])
    watchlist = portfolio_data.get("watchlist", [])

    # 4. Generate all tickers in one line
    portfolio_data["all_tickers"] = [h["ticker"] for h in holdings] + [w["ticker"] for w in watchlist]

    return portfolio_data


def validate_portfolio(data: dict[str, Any]) -> list[str]:
    """Checks that all entries have required fields. Returns list of warning messages."""
    warnings = []
    required_fields = {"ticker", "exchange", "name"}

    for section in ("holdings", "watchlist"):
        for index, entry in enumerate(data.get(section, [])):
            missing = required_fields - entry.keys()
            if missing:
                ticker_name = entry.get("ticker", f"index {index}")
                warnings.append(
                    f"Warning in '{section}': '{ticker_name}' is missing fields {missing}"
                )
                
    return warnings


if __name__ == "__main__":
    # Test our streamlined JSON loader
    try:
        portfolio = load_portfolio("stock_portfolio.json")
        
        print("--- Portfolio Loaded Successfully ---")
        print(f"Account: {portfolio.get('account', 'Unknown')}")
        print(f"Currency: {portfolio.get('base_currency', 'Unknown')}")
        print(f"Last Updated: {portfolio.get('last_updated', 'Unknown')}")
        print(f"Holdings Count: {len(portfolio.get('holdings', []))}")
        print(f"Watchlist Count: {len(portfolio.get('watchlist', []))}")
        print(f"All Tickers: {portfolio['all_tickers']}")
        
        # Check for issues
        issues = validate_portfolio(portfolio)
        if issues:
            print("\nValidation warnings found:")
            for issue in issues:
                print(f" - {issue}")
        else:
            print("\nNo validation issues found. Data is healthy!")
            
    except Exception as err:
        print(f"Error loading portfolio: {err}")