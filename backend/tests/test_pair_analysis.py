import numpy as np
from app.services.pair_analysis import (
    analyze_pair, hedge_ratio, compute_spread, zscore, half_life,
    engle_granger_test, generate_signal,
)


def test_cointegrated_pair_detected(cointegrated_pair):
    pa, pb = cointegrated_pair
    result = engle_granger_test(pa, pb)
    assert result["p_value"] < 0.05, "known cointegrated pair should test significant"


def test_hedge_ratio_is_reasonable(cointegrated_pair):
    pa, pb = cointegrated_pair
    beta = hedge_ratio(pa, pb)
    assert 0.1 < abs(beta) < 10, f"hedge ratio {beta} outside sane bounds"


def test_spread_is_computed_correctly(cointegrated_pair):
    pa, pb = cointegrated_pair
    beta = hedge_ratio(pa, pb)
    spread = compute_spread(pa, pb, beta)
    expected = pa.iloc[0] - beta * pb.iloc[0]
    assert abs(spread.iloc[0] - expected) < 1e-9


def test_zscore_normalizes_to_roughly_unit_variance(cointegrated_pair):
    pa, pb = cointegrated_pair
    beta = hedge_ratio(pa, pb)
    spread = compute_spread(pa, pb, beta)
    z = zscore(spread, window=30).dropna()
    assert -1 < z.mean() < 1
    assert 0.5 < z.std() < 2.0


def test_half_life_positive_for_mean_reverting_spread(cointegrated_pair):
    pa, pb = cointegrated_pair
    beta = hedge_ratio(pa, pb)
    spread = compute_spread(pa, pb, beta)
    hl = half_life(spread)
    assert hl > 0, "a genuinely mean-reverting spread should have positive half-life"
    assert hl < 100, "half-life should be reasonably short for an engineered stationary spread"


def test_analyze_pair_returns_all_expected_fields(cointegrated_pair):
    pa, pb = cointegrated_pair
    result = analyze_pair(pa, pb)
    for key in ["correlation", "hedge_ratio", "cointegration", "adf_on_spread",
                "half_life_days", "latest_zscore", "signal", "confidence"]:
        assert key in result
    assert result["signal"] in ("BUY", "SELL", "HOLD")
    assert 0 <= result["confidence"] <= 100


def test_signal_generation_buy_on_very_negative_z():
    signal, confidence = generate_signal(latest_z=-2.5, coint_pvalue=0.001, hl=10)
    assert signal == "BUY"
    assert confidence > 0


def test_signal_generation_sell_on_very_positive_z():
    signal, confidence = generate_signal(latest_z=2.5, coint_pvalue=0.001, hl=10)
    assert signal == "SELL"


def test_signal_generation_hold_when_not_cointegrated():
    signal, _ = generate_signal(latest_z=3.0, coint_pvalue=0.5, hl=10)
    assert signal == "HOLD"


def test_signal_generation_hold_on_weak_z():
    signal, _ = generate_signal(latest_z=0.3, coint_pvalue=0.001, hl=10)
    assert signal == "HOLD"


def test_independent_random_walks_generally_not_cointegrated():
    """
    Sanity check on the statistical test itself (not the synthetic data generator):
    two genuinely independent random walks should fail the cointegration test far
    more often than not. Note the synthetic universe generator intentionally shares
    a common market factor across ALL tickers for realism, so even "unrelated"
    tickers within it are not a valid negative-control case -- that's why this test
    builds its own independent series instead of reusing the fixtures.
    """
    import pandas as pd
    false_positive_count = 0
    trials = 20
    for seed in range(trials):
        rng = np.random.default_rng(seed * 1000 + 1)
        a = pd.Series(np.exp(np.log(100) + rng.normal(0, 0.01, 500).cumsum()))
        rng2 = np.random.default_rng(seed * 1000 + 2)
        b = pd.Series(np.exp(np.log(100) + rng2.normal(0, 0.01, 500).cumsum()))
        result = engle_granger_test(a, b)
        if result["p_value"] < 0.05:
            false_positive_count += 1
    # Engle-Granger at 5% significance should false-positive on well under half of trials
    # for genuinely independent series
    assert false_positive_count < trials * 0.4
