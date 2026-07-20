"""
Thin Redis cache wrapper for scanner results. Isolated here so both the Celery task
(which writes) and the API/WebSocket layer (which reads) share one implementation,
and so the "Redis unreachable -> fall back to inline computation" logic lives in one
place instead of being duplicated.
"""
import json
import logging
import os

logger = logging.getLogger("quantedge")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SCAN_CACHE_KEY = "quantedge:scanner:latest"
SCAN_CACHE_TTL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "30")) * 3

_redis_client = None


def _get_client():
    global _redis_client
    if _redis_client is None:
        import redis
        _redis_client = redis.from_url(REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
    return _redis_client


def set_scan_result(result: dict) -> None:
    try:
        client = _get_client()
        client.set(SCAN_CACHE_KEY, json.dumps(result), ex=SCAN_CACHE_TTL_SECONDS)
    except Exception as e:
        logger.warning("Could not write scan result to Redis cache", extra={"error": str(e)})


def get_cached_scan_result() -> dict | None:
    try:
        client = _get_client()
        raw = client.get(SCAN_CACHE_KEY)
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.info("Redis cache unavailable, will compute scan inline", extra={"error": str(e)})
        return None
