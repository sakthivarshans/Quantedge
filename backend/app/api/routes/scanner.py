from itertools import combinations
from fastapi import APIRouter, Query, Request
import pandas as pd
from app.services.data_service import fetch_price_history, DEFAULT_UNIVERSE, KNOWN_RELATED_PAIRS
from app.services.pair_analysis import analyze_pair
from app.core.rate_limit import limiter

router = APIRouter(prefix="/api/scanner", tags=["scanner"])

_cache: dict = {}

# The background worker always computes and caches this many results for the default
# (full-universe) scan; individual requests then just slice down to their requested
# top_n. This is what actually makes the cache useful: caching only worked for one
# exact top_n value before, which none of the frontend's real requests (30, then 6)
# ever matched -- so every page load was paying the full inline computation cost.
CACHED_RESULT_SIZE = 50


def _get_price_frames(tickers: list[str], days: int) -> dict[str, pd.DataFrame]:
    key = (tuple(sorted(tickers)), days)
    if key not in _cache:
        _cache[key] = fetch_price_history(tickers, days=days)
    return _cache[key]


def _scan_market_core(tickers: str = None, days: int = 500, top_n: int = 20):
    universe = tickers.split(",") if tickers else DEFAULT_UNIVERSE
    frames = _get_price_frames(universe, days)
    closes = {t: df.set_index("date")["close"] for t, df in frames.items()}

    # Prioritize known related pairs first, then scan a limited number of remaining combos
    # (full N^2 scan is expensive; production would parallelize/cache this)
    candidate_pairs = list(KNOWN_RELATED_PAIRS)
    others = [p for p in combinations(sorted(closes.keys()), 2) if p not in candidate_pairs][:40]
    candidate_pairs += others

    results = []
    for a, b in candidate_pairs:
        if a not in closes or b not in closes:
            continue
        pa, pb = closes[a].align(closes[b], join="inner")
        if len(pa) < 60:
            continue
        try:
            analysis = analyze_pair(pa, pb)
        except Exception:
            continue
        results.append({
            "pair": f"{a}/{b}",
            "ticker_a": a, "ticker_b": b,
            "signal": analysis["signal"],
            "confidence": analysis["confidence"],
            "correlation": analysis["correlation"],
            "cointegration_pvalue": analysis["cointegration"]["p_value"],
            "half_life_days": analysis["half_life_days"],
            "latest_zscore": analysis["latest_zscore"],
            "expected_return_pct": round(min(abs(analysis["latest_zscore"]) * 0.9, 5.0), 2),
        })

    results = [r for r in results if r["signal"] != "HOLD"]
    results.sort(key=lambda r: r["confidence"], reverse=True)
    return {"universe_size": len(universe), "opportunities": results[:top_n]}


def _is_default_scan(tickers: str | None, days: int) -> bool:
    """Whether this request matches the shape the background worker caches --
    top_n is deliberately excluded from this check (see CACHED_RESULT_SIZE above)."""
    return tickers is None and days == 500


@router.get("")
@limiter.limit("20/minute")
def scan_market(request: Request, tickers: str = Query(None, description="Comma-separated tickers; defaults to full universe"),
                 days: int = 500, top_n: int = 20):
    if _is_default_scan(tickers, days):
        from app.workers.cache import get_cached_scan_result
        cached = get_cached_scan_result()
        if cached is not None:
            return {**cached, "opportunities": cached["opportunities"][:top_n]}
    return _scan_market_core(tickers, days, top_n)
