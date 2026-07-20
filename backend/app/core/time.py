from datetime import datetime, timezone


def utcnow() -> datetime:
    """
    Timezone-aware replacement for the deprecated datetime.utcnow(). Used everywhere
    the app needs "now" for DB timestamps or JWT expiry, so every part of the app
    produces consistent aware datetimes rather than a mix of naive and aware values
    that could compare incorrectly.
    """
    return datetime.now(timezone.utc)
