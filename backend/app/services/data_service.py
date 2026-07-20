"""
Market data ingestion.

Three-tier fallback chain, each tier only attempted if the one before it is
unavailable or fails:
  1. Alpaca Markets (if ALPACA_API_KEY/ALPACA_SECRET_KEY are set) -- a real, free,
     production-grade data feed (IEX real-time + historical bars), the recommended
     path for actually running this with real data. See README/DEPLOYMENT.md for
     how to get a free key (no credit card required).
  2. yfinance -- unofficial, free, no signup needed, but breaks unpredictably and
     gets rate-limited by Yahoo, especially from cloud provider IPs.
  3. Synthetic generator -- produces realistic, genuinely cointegrated price series
     for known pairs (e.g. V/MA, AAPL/MSFT), so the rest of the platform (scanner,
     backtester, risk engine) always has data to work with even with zero network
     access or API keys configured.
"""
import logging
import os
import numpy as np
import pandas as pd
from datetime import timedelta
from app.core.time import utcnow

logger = logging.getLogger("quantedge")

DEFAULT_UNIVERSE = [
    # Technology / mega-cap
    "AAPL", "MSFT", "GOOG", "GOOGL", "META", "AMZN", "NVDA", "AMD", "INTC",
    "CRM", "ORCL", "ADBE", "CSCO", "IBM", "QCOM", "TXN", "AVGO",
    # Consumer discretionary / retail
    "TSLA", "HD", "LOW", "NKE", "SBUX", "MCD", "TGT", "DIS",
    # Financials
    "V", "MA", "JPM", "BAC", "WFC", "GS", "MS", "C", "AXP", "BLK",
    # Energy
    "XOM", "CVX", "COP", "SLB", "OXY",
    # Healthcare
    "UNH", "JNJ", "PFE", "ABBV", "MRK", "LLY", "TMO", "ABT",
    # Consumer staples
    "KO", "PEP", "PG", "CL", "MDLZ", "WMT", "COST",
    # Industrials
    "BA", "CAT", "GE", "HON", "UPS", "LMT",
    # Communication services
    "NFLX", "CMCSA", "T", "VZ",
]

# Pairs we seed with a genuine cointegration relationship in synthetic mode --
# same-sector pairs that tend to move together in real markets too.
KNOWN_RELATED_PAIRS = [
    ("V", "MA"), ("AAPL", "MSFT"), ("GOOG", "META"), ("XOM", "CVX"),
    ("JPM", "BAC"), ("KO", "PEP"), ("HD", "LOW"),
    ("WFC", "C"), ("GS", "MS"), ("JNJ", "PFE"), ("ABBV", "MRK"),
    ("PG", "CL"), ("WMT", "COST"), ("BA", "LMT"), ("VZ", "T"),
    ("NKE", "SBUX"), ("CAT", "HON"), ("ORCL", "IBM"), ("QCOM", "TXN"),
    ("MCD", "TGT"),
]


def _synthetic_series(ticker: str, days: int, seed: int, base_price: float,
                       common_factor: np.ndarray = None, beta: float = 1.0,
                       noise_scale: float = 0.008, idio_phi: float = 0.90) -> pd.Series:
    """
    Builds a log-price series as: shared stochastic trend (common_factor, a random walk)
    plus a STATIONARY idiosyncratic AR(1) component. Using a stationary (not random-walk)
    idiosyncratic term is what actually guarantees the two series in a pair share a single
    common trend and are therefore genuinely cointegrated -- if the idiosyncratic term were
    itself a random walk, its spurious correlation with the common factor could dominate by
    pure chance (two independent random walks are not reliably uncorrelated).
    """
    rng = np.random.default_rng(seed)
    if common_factor is None:
        common_factor = rng.normal(0.0003, 0.012, days).cumsum()

    eps = rng.normal(0, noise_scale, days)
    idiosyncratic = np.zeros(days)
    for t in range(1, days):
        idiosyncratic[t] = idio_phi * idiosyncratic[t - 1] + eps[t]

    log_price = np.log(base_price) + beta * common_factor + idiosyncratic
    return pd.Series(np.exp(log_price))


def generate_synthetic_universe(tickers: list[str], days: int = 750) -> dict[str, pd.DataFrame]:
    """Generates a dict of ticker -> OHLCV dataframe with realistic correlated pairs."""
    end = utcnow().date()
    dates = pd.bdate_range(end=end, periods=days)
    rng_master = np.random.default_rng(42)
    market_factor = rng_master.normal(0.0002, 0.01, days).cumsum()

    data = {}
    related_map = {}
    for a, b in KNOWN_RELATED_PAIRS:
        related_map[a] = b
        related_map[b] = a

    seed_counter = 0
    generated_factors = {}
    for ticker in tickers:
        seed_counter += 1
        base_price = 50 + (hash(ticker) % 400)
        if ticker in related_map and related_map[ticker] in generated_factors:
            # reuse partner's idiosyncratic drift lightly to keep them cointegrated
            partner_factor = generated_factors[related_map[ticker]]
            common = 0.85 * partner_factor + 0.15 * market_factor
        else:
            common = market_factor
        series = _synthetic_series(
            ticker, days, seed=seed_counter, base_price=base_price,
            common_factor=common, beta=1.0, noise_scale=0.006,
        )
        generated_factors[ticker] = common
        close = series.values
        high = close * (1 + np.abs(np.random.default_rng(seed_counter + 100).normal(0, 0.004, days)))
        low = close * (1 - np.abs(np.random.default_rng(seed_counter + 200).normal(0, 0.004, days)))
        open_ = close * (1 + np.random.default_rng(seed_counter + 300).normal(0, 0.002, days))
        volume = np.random.default_rng(seed_counter + 400).integers(1_000_000, 20_000_000, days)

        df = pd.DataFrame({
            "date": dates, "open": open_, "high": high, "low": low,
            "close": close, "volume": volume,
        })
        data[ticker] = df

    return data


def _fetch_from_alpaca(tickers: list[str], days: int) -> dict[str, pd.DataFrame] | None:
    """
    Returns None (rather than raising) on any failure -- credentials missing, package
    not installed, network error, or empty response -- so the caller can move on to
    the next tier in the fallback chain without special-casing each failure mode.
    """
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        return None

    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        client = StockHistoricalDataClient(api_key, secret_key)
        end = utcnow()
        start = end - timedelta(days=int(days * 1.6))  # buffer for weekends/holidays

        request = StockBarsRequest(
            symbol_or_symbols=tickers, timeframe=TimeFrame.Day,
            start=start, end=end,
        )
        bar_set = client.get_stock_bars(request)
        df_all = bar_set.df  # MultiIndex (symbol, timestamp) DataFrame
        if df_all is None or df_all.empty:
            return None

        result = {}
        for ticker in tickers:
            try:
                sub = df_all.loc[ticker].reset_index()
                sub = sub.rename(columns={
                    "timestamp": "date", "open": "open", "high": "high",
                    "low": "low", "close": "close", "volume": "volume",
                })
                sub["date"] = pd.to_datetime(sub["date"]).dt.tz_localize(None)
                if sub.empty:
                    continue
                result[ticker] = sub[["date", "open", "high", "low", "close", "volume"]]
            except KeyError:
                continue  # this ticker had no bars in the response

        if len(result) < max(1, len(tickers) // 2):
            logger.warning(
                "Alpaca returned too few tickers, falling back",
                extra={"requested": len(tickers), "received": len(result)},
            )
            return None
        return result
    except Exception as e:
        logger.warning("Alpaca fetch failed, falling back", extra={"error": str(e)})
        return None


def _fetch_from_yfinance(tickers: list[str], days: int) -> dict[str, pd.DataFrame] | None:
    """Returns None (rather than raising) on any failure, same contract as Alpaca above."""
    try:
        import yfinance as yf
        end = utcnow()
        start = end - timedelta(days=int(days * 1.6))  # buffer for weekends/holidays
        raw = yf.download(tickers, start=start.date(), end=end.date(), group_by="ticker",
                           auto_adjust=True, progress=False, threads=True)
        if raw is None or raw.empty:
            return None

        result = {}
        for ticker in tickers:
            try:
                sub = raw[ticker].dropna().reset_index()
                sub = sub.rename(columns={
                    "Date": "date", "Open": "open", "High": "high",
                    "Low": "low", "Close": "close", "Volume": "volume",
                })
                if sub.empty:
                    continue
                result[ticker] = sub[["date", "open", "high", "low", "close", "volume"]]
            except Exception:
                continue

        if len(result) < max(1, len(tickers) // 2):
            return None
        return result
    except Exception as e:
        logger.warning("yfinance fetch failed, falling back", extra={"error": str(e)})
        return None


def fetch_price_history(tickers: list[str], days: int = 750) -> dict[str, pd.DataFrame]:
    """
    Three-tier fallback chain: Alpaca (if configured) -> yfinance -> synthetic.
    USE_SYNTHETIC_DATA=true skips straight to synthetic, useful for fast/offline dev
    and for demo deploys where you'd rather have clearly-synthetic-but-realistic data
    than a flaky third-party dependency.
    """
    if os.getenv("USE_SYNTHETIC_DATA", "false").lower() == "true":
        return generate_synthetic_universe(tickers, days=days)

    result = _fetch_from_alpaca(tickers, days)
    if result is not None:
        return result

    result = _fetch_from_yfinance(tickers, days)
    if result is not None:
        return result

    logger.info("All real data sources unavailable, using synthetic data")
    return generate_synthetic_universe(tickers, days=days)
