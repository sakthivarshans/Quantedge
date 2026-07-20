from app.services.backtest_service import run_backtest


def test_backtest_returns_expected_shape(cointegrated_pair):
    pa, pb = cointegrated_pair
    result = run_backtest(pa, pb, capital=100_000)
    assert "metrics" in result
    assert "equity_curve" in result
    assert len(result["equity_curve"]) == len(pa)
    m = result["metrics"]
    for key in ["total_return_pct", "sharpe_ratio", "sortino_ratio", "max_drawdown_pct",
                "num_trades", "win_rate_pct", "final_equity"]:
        assert key in m


def test_backtest_final_equity_is_positive(cointegrated_pair):
    pa, pb = cointegrated_pair
    result = run_backtest(pa, pb, capital=100_000)
    assert result["metrics"]["final_equity"] > 0


def test_backtest_max_drawdown_is_non_positive(cointegrated_pair):
    pa, pb = cointegrated_pair
    result = run_backtest(pa, pb, capital=100_000)
    assert result["metrics"]["max_drawdown_pct"] <= 0


def test_backtest_higher_entry_threshold_trades_less_often(cointegrated_pair):
    pa, pb = cointegrated_pair
    loose = run_backtest(pa, pb, entry_threshold=1.0)
    strict = run_backtest(pa, pb, entry_threshold=3.0)
    assert strict["metrics"]["num_trades"] <= loose["metrics"]["num_trades"]


def test_backtest_positions_are_within_valid_range(cointegrated_pair):
    pa, pb = cointegrated_pair
    result = run_backtest(pa, pb)
    assert all(p in (-1, 0, 1) for p in result["positions"])
