import numpy as np
import pandas as pd

SECTOR_MAP = {
    "AAPL": "Technology", "MSFT": "Technology", "GOOG": "Technology", "GOOGL": "Technology",
    "META": "Technology", "NVDA": "Technology", "AMD": "Technology",
    "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary", "HD": "Consumer Discretionary",
    "LOW": "Consumer Discretionary",
    "V": "Financials", "MA": "Financials", "JPM": "Financials", "BAC": "Financials",
    "XOM": "Energy", "CVX": "Energy",
    "KO": "Consumer Staples", "PEP": "Consumer Staples",
    "UNH": "Healthcare",
}


def value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
    if len(returns) == 0:
        return 0.0
    return float(-np.percentile(returns.dropna(), (1 - confidence) * 100))


def conditional_var(returns: pd.Series, confidence: float = 0.95) -> float:
    var = value_at_risk(returns, confidence)
    tail = returns[returns <= -var]
    if len(tail) == 0:
        return var
    return float(-tail.mean())


def portfolio_risk_report(positions: list[dict], returns_by_ticker: dict[str, pd.Series]) -> dict:
    """
    positions: [{"ticker": "AAPL", "market_value": 15000}, ...]
    returns_by_ticker: ticker -> daily return series
    """
    total_value = sum(p["market_value"] for p in positions) or 1.0
    sector_exposure: dict[str, float] = {}
    for p in positions:
        sector = SECTOR_MAP.get(p["ticker"], "Other")
        sector_exposure[sector] = sector_exposure.get(sector, 0) + p["market_value"] / total_value

    weights = {p["ticker"]: p["market_value"] / total_value for p in positions}
    tickers = [p["ticker"] for p in positions if p["ticker"] in returns_by_ticker]
    if tickers:
        df = pd.DataFrame({t: returns_by_ticker[t] for t in tickers}).dropna()
        port_returns = sum(df[t] * weights[t] for t in tickers)
    else:
        port_returns = pd.Series(dtype=float)

    var95 = value_at_risk(port_returns, 0.95)
    cvar95 = conditional_var(port_returns, 0.95)
    equity = (1 + port_returns).cumprod() if len(port_returns) else pd.Series([1.0])
    running_max = equity.cummax()
    max_dd = float(((equity - running_max) / running_max).min()) if len(equity) else 0.0

    warnings = []
    for sector, exposure in sector_exposure.items():
        if exposure > 0.35:
            warnings.append(
                f"High risk detected. {sector} exposure is {exposure*100:.0f}%, "
                f"exceeding the 35% concentration guideline. Recommended reduction: "
                f"{(exposure-0.30)*100:.0f}%."
            )

    return {
        "total_market_value": round(total_value, 2),
        "sector_exposure_pct": {k: round(v * 100, 1) for k, v in sector_exposure.items()},
        "value_at_risk_95_pct": round(var95 * 100, 2),
        "conditional_var_95_pct": round(cvar95 * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "warnings": warnings,
    }
