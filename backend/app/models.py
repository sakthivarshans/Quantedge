from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from app.core.time import utcnow
from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # Nullable because Google-authenticated users never set a password.
    hashed_password = Column(String, nullable=True)
    auth_provider = Column(String, nullable=False, default="password")  # "password" or "google"
    google_sub = Column(String, unique=True, index=True, nullable=True)  # Google's stable user id
    name = Column(String, nullable=True)
    picture_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    id = Column(Integer, primary_key=True, index=True)
    # Nullable: some events (e.g. a page view before signup) have no user yet.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    event_name = Column(String, nullable=False, index=True)
    event_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)


class PriceBar(Base):
    __tablename__ = "price_bars"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, nullable=False)
    date = Column(DateTime, index=True, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float, nullable=False)
    volume = Column(Float)


class BacktestResult(Base):
    __tablename__ = "backtest_results"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    task_id = Column(String, unique=True, index=True, nullable=True)
    status = Column(String, default="PENDING")  # PENDING / RUNNING / SUCCESS / FAILED
    ticker_a = Column(String, nullable=False)
    ticker_b = Column(String, nullable=False)
    params = Column(JSON)
    metrics = Column(JSON, nullable=True)
    equity_curve = Column(JSON, nullable=True)
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)


class ResearchSession(Base):
    __tablename__ = "research_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False, default="Untitled Session")
    cells = Column(JSON, default=list)  # list of {id, type, params, result, created_at}
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class PaperTrade(Base):
    __tablename__ = "paper_trades"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ticker_a = Column(String, nullable=False)
    ticker_b = Column(String, nullable=False)
    direction = Column(String)  # LONG_SPREAD / SHORT_SPREAD
    hedge_ratio = Column(Float, default=1.0)
    entry_z = Column(Float)
    exit_z = Column(Float, nullable=True)
    entry_price_a = Column(Float)
    entry_price_b = Column(Float)
    exit_price_a = Column(Float, nullable=True)
    exit_price_b = Column(Float, nullable=True)
    capital_allocated = Column(Float, default=10000.0)
    status = Column(String, default="OPEN")  # OPEN / CLOSED
    pnl = Column(Float, nullable=True)
    opened_at = Column(DateTime, default=utcnow)
    closed_at = Column(DateTime, nullable=True)
