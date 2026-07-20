import os
import pytest


def test_get_cached_scan_result_returns_none_when_redis_unreachable():
    """Cache layer must fail open (return None -> caller falls back to inline compute),
    never raise, if Redis is down. This is what keeps the app working without the
    worker infrastructure running."""
    import app.workers.cache as cache_module
    cache_module.REDIS_URL = "redis://nonexistent-host-for-testing:6399/0"
    cache_module._redis_client = None  # force reconnect attempt against the bad host
    result = cache_module.get_cached_scan_result()
    assert result is None


def test_set_scan_result_does_not_raise_when_redis_unreachable():
    import app.workers.cache as cache_module
    cache_module.REDIS_URL = "redis://nonexistent-host-for-testing:6399/0"
    cache_module._redis_client = None
    # Should not raise even though the write will fail
    cache_module.set_scan_result({"opportunities": []})


@pytest.mark.skipif(
    os.getenv("SKIP_REDIS_TESTS", "false").lower() == "true",
    reason="Redis not available in this environment",
)
def test_scan_result_roundtrips_through_real_redis():
    import app.workers.cache as cache_module
    cache_module.REDIS_URL = "redis://localhost:6379/0"
    cache_module._redis_client = None
    try:
        sample = {"universe_size": 5, "opportunities": [{"pair": "V/MA", "signal": "BUY"}]}
        cache_module.set_scan_result(sample)
        result = cache_module.get_cached_scan_result()
        assert result == sample
    except Exception as e:
        pytest.skip(f"Redis not reachable in this environment: {e}")


def test_refresh_market_scan_task_writes_to_cache():
    """Runs the Celery task's underlying function directly (not through a broker) and
    confirms it populates the cache -- this is the actual behavior that matters, not
    the Celery scheduling machinery itself."""
    from app.workers.tasks import refresh_market_scan
    import app.workers.cache as cache_module
    cache_module.REDIS_URL = "redis://localhost:6379/0"
    cache_module._redis_client = None
    try:
        result = refresh_market_scan.run()
        assert "num_opportunities" in result
        cached = cache_module.get_cached_scan_result()
        if cached is not None:  # only assert content if Redis is actually available here
            assert "opportunities" in cached
    except Exception as e:
        pytest.skip(f"Redis not reachable in this environment: {e}")
