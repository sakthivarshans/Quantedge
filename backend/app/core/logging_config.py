"""
Structured logging + optional error monitoring.

Logs are emitted as JSON lines (easy to ship to CloudWatch/Datadog/etc in production).
If SENTRY_DSN is set, errors are also reported to Sentry; if unset, Sentry is skipped
entirely so this has zero effect on local dev.
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Allow callers to attach structured context: logger.info("msg", extra={"user_id": 1})
        for key, value in record.__dict__.items():
            if key not in payload and key not in (
                "args", "msg", "levelno", "levelname", "pathname", "filename", "module",
                "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created",
                "msecs", "relativeCreated", "thread", "threadName", "processName", "process",
                "name",
            ):
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Quiet down noisy libraries at INFO unless explicitly debugging
    for noisy in ("uvicorn.access", "httpx", "urllib3"):
        logging.getLogger(noisy).setLevel(os.getenv("LOG_LEVEL_LIBS", "WARNING").upper())

    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.logging import LoggingIntegration

            sentry_sdk.init(
                dsn=sentry_dsn,
                environment=os.getenv("ENVIRONMENT", "development"),
                traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
                integrations=[
                    FastApiIntegration(),
                    LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
                ],
            )
            root.info("Sentry error monitoring enabled")
        except ImportError:
            root.warning("SENTRY_DSN is set but sentry-sdk is not installed; skipping Sentry init")
