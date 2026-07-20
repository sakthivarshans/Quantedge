import os
import logging
import time
from dotenv import load_dotenv
from fastapi import FastAPI, Request

load_dotenv()  # Load variables from backend/.env into the environment
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.core.logging_config import configure_logging
from app.core.database import Base, engine  # noqa: F401 (Base/engine kept for Alembic + other modules)
from app.core.rate_limit import limiter
from app import models  # noqa: F401 ensures models are registered
from app.api.routes import scanner, pairs, backtest, risk, auth, paper_trading, live, research, analytics

configure_logging()
logger = logging.getLogger("quantedge")

app = FastAPI(title="QuantEdge API", version="0.1.0",
              description="Institutional statistical arbitrage research platform API")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000, 2)
    logger.info(
        "request",
        extra={
            "http_method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": request.client.host if request.client else None,
        },
    )
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scanner.router)
app.include_router(pairs.router)
app.include_router(backtest.router)
app.include_router(risk.router)
app.include_router(risk.opt_router)
app.include_router(auth.router)
app.include_router(paper_trading.router)
app.include_router(live.router)
app.include_router(research.router)
app.include_router(analytics.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "QuantEdge API. See /docs for interactive API documentation."}
