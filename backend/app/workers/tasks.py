import logging
from app.core.time import utcnow
from app.workers.celery_app import celery_app
from app.workers.cache import set_scan_result

logger = logging.getLogger("quantedge")


@celery_app.task(name="app.workers.tasks.refresh_market_scan")
def refresh_market_scan():
    """
    Runs the (expensive) pairwise cointegration scan across the full ticker universe
    and caches the result in Redis. Scheduled by Celery Beat every SCAN_INTERVAL_SECONDS.
    """
    from app.api.routes.scanner import _scan_market_core, CACHED_RESULT_SIZE

    result = _scan_market_core(tickers=None, days=500, top_n=CACHED_RESULT_SIZE)
    set_scan_result(result)
    logger.info(
        "market scan refreshed",
        extra={"num_opportunities": len(result["opportunities"]), "universe_size": result["universe_size"]},
    )
    return {"num_opportunities": len(result["opportunities"])}


@celery_app.task(name="app.workers.tasks.run_backtest_job", bind=True)
def run_backtest_job(self, backtest_result_id: int):
    """
    Runs a single backtest in the background and writes the result back to the
    backtest_results row that was created (in PENDING status) when the job was submitted.
    Submitted via POST /api/backtest/async; status polled via GET /api/backtest/jobs/{id}.
    """
    from app.core.database import SessionLocal
    from app.models import BacktestResult
    from app.services.data_service import fetch_price_history
    from app.services.backtest_service import run_backtest as run_backtest_calc

    db = SessionLocal()
    try:
        job = db.query(BacktestResult).filter(BacktestResult.id == backtest_result_id).first()
        if job is None:
            logger.error("backtest job not found", extra={"backtest_result_id": backtest_result_id})
            return

        job.status = "RUNNING"
        job.task_id = self.request.id
        db.commit()

        params = job.params or {}
        frames = fetch_price_history([job.ticker_a, job.ticker_b], days=params.get("days", 750))
        pa = frames[job.ticker_a].set_index("date")["close"]
        pb = frames[job.ticker_b].set_index("date")["close"]
        pa, pb = pa.align(pb, join="inner")

        result = run_backtest_calc(
            pa, pb,
            capital=params.get("capital", 100_000),
            entry_threshold=params.get("entry_threshold", 2.0),
            exit_threshold=params.get("exit_threshold", 0.5),
            stop_loss_z=params.get("stop_loss_z", 3.5),
            z_window=params.get("z_window", 30),
        )

        job.metrics = result["metrics"]
        job.equity_curve = result["equity_curve"]
        job.status = "SUCCESS"
        job.completed_at = utcnow()
        db.commit()
        logger.info("backtest job completed", extra={"backtest_result_id": backtest_result_id})
        return {"status": "SUCCESS", "backtest_result_id": backtest_result_id}

    except Exception as e:
        db.rollback()
        job = db.query(BacktestResult).filter(BacktestResult.id == backtest_result_id).first()
        if job:
            job.status = "FAILED"
            job.error = str(e)
            job.completed_at = utcnow()
            db.commit()
        logger.error("backtest job failed", extra={"backtest_result_id": backtest_result_id, "error": str(e)})
        return {"status": "FAILED", "backtest_result_id": backtest_result_id, "error": str(e)}
    finally:
        db.close()
