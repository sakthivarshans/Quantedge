import pandas as pd


def test_fetch_from_alpaca_returns_none_without_credentials(monkeypatch):
    """Missing API keys should fail open (return None), not raise -- this is what lets
    the fallback chain move on to yfinance/synthetic silently."""
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    from app.services.data_service import _fetch_from_alpaca
    result = _fetch_from_alpaca(["AAPL"], days=300)
    assert result is None


def test_fetch_from_alpaca_parses_response_correctly(monkeypatch):
    """Mocks Alpaca's client entirely (no real network access to Alpaca from this
    environment) to verify the response-parsing logic -- the MultiIndex (symbol,
    timestamp) DataFrame Alpaca returns gets reshaped into our standard
    date/open/high/low/close/volume format correctly."""
    monkeypatch.setenv("ALPACA_API_KEY", "fake-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "fake-secret")

    dates = pd.date_range("2025-01-01", periods=5, tz="UTC")
    mock_df = pd.DataFrame({
        "open": [100.0, 101.0, 102.0, 103.0, 104.0],
        "high": [101.0, 102.0, 103.0, 104.0, 105.0],
        "low": [99.0, 100.0, 101.0, 102.0, 103.0],
        "close": [100.5, 101.5, 102.5, 103.5, 104.5],
        "volume": [1_000_000] * 5,
    }, index=pd.MultiIndex.from_product([["AAPL"], dates], names=["symbol", "timestamp"]))

    class FakeBarSet:
        df = mock_df

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_stock_bars(self, request):
            return FakeBarSet()

    monkeypatch.setattr("alpaca.data.historical.StockHistoricalDataClient", FakeClient)

    from app.services.data_service import _fetch_from_alpaca
    result = _fetch_from_alpaca(["AAPL"], days=300)

    assert result is not None
    assert "AAPL" in result
    df = result["AAPL"]
    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert len(df) == 5
    assert df["close"].iloc[0] == 100.5


def test_fetch_from_alpaca_returns_none_on_client_error(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "fake-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "fake-secret")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            raise ConnectionError("simulated network failure")

    monkeypatch.setattr("alpaca.data.historical.StockHistoricalDataClient", FakeClient)

    from app.services.data_service import _fetch_from_alpaca
    result = _fetch_from_alpaca(["AAPL"], days=300)
    assert result is None


def test_fetch_price_history_prefers_alpaca_over_yfinance_and_synthetic(monkeypatch):
    """With USE_SYNTHETIC_DATA unset and a working (mocked) Alpaca response, the top
    of the fallback chain should win -- yfinance and synthetic should never be reached."""
    monkeypatch.delenv("USE_SYNTHETIC_DATA", raising=False)

    sentinel = {"AAPL": pd.DataFrame({"date": [], "open": [], "high": [], "low": [], "close": [], "volume": []})}
    monkeypatch.setattr("app.services.data_service._fetch_from_alpaca", lambda t, d: sentinel)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("yfinance should not be reached when Alpaca succeeds")
    monkeypatch.setattr("app.services.data_service._fetch_from_yfinance", fail_if_called)

    from app.services.data_service import fetch_price_history
    result = fetch_price_history(["AAPL"], days=300)
    assert result is sentinel


def test_fetch_price_history_falls_back_to_yfinance_when_alpaca_unavailable(monkeypatch):
    monkeypatch.delenv("USE_SYNTHETIC_DATA", raising=False)
    monkeypatch.setattr("app.services.data_service._fetch_from_alpaca", lambda t, d: None)

    sentinel = {"AAPL": pd.DataFrame({"date": [], "open": [], "high": [], "low": [], "close": [], "volume": []})}
    monkeypatch.setattr("app.services.data_service._fetch_from_yfinance", lambda t, d: sentinel)

    from app.services.data_service import fetch_price_history
    result = fetch_price_history(["AAPL"], days=300)
    assert result is sentinel


def test_fetch_price_history_falls_back_to_synthetic_when_both_unavailable(monkeypatch):
    monkeypatch.delenv("USE_SYNTHETIC_DATA", raising=False)
    monkeypatch.setattr("app.services.data_service._fetch_from_alpaca", lambda t, d: None)
    monkeypatch.setattr("app.services.data_service._fetch_from_yfinance", lambda t, d: None)

    from app.services.data_service import fetch_price_history
    result = fetch_price_history(["AAPL", "MSFT"], days=300)
    assert "AAPL" in result
    assert "MSFT" in result
    assert len(result["AAPL"]) > 0


def test_use_synthetic_data_env_var_skips_real_sources_entirely(monkeypatch):
    """USE_SYNTHETIC_DATA=true should short-circuit before even trying Alpaca/yfinance."""
    monkeypatch.setenv("USE_SYNTHETIC_DATA", "true")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("should not attempt real data sources when USE_SYNTHETIC_DATA=true")
    monkeypatch.setattr("app.services.data_service._fetch_from_alpaca", fail_if_called)
    monkeypatch.setattr("app.services.data_service._fetch_from_yfinance", fail_if_called)

    from app.services.data_service import fetch_price_history
    result = fetch_price_history(["AAPL"], days=300)
    assert "AAPL" in result


def test_scanner_cache_is_used_regardless_of_requested_top_n(monkeypatch):
    """
    Regression test for a real bug: the scanner cache used to only be read when
    top_n exactly equaled a hardcoded value (20), which none of the actual frontend
    requests (Scanner page asks for 30, Dashboard asks for 6) ever matched -- so the
    cache silently never got hit in practice, even though it looked correctly wired.
    This verifies the cache is consulted for arbitrary top_n values, and only the
    slicing changes, not whether the cache gets used at all.
    """
    from app.api.routes import scanner as scanner_module

    fake_cached_result = {
        "universe_size": 65,
        "opportunities": [{"pair": f"PAIR{i}", "confidence": 100 - i} for i in range(50)],
    }
    monkeypatch.setattr("app.workers.cache.get_cached_scan_result", lambda: fake_cached_result)

    for requested_top_n in [6, 20, 30, 50]:
        result = scanner_module.scan_market.__wrapped__(
            request=None, tickers=None, days=500, top_n=requested_top_n,
        )
        assert len(result["opportunities"]) == requested_top_n, (
            f"top_n={requested_top_n} should slice the cached result, not bypass the cache"
        )
