import numpy as np
from app.services.risk_service import value_at_risk, conditional_var, portfolio_risk_report
from app.services.optimizer_service import mean_variance_allocation, risk_parity_allocation, optimize_portfolio
import pandas as pd


def test_var_is_non_negative_for_typical_returns():
    rng = np.random.default_rng(1)
    returns = pd.Series(rng.normal(0, 0.01, 500))
    var = value_at_risk(returns, 0.95)
    assert var >= 0


def test_cvar_is_greater_than_or_equal_to_var():
    rng = np.random.default_rng(1)
    returns = pd.Series(rng.normal(0, 0.01, 500))
    var = value_at_risk(returns, 0.95)
    cvar = conditional_var(returns, 0.95)
    assert cvar >= var


def test_portfolio_risk_report_flags_concentration(synthetic_frames):
    positions = [
        {"ticker": "AAPL", "market_value": 50000},
        {"ticker": "MSFT", "market_value": 30000},
        {"ticker": "GOOG", "market_value": 15000},
        {"ticker": "V", "market_value": 5000},
    ]
    returns_by_ticker = {
        t: synthetic_frames[t].set_index("date")["close"].pct_change().dropna()
        for t in ["AAPL", "MSFT", "GOOG", "V"]
    }
    report = portfolio_risk_report(positions, returns_by_ticker)
    assert report["sector_exposure_pct"]["Technology"] > 90
    assert len(report["warnings"]) > 0


def test_mean_variance_weights_sum_to_one():
    returns = [0.02, 0.015, 0.01]
    cov = np.diag([0.04**2, 0.03**2, 0.05**2])
    weights = mean_variance_allocation(returns, cov)
    assert abs(sum(weights) - 1.0) < 1e-4
    assert all(w >= -1e-6 for w in weights)


def test_risk_parity_weights_sum_to_one():
    cov = np.diag([0.04**2, 0.03**2, 0.05**2])
    weights = risk_parity_allocation(cov)
    assert abs(sum(weights) - 1.0) < 1e-4


def test_risk_parity_gives_less_weight_to_higher_vol_asset():
    cov = np.diag([0.01**2, 0.10**2])  # asset 1 much more volatile
    weights = risk_parity_allocation(cov)
    assert weights[0] > weights[1]


def test_optimize_portfolio_allocations_match_capital():
    opps = [
        {"pair": "A/B", "expected_return": 0.02, "volatility": 0.04},
        {"pair": "C/D", "expected_return": 0.015, "volatility": 0.03},
    ]
    result = optimize_portfolio(opps, capital=100_000, method="mean_variance")
    total_allocated = sum(a["capital_allocated"] for a in result["allocations"])
    assert abs(total_allocated - 100_000) < 1.0
