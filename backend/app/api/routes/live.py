import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.api.routes.scanner import _scan_market_core
from app.workers.cache import get_cached_scan_result

router = APIRouter(tags=["live"])


def _get_latest_scan() -> dict:
    cached = get_cached_scan_result()
    if cached is not None:
        return {**cached, "opportunities": cached["opportunities"][:15]}
    return _scan_market_core(tickers=None, days=500, top_n=15)


@router.websocket("/ws/live-scanner")
async def live_scanner(websocket: WebSocket, interval_seconds: int = 15):
    """
    Streams the market scanner results every `interval_seconds`. Reads from the same
    Redis cache the Celery worker populates (see app/workers/), so an arbitrary number
    of connected clients share one underlying computation instead of each triggering
    their own scan.
    """
    await websocket.accept()
    try:
        while True:
            result = _get_latest_scan()
            await websocket.send_text(json.dumps({"type": "scanner_update", "data": result}))
            await asyncio.sleep(interval_seconds)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
