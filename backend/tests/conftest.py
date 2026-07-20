import os
os.environ["USE_SYNTHETIC_DATA"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///./test_quantedge.db"
os.environ["DISABLE_RATE_LIMIT"] = "true"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"

import pytest
from app.services.data_service import generate_synthetic_universe, DEFAULT_UNIVERSE


@pytest.fixture(scope="session")
def synthetic_frames():
    return generate_synthetic_universe(DEFAULT_UNIVERSE, days=500)


@pytest.fixture(scope="session")
def cointegrated_pair(synthetic_frames):
    """V and MA are seeded as a genuinely cointegrated pair in the synthetic generator."""
    pa = synthetic_frames["V"].set_index("date")["close"]
    pb = synthetic_frames["MA"].set_index("date")["close"]
    return pa, pb


@pytest.fixture(scope="session")
def unrelated_pair(synthetic_frames):
    """AMD and KO have no engineered relationship -- should generally fail cointegration."""
    pa = synthetic_frames["AMD"].set_index("date")["close"]
    pb = synthetic_frames["KO"].set_index("date")["close"]
    return pa, pb
