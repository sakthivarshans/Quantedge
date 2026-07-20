# Deploying QuantEdge to Railway (portfolio deploy)

This is the exact click-by-click path for getting this live on a public URL. Total
time: ~15-20 minutes. Railway is the pick here because it does managed Postgres +
Redis + multiple services from one repo with the least amount of yak-shaving.

**Recommendation for a portfolio deploy specifically:** set `USE_SYNTHETIC_DATA=true`.
Real `yfinance` gets rate-limited or blocked from cloud provider IPs surprisingly often
(Yahoo doesn't like datacenter traffic), and a recruiter opening your Scanner page to a
500 error is worse than honest, clearly-labeled synthetic data. The synthetic generator
produces genuinely cointegrated pairs and realistic statistics -- it's not fake-looking,
it's just not live Yahoo Finance data. You can flip this to `false` later once you've
got a real data vendor key (see README's "Extending the scanner universe" section).

---

## 0. Push to GitHub

```bash
cd quantedge
git init
git add .
git commit -m "Initial commit"
```
Create a new repo on GitHub, then:
```bash
git remote add origin https://github.com/<you>/quantedge.git
git branch -M main
git push -u origin main
```

## 1. Create the Railway project

1. Go to https://railway.app, sign in with GitHub.
2. **New Project** → **Deploy from GitHub repo** → pick `quantedge`.
3. Railway will try to auto-detect a service from the repo root. **Delete that
   auto-created service** -- we're going to add 5 services manually, each pointed at a
   subdirectory, since this repo has multiple deployables in one place.

## 2. Add Postgres

1. In the project canvas: **New** → **Database** → **Add PostgreSQL**.
2. That's it -- Railway provisions it and exposes a `DATABASE_URL`-shaped set of
   variables you'll reference from the backend service in a moment.

## 3. Add Redis

1. **New** → **Database** → **Add Redis**.
2. Same deal -- Railway exposes connection variables you'll reference next.

## 4. Deploy the backend

1. **New** → **GitHub Repo** → same `quantedge` repo again.
2. In the new service's **Settings**:
   - **Root Directory**: `backend`
   - Railway will detect the `Dockerfile` automatically and build from it.
3. In **Variables**, add:
   ```
   DATABASE_URL       = ${{Postgres.DATABASE_URL}}
   REDIS_URL          = ${{Redis.REDIS_URL}}
   USE_SYNTHETIC_DATA = true
   JWT_SECRET_KEY     = <generate one: python3 -c "import secrets; print(secrets.token_urlsafe(48))">
   ENVIRONMENT        = production
   LOG_LEVEL          = INFO
   CORS_ORIGINS       = *
   ```
   (The `${{Postgres.DATABASE_URL}}` / `${{Redis.REDIS_URL}}` syntax is Railway's
   variable-reference syntax -- it autocompletes when you type `${{` in the Variables
   panel, and automatically points at the services you added in steps 2-3.)
4. In **Settings → Networking**, click **Generate Domain** to get a public URL, e.g.
   `quantedge-backend-production.up.railway.app`.
5. Deploy. Watch the build logs -- the Dockerfile's `CMD` runs `alembic upgrade head`
   automatically before starting uvicorn, so the schema gets created on first deploy
   with no manual step.
6. Sanity check: visit `https://<your-backend-domain>/api/health` -- should return
   `{"status":"ok"}`. Then `/docs` for the interactive API explorer.

## 5. Deploy the Celery worker

1. **New** → **GitHub Repo** → same repo again.
2. **Root Directory**: `backend` (same as backend service)
3. **Settings → Deploy → Custom Start Command**:
   ```
   celery -A app.workers.celery_app worker --loglevel=info
   ```
   (This overrides the Dockerfile's default CMD, so it won't re-run migrations --
   that's fine, the backend service already handled that.)
4. **Variables** -- same as the backend service: `DATABASE_URL`, `REDIS_URL`,
   `USE_SYNTHETIC_DATA=true`, `LOG_LEVEL=INFO`. No public domain needed for this one.

## 6. Deploy Celery beat

1. Repeat step 5 exactly, but the start command is:
   ```
   celery -A app.workers.celery_app beat --loglevel=info
   ```
2. Same variables, plus optionally `SCAN_INTERVAL_SECONDS=30`.

## 7. Deploy the frontend

1. **New** → **GitHub Repo** → same repo again.
2. **Root Directory**: `frontend`
3. Railway will detect the `Dockerfile` here too (the nginx multi-stage build) --
   **don't use it for this deployment topology**. That Dockerfile's nginx.conf proxies
   `/api` and `/ws` to a service literally named `backend` on the same Docker network,
   which only exists in the `docker-compose.yml` setup, not here where each service has
   its own Railway domain. Instead, in **Settings → Build**, switch the builder from
   "Dockerfile" to **Nixpacks** (Railway's default Node builder). It'll run
   `npm install && npm run build` automatically, and the `start` script already in
   `package.json` (`serve -s dist -l $PORT`) handles serving the built app.
4. **Variables**:
   ```
   VITE_API_URL = https://<your-backend-domain>/api
   ```
   This has to be set **before the build runs** since Vite bakes `import.meta.env.*`
   values in at build time, not runtime. If you change it later, you need to redeploy
   (trigger a rebuild), not just restart.
5. **Settings → Networking** → **Generate Domain**.
6. Deploy.

## 8. Close the loop: tighten CORS

Once you have the frontend's real domain, go back to the **backend** service's
Variables and change:
```
CORS_ORIGINS = https://<your-frontend-domain>
```
and redeploy the backend. (`*` is fine to get everything working first, but shouldn't
stay that way.)

## 9. Optional: switch to real market data (Alpaca)

By default this guide has you running on `USE_SYNTHETIC_DATA=true` -- realistic,
genuinely cointegrated data, but not real prices. To use real market data instead:

1. Go to https://alpaca.markets and sign up (free, no credit card required).
2. Once in the dashboard, make sure you're in **Paper Trading** mode (top-right toggle)
   -- paper trading accounts get full market data access for free, which is all this
   app needs (it never places real trades through Alpaca; it has its own separate
   internal paper trading feature).
3. Go to **Home** (or **API Keys** in the left nav) and generate a new key pair. Copy
   both the **API Key ID** and **Secret Key** immediately -- the secret is only shown once.
4. Set these on **all three** backend-related services (`backend`, `celery-worker`,
   `celery-beat`):
   ```
   USE_SYNTHETIC_DATA = false
   ALPACA_API_KEY     = <your key id>
   ALPACA_SECRET_KEY  = <your secret key>
   ```
5. Redeploy all three. The data layer tries Alpaca first, falls back to (unofficial,
   free) yfinance if Alpaca fails, and falls back to synthetic data only as a last
   resort -- so even if you mistype a key, the app degrades gracefully instead of
   breaking.
6. Verify: hit `https://<your-backend-domain>/api/scanner` and check the response --
   real tickers will show realistic current prices; you can spot-check one against
   Google Finance. (There's no field literally labeled "is this real," so the check is
   just eyeballing whether AAPL's price looks like AAPL's actual current price.)

## 10. Optional: enable "Sign in with Google"

This needs a Google OAuth Client ID, which only you can create (it's tied to your
Google account). Takes about 5 minutes:

1. Go to https://console.cloud.google.com/apis/credentials (create a project first if
   you don't have one -- top-left project dropdown → New Project, any name is fine).
2. **Configure consent screen** (first time only): **APIs & Services → OAuth consent
   screen** → External → fill in app name, your email, save. You can leave it in
   "Testing" mode -- for a portfolio demo you don't need Google's full verification
   review, but only emails you explicitly add as test users can sign in while in
   Testing mode. Add your own email (and anyone else you want to demo it to) under
   **Test users**. To let literally anyone sign in without an allowlist, you'd need to
   publish the app to "Production," which requires Google's review for some scopes --
   not necessary here, since this app only requests basic profile/email info.
3. **Create credentials → OAuth client ID** → Application type: **Web application**.
4. Under **Authorized JavaScript origins**, add both:
   - `http://localhost:5173` (local dev)
   - `https://<your-frontend-domain>` (whatever Railway gave you in step 7)
   You do NOT need to add a redirect URI -- Google Identity Services (what this app
   uses) works via a JS popup/One Tap flow, not a redirect.
5. Copy the generated **Client ID** (looks like
   `123456789-abc...xyz.apps.googleusercontent.com`).
6. Set it in **two places**:
   - Frontend service's Variables: `VITE_GOOGLE_CLIENT_ID = <that client id>` (must be
     set before the build, same caveat as `VITE_API_URL` above -- redeploy after adding it).
   - Backend service's Variables: `GOOGLE_CLIENT_ID = <that same client id>` (the
     backend verifies the token was issued for this exact client id).
7. Redeploy both services. The "Continue with Google" button will now render on the
   login page (it's hidden entirely when `VITE_GOOGLE_CLIENT_ID` is unset, so nothing
   breaks if you skip this whole section).

## 11. Verify the whole thing

Visit your frontend URL:
- Dashboard should load with opportunities (synthetic data by default, but real
  cointegration math -- or real prices if you did step 9).
- Register an account, open a paper trade, confirm PnL updates.
- Toggle "Go Live" on Paper Trading -- should show "Connected" (this is the part that
  needed the WebSocket URL fix, since frontend and backend are on different domains
  here, not one nginx origin like in Docker Compose).
- Strategy Lab → "Run in Background" → should show PENDING then SUCCESS within a few
  seconds (proves the Celery worker is actually running and picking up jobs).
- If you set up Alpaca (step 9): check `/api/scanner` prices against a real quote source
  to confirm you're on real data, not the synthetic fallback.
- If you set up Google Sign-In (step 10): the "Continue with Google" button should
  appear on the login page and complete a real sign-in.

## Costs

Railway's free tier / small usage should cover a portfolio demo comfortably (this app's
resource footprint is small -- SQLite-scale data volumes, no real trading), but Railway
is usage-billed past the free trial credit, not a flat free tier forever. Render's free
tier is a fully-free alternative but free-tier services spin down after 15 min idle and
take ~30s to wake back up on the next request -- worth knowing if a recruiter clicks the
link cold.
