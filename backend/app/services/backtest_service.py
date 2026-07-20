"""
Vectorized pairs-trading backtester.

Strategy: enter long-spread when z <= -entry_threshold, short-spread when
z >= +entry_threshold, exit when z crosses back through exit_threshold
(or hits stop_loss in z-space). Position sized as a fraction of capital.
"""
import numpy as np
import pandas as pd
from app.services.pair_analysis import hedge_ratio, compute_spread, zscore


def run_backtest(price_a: pd.Series, price_b: pd.Series, capital: float = 100_000,
                  entry_threshold: float = 2.0, exit_threshold: float = 0.5,
                  stop_loss_z: float = 3.5, z_window: int = 30) -> dict:
    beta = hedge_ratio(price_a, price_b)
    spread = compute_spread(price_a, price_b, beta)
    z = zscore(spread, window=z_window)

    position = 0  # -1 short spread, +1 long spread, 0 flat
    positions = []
    for zi in z:
        if np.isnan(zi):
            positions.append(0)
            continue
        if position == 0:
            if zi <= -entry_threshold:
                position = 1
            elif zi >= entry_threshold:
                position = -1
        elif position == 1:
            if zi >= -exit_threshold or zi <= -stop_loss_z:
                position = 0
        elif position == -1:
            if zi <= exit_threshold or zi >= stop_loss_z:
                position = 0
        positions.append(position)

    positions = pd.Series(positions, index=spread.index).shift(1).fillna(0)  # trade next bar
    spread_returns = spread.diff().fillna(0)
    strategy_pnl = positions * spread_returns
    equity_curve = capital + strategy_pnl.cumsum() * (capital * 0.01 / max(spread.std(), 1e-6))
    equity_returns = equity_curve.pct_change().fillna(0)

    total_return = float((equity_curve.iloc[-1] / capital) - 1)
    ann_factor = 252
    ann_return = float((1 + total_return) ** (ann_factor / max(len(equity_curve), 1)) - 1)
    ann_vol = float(equity_returns.std() * np.sqrt(ann_factor))
    sharpe = float(ann_return / ann_vol) if ann_vol > 0 else 0.0

    downside = equity_returns[equity_returns < 0]
    downside_vol = float(downside.std() * np.sqrt(ann_factor)) if len(downside) else 0.0
    sortino = float(ann_return / downside_vol) if downside_vol > 0 else 0.0

    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max
    max_drawdown = float(drawdown.min())

    trade_changes = positions.diff().fillna(0)
    num_trades = int((trade_changes != 0).sum())
    wins = int(((strategy_pnl > 0) & (positions.shift(-1) == 0) & (positions != 0)).sum())
    win_rate = float(wins / num_trades) if num_trades > 0 else 0.0

    return {
        "hedge_ratio": round(beta, 4),
        "metrics": {
            "total_return_pct": round(total_return * 100, 2),
            "annual_return_pct": round(ann_return * 100, 2),
            "annual_volatility_pct": round(ann_vol * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "max_drawdown_pct": round(max_drawdown * 100, 2),
            "num_trades": num_trades,
            "win_rate_pct": round(win_rate * 100, 2),
            "final_equity": round(float(equity_curve.iloc[-1]), 2),
        },
        "equity_curve": [round(v, 2) for v in equity_curve.tolist()],
        "positions": positions.astype(int).tolist(),
        "zscore_series": z.fillna(0).tolist(),
    }
