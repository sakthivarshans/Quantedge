"""
Research notebook analysis functions. Each function corresponds to a "cell type"
the user can run in the Research Notebook UI, mirroring what a quant researcher
would actually script ad hoc: correlation matrices, single-pair diagnostics,
rolling statistics, and simple factor/beta exposure.
"""
import numpy as np
import pandas as pd
from app.services.data_service import fetch_price_history
from app.services.pair_analysis import analyze_pair


def run_correlation_matrix(tickers: list[str], days: int = 500) -> dict:
    frames = fetch_price_history(tickers, days=days)
    closes = {t: df.set_index("date")["close"] for t, df in frames.items() if t in tickers}
    df = pd.DataFrame(closes).dropna()
    corr = df.corr().round(3)
    return {
        "tickers": list(corr.columns),
        "matrix": corr.values.tolist(),
    }


def run_pair_diagnostics(ticker_a: str, ticker_b: str, days: int = 500) -> dict:
    frames = fetch_price_history([ticker_a, ticker_b], days=days)
    pa = frames[ticker_a].set_index("date")["close"]
    pb = frames[ticker_b].set_index("date")["close"]
    pa, pb = pa.align(pb, join="inner")
    result = analyze_pair(pa, pb)
    return {
        "ticker_a": ticker_a, "ticker_b": ticker_b,
        "dates": [d.strftime("%Y-%m-%d") for d in pa.index],
        "price_a": pa.round(2).tolist(), "price_b": pb.round(2).tolist(),
        **result,
    }


def run_rolling_stats(tickers: list[str], window: int = 30, days: int = 500) -> dict:
    frames = fetch_price_history(tickers, days=days)
    result = {}
    for t in tickers:
        if t not in frames:
            continue
        close = frames[t].set_index("date")["close"]
        returns = close.pct_change()
        rolling_vol = (returns.rolling(window).std() * np.sqrt(252)).dropna()
        rolling_mean_return = (returns.rolling(window).mean() * 252).dropna()
        result[t] = {
            "dates": [d.strftime("%Y-%m-%d") for d in rolling_vol.index],
            "annualized_volatility": rolling_vol.round(4).tolist(),
            "annualized_return": rolling_mean_return.round(4).tolist(),
            "latest_volatility": round(float(rolling_vol.iloc[-1]), 4) if len(rolling_vol) else None,
            "latest_return": round(float(rolling_mean_return.iloc[-1]), 4) if len(rolling_mean_return) else None,
        }
    return {"window": window, "series": result}


def run_beta_exposure(tickers: list[str], benchmark: str = "AAPL", days: int = 500) -> dict:
    """
    Simple single-factor beta of each ticker against a benchmark (defaults to AAPL as
    a market-proxy stand-in since this platform doesn't wire up a real index feed).
    """
    all_tickers = list(set(tickers) | {benchmark})
    frames = fetch_price_history(all_tickers, days=days)
    if benchmark not in frames:
        raise ValueError(f"Could not fetch data for benchmark {benchmark}")

    bench_returns = frames[benchmark].set_index("date")["close"].pct_change().dropna()
    results = []
    for t in tickers:
        if t not in frames or t == benchmark:
            continue
        ret = frames[t].set_index("date")["close"].pct_change().dropna()
        ret, bench = ret.align(bench_returns, join="inner")
        if len(ret) < 30:
            continue
        cov = np.cov(ret, bench)[0][1]
        var = np.var(bench)
        beta = cov / var if var > 0 else 0.0
        correlation = float(ret.corr(bench))
        results.append({"ticker": t, "beta": round(float(beta), 3), "correlation": round(correlation, 3)})

    return {"benchmark": benchmark, "exposures": results}


CELL_RUNNERS = {
    "correlation_matrix": lambda p: run_correlation_matrix(p["tickers"], p.get("days", 500)),
    "pair_diagnostics": lambda p: run_pair_diagnostics(p["ticker_a"], p["ticker_b"], p.get("days", 500)),
    "rolling_stats": lambda p: run_rolling_stats(p["tickers"], p.get("window", 30), p.get("days", 500)),
    "beta_exposure": lambda p: run_beta_exposure(p["tickers"], p.get("benchmark", "AAPL"), p.get("days", 500)),
}


def run_cell(cell_type: str, params: dict) -> dict:
    if cell_type not in CELL_RUNNERS:
        raise ValueError(f"Unknown cell type: {cell_type}. Valid types: {list(CELL_RUNNERS.keys())}")
    return CELL_RUNNERS[cell_type](params)
