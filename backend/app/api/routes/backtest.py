from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, BacktestResult
from app.services.data_service import fetch_price_history
from app.services.backtest_service import run_backtest
from app.services.analytics_service import log_event

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    ticker_a: str
    ticker_b: str
    capital: float = 100_000
    entry_threshold: float = 2.0
    exit_threshold: float = 0.5
    stop_loss_z: float = 3.5
    z_window: int = 30
    days: int = 750


@router.post("")
def backtest(req: BacktestRequest, db: Session = Depends(get_db)):
    """Synchronous backtest -- blocks until done. Fine for a quick one-off run; for
    longer backtests or when you want a persisted history, use POST /async instead."""
    a, b = req.ticker_a.upper(), req.ticker_b.upper()
    frames = fetch_price_history([a, b], days=req.days)
    if a not in frames or b not in frames:
        raise HTTPException(status_code=404, detail="Could not fetch data for one or both tickers")

    df_a = frames[a].set_index("date")
    df_b = frames[b].set_index("date")
    pa, pb = df_a["close"].align(df_b["close"], join="inner")

    result = run_backtest(
        pa, pb, capital=req.capital, entry_threshold=req.entry_threshold,
        exit_threshold=req.exit_threshold, stop_loss_z=req.stop_loss_z, z_window=req.z_window,
    )
    result["dates"] = [d.strftime("%Y-%m-%d") for d in pa.index]
    result["ticker_a"], result["ticker_b"] = a, b
    # This endpoint has no auth requirement (a quick anonymous backtest is a reasonable
    # thing to allow), so the event is logged without a user_id rather than skipped.
    log_event(db, "backtest_run", metadata={"pair": f"{a}/{b}", "sharpe_ratio": result["metrics"]["sharpe_ratio"]})
    return result


@router.post("/async")
def submit_backtest_job(req: BacktestRequest, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    """Queues the backtest as a Celery background job and returns immediately with a
    job id to poll. Also persists the result (success or failure) for later viewing
    via GET /history."""
    a, b = req.ticker_a.upper(), req.ticker_b.upper()
    job = BacktestResult(
        user_id=user.id, ticker_a=a, ticker_b=b, status="PENDING",
        params={
            "capital": req.capital, "entry_threshold": req.entry_threshold,
            "exit_threshold": req.exit_threshold, "stop_loss_z": req.stop_loss_z,
            "z_window": req.z_window, "days": req.days,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from app.workers.tasks import run_backtest_job
    async_result = run_backtest_job.delay(job.id)
    job.task_id = async_result.id
    db.commit()
    log_event(db, "backtest_run_async", user_id=user.id, metadata={"pair": f"{a}/{b}", "job_id": job.id})

    return {"job_id": job.id, "task_id": job.task_id, "status": job.status}


@router.get("/jobs/{job_id}")
def get_job_status(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = db.query(BacktestResult).filter(
        BacktestResult.id == job_id, BacktestResult.user_id == user.id
    ).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.id, "status": job.status, "ticker_a": job.ticker_a, "ticker_b": job.ticker_b,
        "params": job.params, "metrics": job.metrics, "equity_curve": job.equity_curve,
        "error": job.error, "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.get("/history")
def get_backtest_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    jobs = (
        db.query(BacktestResult)
        .filter(BacktestResult.user_id == user.id)
        .order_by(BacktestResult.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "job_id": j.id, "status": j.status, "pair": f"{j.ticker_a}/{j.ticker_b}",
            "metrics": j.metrics, "created_at": j.created_at.isoformat(),
        }
        for j in jobs
    ]
