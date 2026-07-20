from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.services import paper_trading_service as svc

router = APIRouter(prefix="/api/paper-trading", tags=["paper-trading"])


class OpenTradeRequest(BaseModel):
    ticker_a: str
    ticker_b: str
    capital_allocated: float = 10000.0


@router.post("/open")
def open_trade(req: OpenTradeRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        trade = svc.open_trade(
            db, user.id, req.ticker_a.upper(), req.ticker_b.upper(), req.capital_allocated,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "id": trade.id, "pair": f"{trade.ticker_a}/{trade.ticker_b}", "direction": trade.direction,
        "entry_z": trade.entry_z, "hedge_ratio": trade.hedge_ratio, "status": trade.status,
    }


@router.post("/close/{trade_id}")
def close_trade(trade_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        trade = svc.close_trade(db, user.id, trade_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": trade.id, "status": trade.status, "pnl": trade.pnl}


@router.get("/portfolio")
def portfolio(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return svc.get_portfolio(db, user.id)
