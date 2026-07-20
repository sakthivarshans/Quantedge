# QuantEdge — Institutional Statistical Arbitrage Research Platform

A production-style web app for discovering, analyzing, backtesting, and monitoring
statistical arbitrage (pairs trading) opportunities, with real cointegration testing,
a vectorized backtester, a risk engine, and a portfolio optimizer.

## Architecture

```
quantedge/
├── backend/           FastAPI + SQLAlchemy + pandas/numpy/statsmodels
│   └── app/
│       ├── services/  Core quant engine (this is the heart of the app)
│       │   ├── data_service.py       market data ingestion (yfinance + synthetic fallback)
│       │   ├── pair_analysis.py      correlation, Engle-Granger cointegration, ADF, z-score
│       │   ├── backtest_service.py   vectorized mean-reversion backtester
│       │   ├── risk_service.py       VaR, CVaR, sector concentration
│       │   ├── optimizer_service.py  mean-variance & risk-parity allocation
│       │   ├── paper_trading_service.py
│       │   └── research_service.py   correlation matrix, pair diagnostics, beta exposure
│       ├── workers/    Celery + Redis background job layer
│       │   ├── celery_app.py         broker/schedule config
│       │   ├── tasks.py              refresh_market_scan (runs every 30s via Celery Beat)
│       │   └── cache.py              Redis cache read/write, fails open if Redis is down
│       ├── core/        auth (JWT), rate limiting, structured logging, DB session
│       ├── api/routes/  scanner, pairs, backtest, risk, auth, paper-trading, research, live (ws)
│       └── alembic/     versioned schema migrations
├── frontend/           React + TypeScript + Vite + Tailwind v4 + Recharts
│   └── src/pages/       Dashboard, Scanner, Pair Detail, Strategy Lab, Risk & Portfolio,
│                        Paper Trading, Research Notebook
└── docker-compose.yml   Postgres + Redis + backend + celery-worker + celery-beat + frontend
```

### Why these choices
- **Python/FastAPI backend**: the statistical core (cointegration tests, OLS hedge ratios,
  vectorized backtesting) needs `statsmodels`/`numpy`/`pandas` — trying to do this in
  Node would mean reimplementing econometrics from scratch.
- **Postgres in production, SQLite for local dev**: `DATABASE_URL` env var switches
  between them automatically — no code changes needed.
- **Synthetic data fallback**: `data_service.py` tries `yfinance` first, and falls back to
  a synthetic-but-genuinely-cointegrated generator if market data is unavailable (rate
  limits, no network, market closed). This means the app is always demoable.

## What's implemented

**Phase 1:**
- ✅ Market Scanner — cointegration + z-score scan across a configurable ticker universe
- ✅ Pair Detail page — price chart, spread, z-score, Engle-Granger + ADF test statistics
- ✅ Strategy Lab — configurable backtester (entry/exit/stop-loss z-thresholds), Sharpe/Sortino/drawdown
- ✅ Risk engine — VaR, CVaR, sector concentration warnings
- ✅ Portfolio optimizer — mean-variance and risk-parity capital allocation
- ✅ Dashboard — portfolio snapshot + top opportunities

**Phase 2:**
- ✅ Auth — JWT-based register/login, protected routes, `Authorization: Bearer` on the API
- ✅ Paper Trading engine — open/close simulated pairs positions, mark-to-market PnL against
  live spread/z-score, auto-flags positions worth closing (z reverted or stop-loss hit)
- ✅ Live Monitoring — WebSocket endpoint (`/ws/live-scanner`) streaming refreshed scanner
  signals every 15s; toggle "Go Live" on the Paper Trading page

**Phase 3:**
- ✅ Automated tests — 32 pytest tests covering the quant engine (cointegration, hedge
  ratio, half-life, signal logic), backtester, risk/optimizer math, and full API
  integration tests (auth flow, paper trading open/close, per-user data isolation)
- ✅ CI pipeline (`.github/workflows/ci.yml`) — lints + tests backend, lints + type-checks
  + builds frontend, builds both Docker images, on every push/PR
- ✅ Deploy pipeline (`.github/workflows/deploy.yml`) — builds & pushes versioned images
  to GHCR on git tags (`v*`); wire up your host's redeploy hook to complete it

**Phase 4:**
- ✅ Research Notebook — a cell-based analysis environment (not arbitrary code execution,
  which isn't safe to expose in a web app): correlation matrices, pair diagnostics, rolling
  volatility/return, and beta exposure cells, each backed by a real endpoint reusing the
  quant core. Sessions save/load per user.
- ✅ Frontend route-level code splitting — main JS bundle dropped from 664KB to a 284KB
  core chunk + per-route lazy chunks (was flagged by the Vite build warning in Phase 2/3)

**Phase 5 — Production Hardening:**
- ✅ Alembic migrations — schema is now version-controlled (`backend/alembic/versions/`)
  instead of `create_all()`; the initial migration captures all 5 tables
- ✅ Rate limiting — `/api/auth/login` (10/min), `/api/auth/register` (5/min), and
  `/api/scanner` (20/min) are limited per-IP via `slowapi`; verified end-to-end that the
  11th login attempt in a minute correctly returns `429`
- ✅ Structured JSON logging — every request logged with method/path/status/duration/IP;
  optional Sentry integration via `SENTRY_DSN` env var (no-op if unset)

**Phase 6 — Background Worker Architecture:**
- ✅ Celery + Redis — the pairwise cointegration scan (the most expensive computation in
  the app) now runs on a schedule via Celery Beat instead of inline on every request.
  Results are cached in Redis; the scanner API and the live WebSocket both read from that
  cache. Measured effect: scanner response time went from **1.4s (inline compute) to 3ms
  (cache hit)** — and that computation now happens once per interval no matter how many
  users are connected, instead of once per request.
- ✅ Graceful degradation — if Redis is unreachable, the API transparently falls back to
  computing the scan inline (the old behavior), so the app still works without the worker
  processes running; this is exercised directly in `tests/test_worker_cache.py`.

**Phase 7 — Async Backtest Jobs:**
- ✅ Background backtest execution — `POST /api/backtest/async` queues a backtest as a
  Celery job and returns a `job_id` immediately instead of blocking the request; poll
  `GET /api/backtest/jobs/{id}` for status (`PENDING` → `RUNNING` → `SUCCESS`/`FAILED`)
- ✅ Persisted backtest history — results are written to the `backtest_results` table
  (previously defined in the schema since Phase 1 but never actually used) via a new
  migration adding `user_id`, `task_id`, `status`, and `error` columns; `GET
  /api/backtest/history` lists a user's past runs
- ✅ Verified with a real (non-eager) Celery worker: submit → immediately `PENDING` →
  poll again after the worker picks it up → `SUCCESS` with real computed metrics
- ✅ Failure handling — a forced data-provider failure is caught, recorded as `FAILED`
  with the error message on the job row, and doesn't crash the worker (tested directly)
- Frontend: Strategy Lab now has a "Run in Background ⚙" button (shown once signed in)
  alongside the original synchronous "Run Backtest", plus a Backtest History table

### Named constraints & Alembic on SQLite
`Base`'s metadata now uses an explicit naming convention (`app/core/database.py`) --
SQLite's `ALTER TABLE` support is limited, so Alembic uses "batch mode" (rebuild-and-swap)
for migrations that add columns/constraints on SQLite, and batch mode requires every
constraint to have a name. This bit us once already (adding the `user_id` foreign key to
`backtest_results` in this phase) -- worth knowing if you add more relations to models
later.

**Phase 8 — Google Sign-In & Visual Redesign:**
- ✅ Google OAuth login — `POST /api/auth/google` verifies the ID token Google Identity
  Services returns to the frontend, then finds-or-creates a local user and issues our
  own JWT (the rest of the app never touches Google's token directly). Links to an
  existing password account automatically if the email already exists, rather than
  creating a duplicate. Fully optional: unset `GOOGLE_CLIENT_ID` / `VITE_GOOGLE_CLIENT_ID`
  and the button simply doesn't render -- nothing else changes.
- ✅ Migration adding `auth_provider`, `google_sub`, `name`, `picture_url` to `users`,
  and making `hashed_password` nullable (Google-only accounts never set one).
- ✅ Visual redesign — a reusable `GradientHero` component (dark navy base with glowing
  vertical blue light-columns) applied to the Login page as a full hero and to the
  Dashboard as a banner; verified visually with real Playwright screenshots during
  development, not just code review. Deliberately *not* applied to data-dense pages
  (Scanner, tables) since a glowing background behind a statistics table hurts
  legibility rather than helping it.
- ✅ Fixed a real bug caught while building this: `verify_password` would previously be
  called with `None` for Google-only accounts attempting a password login, which would
  raise instead of cleanly rejecting -- now guarded explicitly.

**Phase 9 — Real Market Data (Alpaca):**
- ✅ Alpaca Markets wired in as the primary real-data source, ahead of yfinance in the
  fallback chain: `Alpaca → yfinance → synthetic`, each tier only attempted if the one
  before it fails or isn't configured. Free tier, no credit card, real IEX exchange data.
- ✅ Chose Alpaca over alternatives based on current (2026) pricing, not assumption:
  Polygon.io dropped its free tier entirely ($99/mo minimum now), Alpha Vantage's free
  tier is throttled to 25 requests/day (too restrictive to scan 20+ tickers), IEX Cloud
  shut down. Alpaca was the one that held up.
- ✅ Tested with mocked Alpaca responses (`tests/test_data_service.py`) since this
  sandbox has no network route to Alpaca's API -- verifies response parsing (their
  MultiIndex symbol/timestamp DataFrame reshaped into our standard format), credential-
  missing fail-open behavior, and that the fallback chain actually prefers Alpaca over
  yfinance when both are available.
- ✅ Bug caught while writing those tests: the "too few tickers succeeded" safety check
  used `max(2, len(tickers) // 2)`, which rejected a *fully successful* single-ticker
  request (1 result < 2 required). Fixed to `max(1, len(tickers) // 2)` in both the
  Alpaca and yfinance fetch functions.
- Setup is entirely optional and needs your own free Alpaca account (`DEPLOYMENT.md`
  step 9) -- without `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` set, behavior is unchanged
  from before this phase.

**Phase 10 — UI Polish, Performance Fix, and Usage Analytics:**
- ✅ **Real performance bug found and fixed**: the Redis scanner cache (Phase 6) only
  activated when `top_n` exactly equaled a hardcoded `20`, but the frontend actually
  requests `top_n=30` (Scanner page) and `top_n=6` (Dashboard) -- neither ever matched,
  so the cache was silently never hit in practice. Every page load paid the full inline
  computation cost (~2.3-3.4s with the expanded 65-ticker universe). Fixed by caching a
  fixed larger result set and slicing to the requested `top_n` on read, decoupling
  cache-ability from the exact value requested. Verified: 2.3s → 3ms on the real request
  shapes the frontend actually uses.
- ✅ Toast notification system, page-transition animations, hover-prefetch on nav links,
  React Query caching on the main data-fetching pages, expanded ticker universe (20 →
  65 names across more sectors), Postgres connection pool tuning
  (`pool_pre_ping`/`pool_size`/`max_overflow`) for concurrent traffic.
- ✅ **Self-introduced bug caught by testing, not luck**: wiring up hover-prefetch
  created a circular import (`App.tsx` ↔ `Layout.tsx`) that made the entire app render
  blank with zero visible error. Fixed by extracting the shared route-import map into
  its own module; verified the fix with a real browser (Playwright), confirming zero
  console errors and real page content, not just a successful build.
- ✅ Usage analytics -- a lightweight `analytics_events` table (not Firestore; see
  below) logging `signup`/`login`/`login_google`/`trade_opened`/`trade_closed`/
  `backtest_run` server-side (more reliable than trusting fire-and-forget frontend
  calls), plus `POST /api/events` for ad hoc frontend events like `page_view`. `GET
  /api/analytics/summary` gives event counts and daily signups. Verified end-to-end
  against a live server: real signup → login → trade open/close → backtest all
  produced correct counts in the summary.
- Firestore was considered and deliberately not used for the user/auth database: the
  schema is relational by design (`paper_trades`, `backtest_results`, and
  `research_sessions` all foreign-key into `users.id` with real integrity constraints
  tested directly), and Firestore's document model doesn't fit that without giving up
  joins, Alembic migrations, and the referential-integrity tests already in place. The
  `analytics_events` table above is the "flexible schema" use case Firestore is
  actually good at, built instead as one more table in the same Postgres database rather
  than standing up a second database with a different consistency/backup model.

## Running the background workers

```bash
# Terminal 1: Redis (or use Docker: docker run -p 6379:6379 redis:7-alpine)
redis-server

# Terminal 2: Celery worker (executes the scan AND any submitted backtest jobs --
# one worker handles both task types)
cd backend
USE_SYNTHETIC_DATA=true celery -A app.workers.celery_app worker --loglevel=info

# Terminal 3: Celery beat (schedules the scan every SCAN_INTERVAL_SECONDS, default 30s)
cd backend
USE_SYNTHETIC_DATA=true celery -A app.workers.celery_app beat --loglevel=info

# Terminal 4: the API itself, as usual
cd backend
USE_SYNTHETIC_DATA=true uvicorn app.main:app --reload --port 8000
```
With Docker Compose, all four processes (`backend`, `celery-worker`, `celery-beat`,
`redis`) start automatically with `docker compose up --build`.

You don't need the workers running for local dev — the app works without them (just
slower on scanner requests, computing inline every time).

## Running tests locally

```bash
cd backend
pip install -r requirements-dev.txt
USE_SYNTHETIC_DATA=true DISABLE_RATE_LIMIT=true CELERY_TASK_ALWAYS_EAGER=true pytest tests/ -v   # 73 tests
ruff check app/ tests/ alembic/                                     # lint
```
```bash
cd frontend
npm run lint
npm run build   # also type-checks via tsc -b
```

## Database migrations (Alembic)

Schema changes now go through Alembic instead of relying on SQLAlchemy's `create_all()`:

```bash
cd backend
# Apply all pending migrations (run this before starting the app, or let the
# Docker container do it automatically via its CMD)
alembic upgrade head

# After changing a model in app/models.py, generate a new migration:
alembic revision --autogenerate -m "add some_column to some_table"
# Review the generated file in alembic/versions/ before committing --
# autogenerate is a good first draft, not infallible.
```
The Docker image runs `alembic upgrade head` automatically on container start (see
`backend/Dockerfile`), so `docker compose up` handles this for you.

## Rate limiting & observability env vars

| Variable | Default | Purpose |
|---|---|---|
| `DISABLE_RATE_LIMIT` | `false` | Set `true` only for local load-testing; the test suite sets this automatically |
| `LOG_LEVEL` | `INFO` | Root log level |
| `SENTRY_DSN` | unset | Set to enable Sentry error monitoring; no-op if unset |
| `ENVIRONMENT` | `development` | Tagged on Sentry events |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.1` | Sentry performance trace sampling |

## Not yet built
Everything in the original spec's core workflow, a full hardening pass, real (free)
market data, and the main scaling bottleneck (the scanner) are now handled. What's left
is genuine infrastructure scale-out, not correctness or performance gaps in the app itself:
- Tick-level/streaming real-time data (Alpaca's free tier gives real daily bars and
  current quotes, not a live tick stream — that needs a paid vendor plan)
- Multi-region / CDN for the frontend
- Celery worker autoscaling / multiple queues if job volume grows enough that the
  scanner refresh and backtest jobs (both already queued as of Phase 7) start
  contending for the same worker pool

## Local development (without Docker)

**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# USE_SYNTHETIC_DATA=true skips live data fetching entirely — fastest for local dev
USE_SYNTHETIC_DATA=true uvicorn app.main:app --reload --port 8000
```
API docs available at `http://localhost:8000/docs`.

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```
Visit `http://localhost:5173`. The Vite dev server proxies `/api/*` to `localhost:8000`
(see `vite.config.ts`).

## Running everything with Docker Compose

```bash
docker compose up --build
```
This starts Postgres, the FastAPI backend (port 8000), and the frontend served via
nginx (port 80). Visit `http://localhost`.

By default `USE_SYNTHETIC_DATA` is `false` in `docker-compose.yml`, so it will attempt
real market data via `yfinance`. Set it to `"true"` if you don't want a live data
dependency.

## Deploying to the cloud

**For a detailed, click-by-click Railway walkthrough (recommended for a portfolio
deploy), see [`DEPLOYMENT.md`](./DEPLOYMENT.md).** It covers the multi-service setup
(backend, frontend, celery-worker, celery-beat, Postgres, Redis) as five separate
Railway services from one repo, including two gotchas specific to that topology: the
frontend's Docker nginx config assumes same-origin with the backend (fine for Docker
Compose, wrong for separate Railway domains), and `VITE_API_URL` must be set before the
frontend builds since Vite bakes env vars in at build time.

The summary below covers the general shape for any host.


### Option A: Railway / Render (simplest)
1. Push this repo to GitHub.
2. Create a **Postgres** service (Railway/Render both offer managed Postgres) — copy its
   connection string.
3. Create a **backend** service pointing at `/backend`, using its Dockerfile. Set env var
   `DATABASE_URL` to the Postgres connection string.
4. Create a **frontend** service pointing at `/frontend`. Set build-time env var
   `VITE_API_URL` to your backend's public URL + `/api` (e.g.
   `https://quantedge-backend.up.railway.app/api`), since the frontend and backend will
   be on different domains rather than sharing nginx.
5. On the backend, set env var `CORS_ORIGINS` to your frontend's origin (comma-separated
   for multiple), e.g. `https://quantedge.yourdomain.com` — the default `*` is fine for
   local dev but should be tightened in production. Also set `JWT_SECRET_KEY` to a long
   random string (the default is dev-only and insecure).
6. Migrations run automatically — the backend's Dockerfile `CMD` runs
   `alembic upgrade head` before starting the server, so no manual migration step is
   needed on first deploy or on any deploy after a schema change.

### Option B: AWS (more "production-grade" for a resume)
- Push backend & frontend images to **ECR**.
- Run them on **ECS Fargate** (2 services) behind an **ALB**.
- **RDS Postgres** for the database.
- **Route 53** + **ACM** for a custom domain with HTTPS.
- This is the setup worth highlighting if you want the DevOps/cloud story for recruiters.

## Real market data (Alpaca) & extending the scanner universe

`fetch_price_history` (`backend/app/services/data_service.py`) is a three-tier fallback
chain, each tier only attempted if the previous one is unavailable or fails:

1. **Alpaca Markets** — used automatically if `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` are
   set. Free (no credit card), real IEX exchange data, no daily call-count limit that
   would break a 20-ticker scan. This is the recommended path for real data; see
   `DEPLOYMENT.md` step 9 for the signup walkthrough (~5 minutes).
2. **yfinance** — unofficial, free, no signup, tried automatically if Alpaca isn't
   configured. Breaks unpredictably and gets rate-limited by Yahoo, especially from
   cloud provider IPs — fine for occasional local use, not something to depend on.
3. **Synthetic** — forced by `USE_SYNTHETIC_DATA=true`, or used automatically as the
   last resort if both real sources fail. Genuinely cointegrated (not random noise),
   so the statistics are meaningful even though the prices aren't real.

Why Alpaca over other providers: Polygon.io dropped its free tier entirely (starts at
$99/mo as of 2026); Alpha Vantage's free tier is throttled to 25 requests/day, too
restrictive for scanning 20+ tickers; IEX Cloud shut down. Alpaca's free tier is the
most usable option that doesn't compromise on being genuinely free.

`DEFAULT_UNIVERSE` in the same file controls which tickers get scanned — expand it to
cover more names. The rest of the pipeline (cointegration, signals, backtesting) doesn't
need to change regardless of which tier is actually serving the data.
