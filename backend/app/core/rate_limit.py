import os
from slowapi import Limiter
from slowapi.util import get_remote_address

# Per-client-IP rate limiting. In production behind a load balancer, ensure
# X-Forwarded-For is trusted/parsed correctly (see deployment notes in README)
# so this keys off the real client IP rather than the proxy's.
#
# Disabled entirely when DISABLE_RATE_LIMIT=true -- used by the test suite, since
# many tests share one client/IP in a tight loop and would otherwise trip the limits
# meant to catch real abuse.
limiter = Limiter(
    key_func=get_remote_address,
    enabled=os.getenv("DISABLE_RATE_LIMIT", "false").lower() != "true",
)
