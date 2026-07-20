import numpy as np
from scipy.optimize import minimize


def mean_variance_allocation(expected_returns: list[float], cov_matrix: np.ndarray,
                              risk_aversion: float = 3.0) -> list[float]:
    """Maximize expected_return - risk_aversion * variance, subject to weights summing to 1, long-only."""
    n = len(expected_returns)
    mu = np.array(expected_returns)

    def objective(w):
        port_return = w @ mu
        port_var = w @ cov_matrix @ w
        return -(port_return - risk_aversion * port_var)

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds = [(0.0, 1.0)] * n
    x0 = np.ones(n) / n
    result = minimize(objective, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    weights = result.x if result.success else x0
    weights = np.clip(weights, 0, None)
    weights = weights / weights.sum()
    return weights.tolist()


def risk_parity_allocation(cov_matrix: np.ndarray) -> list[float]:
    """Equal risk contribution allocation."""
    n = cov_matrix.shape[0]

    def risk_contribution(w):
        port_vol = np.sqrt(w @ cov_matrix @ w)
        marginal = cov_matrix @ w / max(port_vol, 1e-9)
        return w * marginal

    def objective(w):
        rc = risk_contribution(w)
        target = np.mean(rc)
        return np.sum((rc - target) ** 2)

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds = [(0.001, 1.0)] * n
    x0 = np.ones(n) / n
    result = minimize(objective, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    weights = result.x if result.success else x0
    weights = np.clip(weights, 0, None)
    weights = weights / weights.sum()
    return weights.tolist()


def optimize_portfolio(opportunities: list[dict], capital: float, method: str = "mean_variance") -> dict:
    """
    opportunities: [{"pair": "V/MA", "expected_return": 0.023, "volatility": 0.05, "correlation_group": ...}]
    Builds a simple diagonal covariance matrix from volatilities (assumes low cross-correlation
    between distinct arbitrage opportunities, a standard simplifying assumption for this layer).
    """
    n = len(opportunities)
    if n == 0:
        return {"allocations": []}
    vols = np.array([o["volatility"] for o in opportunities])
    cov = np.diag(vols ** 2)
    returns = [o["expected_return"] for o in opportunities]

    if method == "risk_parity":
        weights = risk_parity_allocation(cov)
    else:
        weights = mean_variance_allocation(returns, cov)

    allocations = []
    for o, w in zip(opportunities, weights):
        allocations.append({
            "pair": o["pair"],
            "weight_pct": round(w * 100, 2),
            "capital_allocated": round(w * capital, 2),
            "expected_return_pct": round(o["expected_return"] * 100, 2),
        })
    return {"method": method, "allocations": allocations}
