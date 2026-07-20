"""
Celery worker configuration.

Architecture: Celery Beat schedules the market scan every N seconds; a Celery worker
picks it up and runs the (expensive) pairwise cointegration scan; the result is cached
in Redis. The API and WebSocket layers read from that cache instead of recomputing the
scan on every request -- so scanner reads are O(1) regardless of how many users are
watching, and the actual computation happens once per interval, off the request path.

Falls back gracefully: if Redis is unreachable, the API layer computes the scan inline
(the same synchronous path used before this phase) so the app still works without the
worker infrastructure running -- useful for quick local dev.
"""
import os
from celery import Celery
from celery.schedules import schedule

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "30"))

celery_app = Celery("quantedge", broker=REDIS_URL, backend=REDIS_URL, include=["app.workers.tasks"])

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Eager mode runs tasks synchronously in-process instead of dispatching to a worker --
    # used by the test suite so tests don't depend on a live Celery worker being up.
    task_always_eager=os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true",
    task_eager_propagates=True,
    beat_schedule={
        "refresh-market-scan": {
            "task": "app.workers.tasks.refresh_market_scan",
            "schedule": schedule(run_every=SCAN_INTERVAL_SECONDS),
        },
    },
)
