import os
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, declarative_base

# Default to local SQLite for dev; set DATABASE_URL env var to a Postgres DSN in production
# e.g. postgresql://user:password@host:5432/quantedge
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quantedge.db")

if DATABASE_URL.startswith("sqlite"):
    # SQLite doesn't have a real connection pool in the Postgres sense; check_same_thread
    # must be disabled since FastAPI can service one request's DB session from a
    # different thread than it was created on.
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Tuned for concurrent traffic: pool_pre_ping avoids handing out stale/dropped
    # connections (a real failure mode once a DB has been idle or restarted under load),
    # and pool_size/max_overflow are sized generously enough for many app instances
    # each holding a modest pool without exhausting Postgres's own max_connections.
    # Override via env vars if you tune this against your actual Postgres plan's limits.
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
        pool_recycle=1800,  # recycle connections every 30 min to avoid server-side timeouts
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Named constraints are required for SQLite's batch-mode ALTER TABLE (used by Alembic
# migrations that add/modify foreign keys) -- unnamed constraints can't be dropped/recreated.
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
Base = declarative_base(metadata=MetaData(naming_convention=naming_convention))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
