import os
import pytest
from app.services.analytics_service import log_event, get_summary, ALLOWED_EVENTS


@pytest.fixture(scope="module")
def db_session():
    db_path = "./test_analytics_quantedge.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    from app.core.database import Base, engine, SessionLocal
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    if os.path.exists(db_path):
        os.remove(db_path)


def test_log_event_rejects_unknown_event_name(db_session):
    with pytest.raises(ValueError):
        log_event(db_session, "not_a_real_event")


def test_all_allowed_events_can_be_logged(db_session):
    for event_name in ALLOWED_EVENTS:
        log_event(db_session, event_name)  # should not raise


def test_get_summary_counts_events_within_window(db_session):
    log_event(db_session, "signup")
    log_event(db_session, "signup")
    log_event(db_session, "login")
    summary = get_summary(db_session, days=30)
    assert summary["event_counts"].get("signup", 0) >= 2
    assert summary["event_counts"].get("login", 0) >= 1
    assert "signups_by_day" in summary
    assert "total_registered_users" in summary


def test_log_event_attaches_metadata_and_user_id(db_session):
    from app.models import User, AnalyticsEvent
    user = User(email="analyticstest@quantedge.dev", hashed_password="fake", auth_provider="password")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    log_event(db_session, "trade_opened", user_id=user.id, metadata={"pair": "V/MA"})

    event = (
        db_session.query(AnalyticsEvent)
        .filter(AnalyticsEvent.event_name == "trade_opened", AnalyticsEvent.user_id == user.id)
        .first()
    )
    assert event is not None
    assert event.event_metadata == {"pair": "V/MA"}
