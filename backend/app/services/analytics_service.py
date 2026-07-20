from datetime import timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models import AnalyticsEvent, User
from app.core.time import utcnow

# Keep this to a fixed, known set rather than accepting arbitrary strings from the
# client -- an open-ended event_name would let a bug (or a malicious client) pollute
# the table with junk that breaks the summary aggregation below.
ALLOWED_EVENTS = {
    "page_view", "signup", "login", "login_google",
    "trade_opened", "trade_closed", "backtest_run", "backtest_run_async",
}


def log_event(db: Session, event_name: str, user_id: int | None = None, metadata: dict | None = None) -> None:
    if event_name not in ALLOWED_EVENTS:
        raise ValueError(f"Unknown event_name: {event_name}. Allowed: {sorted(ALLOWED_EVENTS)}")
    event = AnalyticsEvent(user_id=user_id, event_name=event_name, event_metadata=metadata)
    db.add(event)
    db.commit()


def get_summary(db: Session, days: int = 30) -> dict:
    """
    Deliberately simple aggregates -- counts per event type, daily signups, and
    total distinct users who logged any event -- not a full analytics platform.
    For anything beyond "how many people are actually using this," a dedicated tool
    (PostHog, Plausible, etc.) is the right call rather than growing this endpoint.
    """
    since = utcnow() - timedelta(days=days)

    counts_by_event = dict(
        db.query(AnalyticsEvent.event_name, func.count(AnalyticsEvent.id))
        .filter(AnalyticsEvent.created_at >= since)
        .group_by(AnalyticsEvent.event_name)
        .all()
    )

    total_users = db.query(func.count(User.id)).scalar()

    signups_by_day = (
        db.query(func.date(AnalyticsEvent.created_at), func.count(AnalyticsEvent.id))
        .filter(AnalyticsEvent.event_name == "signup", AnalyticsEvent.created_at >= since)
        .group_by(func.date(AnalyticsEvent.created_at))
        .order_by(func.date(AnalyticsEvent.created_at))
        .all()
    )

    return {
        "window_days": days,
        "total_registered_users": total_users,
        "event_counts": counts_by_event,
        "signups_by_day": [{"date": str(d), "count": c} for d, c in signups_by_day],
    }
