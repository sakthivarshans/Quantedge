"""
Paper trading engine.

A paper trade is a simulated pairs position: LONG_SPREAD (buy A, sell B*hedge_ratio)
when z is very negative, or SHORT_SPREAD (sell A, buy B*hedge_ratio) when z is very
positive. PnL is mark-to-market against current prices using the hedge ratio captured
at entry, and positions are flagged to auto-close when z reverts through the exit
threshold or blows through the stop-loss.
"""
from app.core.time import utcnow
from sqlalchemy.orm import Session
from app.models import PaperTrade
from app.services.data_service import fetch_price_history
from app.services.pair_analysis import hedge_ratio, compute_spread, zscore
from app.services.analytics_service import log_event


def open_trade(db: Session, user_id: int, ticker_a: str, ticker_b: str,
                capital_allocated: float = 10000.0, z_window: int = 30) -> PaperTrade:
    frames = fetch_price_history([ticker_a, ticker_b], days=250)
    if ticker_a not in frames or ticker_b not in frames:
        raise ValueError("Could not fetch price data for one or both tickers")

    pa = frames[ticker_a].set_index("date")["close"]
    pb = frames[ticker_b].set_index("date")["close"]
    pa, pb = pa.align(pb, join="inner")

    beta = hedge_ratio(pa, pb)
    spread = compute_spread(pa, pb, beta)
    z = zscore(spread, window=z_window)
    latest_z = float(z.iloc[-1])

    direction = "LONG_SPREAD" if latest_z < 0 else "SHORT_SPREAD"

    trade = PaperTrade(
        user_id=user_id, ticker_a=ticker_a, ticker_b=ticker_b, direction=direction,
        hedge_ratio=round(beta, 4), entry_z=round(latest_z, 3),
        entry_price_a=round(float(pa.iloc[-1]), 2), entry_price_b=round(float(pb.iloc[-1]), 2),
        capital_allocated=capital_allocated, status="OPEN", opened_at=utcnow(),
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    log_event(db, "trade_opened", user_id=user_id, metadata={
        "pair": f"{ticker_a}/{ticker_b}", "direction": direction, "capital_allocated": capital_allocated,
    })
    return trade


def _mark_to_market(trade: PaperTrade, price_a: float, price_b: float) -> float:
    """PnL for a unit-scaled spread position, scaled by capital_allocated."""
    entry_spread = trade.entry_price_a - trade.hedge_ratio * trade.entry_price_b
    current_spread = price_a - trade.hedge_ratio * price_b
    spread_change = current_spread - entry_spread
    # LONG_SPREAD profits when spread rises back toward zero from a very negative z;
    # SHORT_SPREAD profits when spread falls back toward zero from a very positive z.
    direction_sign = 1 if trade.direction == "LONG_SPREAD" else -1
    # Normalize by entry spread magnitude so pnl scales sensibly with capital_allocated
    denom = max(abs(entry_spread), 1.0)
    pnl_pct = direction_sign * spread_change / denom
    return round(trade.capital_allocated * pnl_pct, 2)


def get_portfolio(db: Session, user_id: int) -> dict:
    trades = db.query(PaperTrade).filter(PaperTrade.user_id == user_id).order_by(PaperTrade.opened_at.desc()).all()
    open_trades = [t for t in trades if t.status == "OPEN"]
    closed_trades = [t for t in trades if t.status == "CLOSED"]

    tickers = sorted({t.ticker_a for t in open_trades} | {t.ticker_b for t in open_trades})
    frames = fetch_price_history(tickers, days=250) if tickers else {}

    open_results = []
    total_unrealized = 0.0
    for t in open_trades:
        pa = frames.get(t.ticker_a)
        pb = frames.get(t.ticker_b)
        current_a = float(pa["close"].iloc[-1]) if pa is not None else t.entry_price_a
        current_b = float(pb["close"].iloc[-1]) if pb is not None else t.entry_price_b

        z_series = None
        if pa is not None and pb is not None:
            sa, sb = pa.set_index("date")["close"].align(pb.set_index("date")["close"], join="inner")
            spread = compute_spread(sa, sb, t.hedge_ratio)
            z_series = zscore(spread, window=30)

        current_z = float(z_series.iloc[-1]) if z_series is not None else None
        pnl = _mark_to_market(t, current_a, current_b)
        total_unrealized += pnl

        should_close = False
        if current_z is not None:
            if t.direction == "LONG_SPREAD" and (current_z >= -0.5 or current_z <= -3.5):
                should_close = True
            if t.direction == "SHORT_SPREAD" and (current_z <= 0.5 or current_z >= 3.5):
                should_close = True

        open_results.append({
            "id": t.id, "pair": f"{t.ticker_a}/{t.ticker_b}", "direction": t.direction,
            "hedge_ratio": t.hedge_ratio, "entry_z": t.entry_z, "current_z": round(current_z, 3) if current_z else None,
            "entry_price_a": t.entry_price_a, "entry_price_b": t.entry_price_b,
            "current_price_a": round(current_a, 2), "current_price_b": round(current_b, 2),
            "capital_allocated": t.capital_allocated, "unrealized_pnl": pnl,
            "opened_at": t.opened_at.isoformat(), "suggest_close": should_close,
        })

    closed_results = [{
        "id": t.id, "pair": f"{t.ticker_a}/{t.ticker_b}", "direction": t.direction,
        "pnl": t.pnl, "opened_at": t.opened_at.isoformat(),
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
    } for t in closed_trades]

    realized_pnl = sum(t.pnl or 0 for t in closed_trades)
    starting_capital = 100_000.0
    equity = starting_capital + realized_pnl + total_unrealized

    return {
        "starting_capital": starting_capital,
        "equity": round(equity, 2),
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": round(total_unrealized, 2),
        "open_positions": open_results,
        "closed_positions": closed_results,
    }


def close_trade(db: Session, user_id: int, trade_id: int) -> PaperTrade:
    trade = db.query(PaperTrade).filter(PaperTrade.id == trade_id, PaperTrade.user_id == user_id).first()
    if trade is None:
        raise ValueError("Trade not found")
    if trade.status != "OPEN":
        raise ValueError("Trade is already closed")

    frames = fetch_price_history([trade.ticker_a, trade.ticker_b], days=250)
    pa = frames[trade.ticker_a]["close"].iloc[-1]
    pb = frames[trade.ticker_b]["close"].iloc[-1]
    pnl = _mark_to_market(trade, float(pa), float(pb))

    trade.exit_price_a = round(float(pa), 2)
    trade.exit_price_b = round(float(pb), 2)
    trade.pnl = pnl
    trade.status = "CLOSED"
    trade.closed_at = utcnow()
    db.commit()
    db.refresh(trade)
    log_event(db, "trade_closed", user_id=user_id, metadata={
        "pair": f"{trade.ticker_a}/{trade.ticker_b}", "pnl": pnl, "won": pnl >= 0,
    })
    return trade
