import pytest
from app.services.research_service import (
    run_correlation_matrix, run_pair_diagnostics, run_rolling_stats, run_beta_exposure, run_cell,
)


def test_correlation_matrix_shape():
    result = run_correlation_matrix(["AAPL", "MSFT", "V"], days=300)
    assert len(result["tickers"]) == 3
    assert len(result["matrix"]) == 3
    assert len(result["matrix"][0]) == 3
    # diagonal should be 1.0 (self-correlation)
    for i in range(3):
        assert abs(result["matrix"][i][i] - 1.0) < 1e-6


def test_pair_diagnostics_matches_pair_analysis_fields():
    result = run_pair_diagnostics("V", "MA", days=300)
    assert result["ticker_a"] == "V"
    assert "cointegration" in result
    assert "signal" in result


def test_rolling_stats_returns_series_per_ticker():
    result = run_rolling_stats(["AAPL", "MSFT"], window=20, days=300)
    assert "AAPL" in result["series"]
    assert "MSFT" in result["series"]
    assert result["series"]["AAPL"]["latest_volatility"] is not None


def test_beta_exposure_returns_reasonable_values():
    result = run_beta_exposure(["MSFT", "V"], benchmark="AAPL", days=300)
    assert result["benchmark"] == "AAPL"
    tickers = [e["ticker"] for e in result["exposures"]]
    assert "MSFT" in tickers
    assert "AAPL" not in tickers  # benchmark excluded from its own exposure list


def test_run_cell_dispatches_correctly():
    result = run_cell("correlation_matrix", {"tickers": ["AAPL", "MSFT"], "days": 300})
    assert "tickers" in result


def test_run_cell_rejects_unknown_type():
    with pytest.raises(ValueError):
        run_cell("not_a_real_cell_type", {})
