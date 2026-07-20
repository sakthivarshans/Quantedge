import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    # Use an isolated test DB so this suite doesn't collide with dev data
    db_path = "./test_api_quantedge.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    from app.core.database import Base, engine
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    from app.main import app
    with TestClient(app) as c:
        yield c
    if os.path.exists(db_path):
        os.remove(db_path)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_scanner_returns_opportunities(client):
    resp = client.get("/api/scanner?top_n=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "opportunities" in data
    assert data["universe_size"] > 0


def test_pair_detail(client):
    resp = client.get("/api/pairs/V/MA")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker_a"] == "V"
    assert data["ticker_b"] == "MA"
    assert "cointegration" in data


def test_backtest_endpoint(client):
    resp = client.post("/api/backtest", json={"ticker_a": "V", "ticker_b": "MA", "days": 500})
    assert resp.status_code == 200
    data = resp.json()
    assert "metrics" in data
    assert data["metrics"]["num_trades"] >= 0


def test_register_and_login_flow(client):
    resp = client.post("/api/auth/register", json={"email": "pytest@quantedge.dev", "password": "testpass123"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # duplicate registration should fail
    dup = client.post("/api/auth/register", json={"email": "pytest@quantedge.dev", "password": "testpass123"})
    assert dup.status_code == 400

    # login with correct credentials
    login = client.post("/api/auth/login", json={"email": "pytest@quantedge.dev", "password": "testpass123"})
    assert login.status_code == 200

    # login with wrong password
    bad_login = client.post("/api/auth/login", json={"email": "pytest@quantedge.dev", "password": "wrongpass"})
    assert bad_login.status_code == 401

    # /me requires a valid token
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "pytest@quantedge.dev"


def test_paper_trading_requires_auth(client):
    resp = client.get("/api/paper-trading/portfolio")
    assert resp.status_code == 401


def test_paper_trading_open_close_flow(client):
    register = client.post("/api/auth/register", json={"email": "trader2@quantedge.dev", "password": "testpass123"})
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    open_resp = client.post(
        "/api/paper-trading/open",
        json={"ticker_a": "AAPL", "ticker_b": "MSFT", "capital_allocated": 5000},
        headers=headers,
    )
    assert open_resp.status_code == 200
    trade_id = open_resp.json()["id"]

    portfolio = client.get("/api/paper-trading/portfolio", headers=headers)
    assert portfolio.status_code == 200
    assert len(portfolio.json()["open_positions"]) == 1

    close_resp = client.post(f"/api/paper-trading/close/{trade_id}", headers=headers)
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "CLOSED"

    # closing again should fail
    close_again = client.post(f"/api/paper-trading/close/{trade_id}", headers=headers)
    assert close_again.status_code == 400

    portfolio_after = client.get("/api/paper-trading/portfolio", headers=headers)
    assert len(portfolio_after.json()["open_positions"]) == 0
    assert len(portfolio_after.json()["closed_positions"]) == 1


def test_paper_trading_is_scoped_per_user(client):
    """User A's trades should not be visible to User B."""
    reg_a = client.post("/api/auth/register", json={"email": "usera@quantedge.dev", "password": "testpass123"})
    reg_b = client.post("/api/auth/register", json={"email": "userb@quantedge.dev", "password": "testpass123"})
    headers_a = {"Authorization": f"Bearer {reg_a.json()['access_token']}"}
    headers_b = {"Authorization": f"Bearer {reg_b.json()['access_token']}"}

    client.post("/api/paper-trading/open", json={"ticker_a": "XOM", "ticker_b": "CVX"}, headers=headers_a)

    portfolio_a = client.get("/api/paper-trading/portfolio", headers=headers_a).json()
    portfolio_b = client.get("/api/paper-trading/portfolio", headers=headers_b).json()

    assert len(portfolio_a["open_positions"]) == 1
    assert len(portfolio_b["open_positions"]) == 0


def test_risk_and_optimizer_endpoints(client):
    risk_resp = client.post("/api/risk", json={"positions": [
        {"ticker": "AAPL", "market_value": 10000},
        {"ticker": "MSFT", "market_value": 10000},
    ]})
    assert risk_resp.status_code == 200
    assert "value_at_risk_95_pct" in risk_resp.json()

    opt_resp = client.post("/api/optimizer", json={
        "opportunities": [
            {"pair": "V/MA", "expected_return": 0.02, "volatility": 0.04},
            {"pair": "AAPL/MSFT", "expected_return": 0.015, "volatility": 0.03},
        ],
        "capital": 50000,
        "method": "risk_parity",
    })
    assert opt_resp.status_code == 200
    assert len(opt_resp.json()["allocations"]) == 2


def test_research_notebook_requires_auth(client):
    resp = client.get("/api/research/sessions")
    assert resp.status_code == 401


def test_research_run_cell(client):
    register = client.post("/api/auth/register", json={"email": "researcher@quantedge.dev", "password": "testpass123"})
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    resp = client.post("/api/research/run-cell", json={
        "cell_type": "correlation_matrix",
        "params": {"tickers": ["AAPL", "MSFT", "V"], "days": 300},
    }, headers=headers)
    assert resp.status_code == 200
    assert "matrix" in resp.json()["result"]

    bad = client.post("/api/research/run-cell", json={"cell_type": "nonsense", "params": {}}, headers=headers)
    assert bad.status_code == 400


def test_research_session_crud(client):
    register = client.post("/api/auth/register", json={"email": "researcher2@quantedge.dev", "password": "testpass123"})
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    create = client.post("/api/research/sessions", json={
        "name": "My Session",
        "cells": [{"id": "c1", "type": "correlation_matrix", "params": {"tickers": ["AAPL", "MSFT"]}}],
    }, headers=headers)
    assert create.status_code == 200
    session_id = create.json()["id"]

    listed = client.get("/api/research/sessions", headers=headers)
    assert len(listed.json()) == 1

    fetched = client.get(f"/api/research/sessions/{session_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "My Session"

    updated = client.put(f"/api/research/sessions/{session_id}", json={
        "name": "Renamed Session", "cells": [],
    }, headers=headers)
    assert updated.status_code == 200

    deleted = client.delete(f"/api/research/sessions/{session_id}", headers=headers)
    assert deleted.status_code == 200

    after_delete = client.get(f"/api/research/sessions/{session_id}", headers=headers)
    assert after_delete.status_code == 404


def test_research_sessions_scoped_per_user(client):
    reg_a = client.post("/api/auth/register", json={"email": "researchA@quantedge.dev", "password": "testpass123"})
    reg_b = client.post("/api/auth/register", json={"email": "researchB@quantedge.dev", "password": "testpass123"})
    headers_a = {"Authorization": f"Bearer {reg_a.json()['access_token']}"}
    headers_b = {"Authorization": f"Bearer {reg_b.json()['access_token']}"}

    client.post("/api/research/sessions", json={"name": "A's session", "cells": []}, headers=headers_a)

    sessions_a = client.get("/api/research/sessions", headers=headers_a).json()
    sessions_b = client.get("/api/research/sessions", headers=headers_b).json()
    assert len(sessions_a) == 1
    assert len(sessions_b) == 0


def test_analytics_summary_requires_auth(client):
    resp = client.get("/api/analytics/summary")
    assert resp.status_code == 401


def test_signup_and_login_are_logged_as_events(client):
    register = client.post("/api/auth/register", json={"email": "analyticsuser@quantedge.dev", "password": "testpass123"})
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/auth/login", json={"email": "analyticsuser@quantedge.dev", "password": "testpass123"})

    summary = client.get("/api/analytics/summary", headers=headers).json()
    assert summary["event_counts"].get("signup", 0) >= 1
    assert summary["event_counts"].get("login", 0) >= 1


def test_paper_trade_open_and_close_are_logged_as_events(client):
    register = client.post("/api/auth/register", json={"email": "analyticstrader@quantedge.dev", "password": "testpass123"})
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    open_resp = client.post("/api/paper-trading/open", json={"ticker_a": "V", "ticker_b": "MA"}, headers=headers)
    trade_id = open_resp.json()["id"]
    client.post(f"/api/paper-trading/close/{trade_id}", headers=headers)

    summary = client.get("/api/analytics/summary", headers=headers).json()
    assert summary["event_counts"].get("trade_opened", 0) >= 1
    assert summary["event_counts"].get("trade_closed", 0) >= 1


def test_backtest_run_is_logged_as_event(client):
    register = client.post("/api/auth/register", json={"email": "analyticsbacktester@quantedge.dev", "password": "testpass123"})
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    client.post("/api/backtest", json={"ticker_a": "V", "ticker_b": "MA", "days": 500})

    summary = client.get("/api/analytics/summary", headers=headers).json()
    assert summary["event_counts"].get("backtest_run", 0) >= 1


def test_log_event_endpoint_works_without_auth(client):
    """page_view (and similar pre-login events) should be loggable anonymously."""
    resp = client.post("/api/events", json={"event_name": "page_view", "metadata": {"path": "/scanner"}})
    assert resp.status_code == 200
    assert resp.json()["logged"] is True


def test_log_event_endpoint_rejects_unknown_event_name(client):
    resp = client.post("/api/events", json={"event_name": "totally_made_up_event"})
    assert resp.status_code == 400


def test_async_backtest_job_completes_and_is_queryable(client):
    """With CELERY_TASK_ALWAYS_EAGER=true (set for the whole test suite), .delay()
    runs the task synchronously in-process, so by the time submit_backtest_job returns,
    the job should already be SUCCESS -- this test exercises the full job lifecycle
    without needing a live Celery worker."""
    register = client.post("/api/auth/register", json={"email": "backtester@quantedge.dev", "password": "testpass123"})
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    submit = client.post("/api/backtest/async", json={
        "ticker_a": "V", "ticker_b": "MA", "days": 500,
    }, headers=headers)
    assert submit.status_code == 200
    job_id = submit.json()["job_id"]
    assert submit.json()["task_id"] is not None

    status = client.get(f"/api/backtest/jobs/{job_id}", headers=headers)
    assert status.status_code == 200
    data = status.json()
    assert data["status"] == "SUCCESS"
    assert "sharpe_ratio" in data["metrics"]
    assert data["equity_curve"] is not None
    assert data["completed_at"] is not None


def test_backtest_job_requires_auth_and_is_scoped(client):
    resp = client.get("/api/backtest/jobs/1")
    assert resp.status_code == 401

    reg_a = client.post("/api/auth/register", json={"email": "backtesterA@quantedge.dev", "password": "testpass123"})
    reg_b = client.post("/api/auth/register", json={"email": "backtesterB@quantedge.dev", "password": "testpass123"})
    headers_a = {"Authorization": f"Bearer {reg_a.json()['access_token']}"}
    headers_b = {"Authorization": f"Bearer {reg_b.json()['access_token']}"}

    submit = client.post("/api/backtest/async", json={"ticker_a": "AAPL", "ticker_b": "MSFT"}, headers=headers_a)
    job_id = submit.json()["job_id"]

    # user B should not be able to see user A's job
    forbidden = client.get(f"/api/backtest/jobs/{job_id}", headers=headers_b)
    assert forbidden.status_code == 404

    allowed = client.get(f"/api/backtest/jobs/{job_id}", headers=headers_a)
    assert allowed.status_code == 200


def test_backtest_history_lists_past_jobs(client):
    register = client.post("/api/auth/register", json={"email": "historian@quantedge.dev", "password": "testpass123"})
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    client.post("/api/backtest/async", json={"ticker_a": "V", "ticker_b": "MA"}, headers=headers)
    client.post("/api/backtest/async", json={"ticker_a": "AAPL", "ticker_b": "MSFT"}, headers=headers)

    history = client.get("/api/backtest/history", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 2
    assert all(h["status"] == "SUCCESS" for h in history.json())


def test_backtest_job_failure_is_recorded(client, monkeypatch):
    """A failure during computation should be recorded on the job, not crash the
    worker or leave the job stuck in PENDING/RUNNING forever."""
    register = client.post("/api/auth/register", json={"email": "faildemo@quantedge.dev", "password": "testpass123"})
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated data provider outage")

    monkeypatch.setattr("app.services.data_service.fetch_price_history", _boom)

    submit = client.post("/api/backtest/async", json={
        "ticker_a": "V", "ticker_b": "MA",
    }, headers=headers)
    job_id = submit.json()["job_id"]

    status = client.get(f"/api/backtest/jobs/{job_id}", headers=headers)
    assert status.json()["status"] == "FAILED"
    assert "simulated data provider outage" in status.json()["error"]


def test_google_login_returns_501_when_not_configured(client, monkeypatch):
    """Without GOOGLE_CLIENT_ID set, the endpoint should fail clearly rather than
    trying (and failing confusingly) to verify against an empty client id."""
    monkeypatch.setattr("app.api.routes.auth.GOOGLE_CLIENT_ID", None)
    resp = client.post("/api/auth/google", json={"id_token": "fake-token"})
    assert resp.status_code == 501


def test_google_login_creates_new_user(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.auth.GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")

    def fake_verify(token, request, client_id):
        assert client_id == "test-client-id.apps.googleusercontent.com"
        return {
            "sub": "google-uid-12345", "email": "newgoogleuser@gmail.com",
            "email_verified": True, "name": "New Google User", "picture": "https://example.com/pic.jpg",
        }

    monkeypatch.setattr("app.api.routes.auth.google_id_token.verify_oauth2_token", fake_verify)

    resp = client.post("/api/auth/google", json={"id_token": "fake-valid-token"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "newgoogleuser@gmail.com"
    assert data["name"] == "New Google User"
    assert data["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me.status_code == 200
    assert me.json()["auth_provider"] == "google"
    assert me.json()["picture_url"] == "https://example.com/pic.jpg"


def test_google_login_rejects_unverified_email(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.auth.GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")

    def fake_verify(token, request, client_id):
        return {"sub": "google-uid-999", "email": "unverified@gmail.com", "email_verified": False}

    monkeypatch.setattr("app.api.routes.auth.google_id_token.verify_oauth2_token", fake_verify)

    resp = client.post("/api/auth/google", json={"id_token": "fake-token"})
    assert resp.status_code == 401


def test_google_login_rejects_invalid_token(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.auth.GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")

    def fake_verify(token, request, client_id):
        raise ValueError("Token used too early")

    monkeypatch.setattr("app.api.routes.auth.google_id_token.verify_oauth2_token", fake_verify)

    resp = client.post("/api/auth/google", json={"id_token": "garbage"})
    assert resp.status_code == 401


def test_google_login_links_existing_password_account(client, monkeypatch):
    """If someone already registered with email+password and later uses Google Sign-In
    with the same email, it should link to the existing account rather than erroring
    on a duplicate email or creating a second, disconnected account."""
    client.post("/api/auth/register", json={"email": "linktest@quantedge.dev", "password": "testpass123"})

    monkeypatch.setattr("app.api.routes.auth.GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")

    def fake_verify(token, request, client_id):
        return {
            "sub": "google-uid-link-test", "email": "linktest@quantedge.dev",
            "email_verified": True, "name": "Link Test", "picture": None,
        }

    monkeypatch.setattr("app.api.routes.auth.google_id_token.verify_oauth2_token", fake_verify)

    resp = client.post("/api/auth/google", json={"id_token": "fake-token"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "linktest@quantedge.dev"

    # the original password login should still work too
    login = client.post("/api/auth/login", json={"email": "linktest@quantedge.dev", "password": "testpass123"})
    assert login.status_code == 200
