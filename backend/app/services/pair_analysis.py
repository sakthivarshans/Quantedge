"""
Core quant engine: pairwise statistical relationship analysis.

Implements:
 - Pearson correlation
 - Engle-Granger two-step cointegration test (+ ADF on residuals)
 - OLS hedge ratio (dynamic, static)
 - Spread construction & z-score
 - Mean-reversion half-life (Ornstein-Uhlenbeck approximation via AR(1))
 - Signal generation (BUY / SELL / HOLD) with a confidence score
"""
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint, adfuller
import statsmodels.api as sm


def hedge_ratio(price_a: pd.Series, price_b: pd.Series) -> float:
    """OLS regression of A on B -> beta (hedge ratio)."""
    X = sm.add_constant(price_b.values)
    model = sm.OLS(price_a.values, X).fit()
    return float(model.params[1])


def compute_spread(price_a: pd.Series, price_b: pd.Series, beta: float) -> pd.Series:
    return price_a - beta * price_b


def half_life(spread: pd.Series) -> float:
    """Half-life of mean reversion via AR(1) fit on spread differences."""
    spread_lag = spread.shift(1).dropna()
    spread_ret = spread.diff().dropna()
    spread_lag = spread_lag.loc[spread_ret.index]
    X = sm.add_constant(spread_lag.values)
    model = sm.OLS(spread_ret.values, X).fit()
    theta = model.params[1]
    if theta >= 0:
        return float("inf")  # not mean reverting
    hl = -np.log(2) / theta
    return float(hl)


def zscore(spread: pd.Series, window: int = 30) -> pd.Series:
    mean = spread.rolling(window).mean()
    std = spread.rolling(window).std()
    return (spread - mean) / std


def engle_granger_test(price_a: pd.Series, price_b: pd.Series) -> dict:
    score, pvalue, crit_values = coint(price_a.values, price_b.values)
    return {"coint_stat": float(score), "p_value": float(pvalue),
            "crit_1pct": float(crit_values[0]), "crit_5pct": float(crit_values[1]),
            "crit_10pct": float(crit_values[2])}


def adf_test(series: pd.Series) -> dict:
    result = adfuller(series.dropna().values)
    return {"adf_stat": float(result[0]), "p_value": float(result[1]),
            "crit_1pct": float(result[4]["1%"]), "crit_5pct": float(result[4]["5%"]),
            "crit_10pct": float(result[4]["10%"])}


def analyze_pair(price_a: pd.Series, price_b: pd.Series, z_window: int = 30) -> dict:
    """Runs the full statistical pipeline for a single pair and returns all metrics."""
    correlation = float(price_a.corr(price_b))
    beta = hedge_ratio(price_a, price_b)
    spread = compute_spread(price_a, price_b, beta)
    z = zscore(spread, window=z_window)
    coint_result = engle_granger_test(price_a, price_b)
    adf_result = adf_test(spread)
    hl = half_life(spread)
    latest_z = float(z.iloc[-1]) if not np.isnan(z.iloc[-1]) else 0.0

    signal, confidence = generate_signal(latest_z, coint_result["p_value"], hl)

    return {
        "correlation": round(correlation, 4),
        "hedge_ratio": round(beta, 4),
        "cointegration": coint_result,
        "adf_on_spread": adf_result,
        "half_life_days": round(hl, 2) if np.isfinite(hl) else None,
        "latest_zscore": round(latest_z, 3),
        "spread": spread.tolist(),
        "zscore_series": z.fillna(0).tolist(),
        "signal": signal,
        "confidence": confidence,
    }


def generate_signal(latest_z: float, coint_pvalue: float, hl: float,
                     entry_threshold: float = 2.0) -> tuple[str, float]:
    """
    Signal logic:
      - Requires cointegration p-value < 0.05 (or at least < 0.10 for weak signal)
      - z > +threshold  -> spread too high -> SELL A / BUY B (short the spread)
      - z < -threshold  -> spread too low  -> BUY A / SELL B (long the spread)
      - Confidence blends cointegration strength, |z|, and mean-reversion speed
    """
    if coint_pvalue > 0.10 or not np.isfinite(hl) or hl <= 0 or hl > 90:
        return "HOLD", round(max(0.0, 40 - coint_pvalue * 100), 1)

    coint_strength = max(0.0, 1 - coint_pvalue / 0.10)  # 1.0 at p=0, 0 at p=0.10
    z_strength = min(1.0, abs(latest_z) / (entry_threshold * 1.5))
    speed_strength = min(1.0, 20 / max(hl, 1))
    confidence = round(100 * (0.45 * coint_strength + 0.4 * z_strength + 0.15 * speed_strength), 1)

    if latest_z >= entry_threshold:
        return "SELL", confidence
    elif latest_z <= -entry_threshold:
        return "BUY", confidence
    else:
        return "HOLD", confidence
