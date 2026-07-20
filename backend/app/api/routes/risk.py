from fastapi import APIRouter
from pydantic import BaseModel
from app.services.data_service import fetch_price_history
from app.services.risk_service import portfolio_risk_report
from app.services.optimizer_service import optimize_portfolio


router = APIRouter(prefix="/api/risk", tags=["risk"])
opt_router = APIRouter(prefix="/api/optimizer", tags=["optimizer"])


class Position(BaseModel):
    ticker: str
    market_value: float


class RiskRequest(BaseModel):
    positions: list[Position]
    days: int = 250


@router.post("")
def risk_report(req: RiskRequest):
    tickers = [p.ticker for p in req.positions]
    frames = fetch_price_history(tickers, days=req.days)
    returns_by_ticker = {
        t: frames[t].set_index("date")["close"].pct_change().dropna()
        for t in tickers if t in frames
    }
    positions = [{"ticker": p.ticker, "market_value": p.market_value} for p in req.positions]
    return portfolio_risk_report(positions, returns_by_ticker)


class Opportunity(BaseModel):
    pair: str
    expected_return: float
    volatility: float


class OptimizeRequest(BaseModel):
    opportunities: list[Opportunity]
    capital: float = 100_000
    method: str = "mean_variance"  # or "risk_parity"


@opt_router.post("")
def optimize(req: OptimizeRequest):
    opps = [o.model_dump() for o in req.opportunities]
    return optimize_portfolio(opps, req.capital, req.method)
