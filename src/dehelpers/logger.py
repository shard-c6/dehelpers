"""Structured JSON logger with automatic secret redaction.

Built entirely on the stdlib :mod:`logging` module — no third-party
dependencies.  Every log record is emitted as a single JSON line with
a consistent schema, making it ready for containerised environments
like Airflow, AWS ECS, or Google Cloud Run.

Usage::

    from dehelpers import get_logger, LogContext

    log = get_logger("my_etl", job_id="daily-sales")
    log.info("Starting extraction", extra={"source": "api"})

    with LogContext(request_id="abc-123"):
        log.info("Fetched page", extra={"page": 1})
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from dehelpers._redact import redact_dict

__all__ = ["get_logger", "LogContext"]

# ---------------------------------------------------------------------------
# Context variables for cross-cutting fields
# ---------------------------------------------------------------------------
_ctx_job_id: ContextVar[str | None] = ContextVar("job_id", default=None)
_ctx_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


class LogContext:
    """Context manager that injects ``job_id`` and/or ``request_id``
    into every log record emitted within its scope.

    Example::

        with LogContext(job_id="etl-run-42", request_id="req-abc"):
            logger.info("Processing")
    """

    def __init__(
        self,
        *,
        job_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        self._job_id = job_id
        self._request_id = request_id
        self._tokens: list = []

    def __enter__(self) -> LogContext:
        if self._job_id is not None:
            self._tokens.append(_ctx_job_id.set(self._job_id))
        if self._request_id is not None:
            self._tokens.append(_ctx_request_id.set(self._request_id))
        return self

    def __exit__(self, *_: object) -> None:
        for token in reversed(self._tokens):
            token.var.reset(token)
        self._tokens.clear()


# ---------------------------------------------------------------------------
# JSON Formatter
# ---------------------------------------------------------------------------
class _JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON with redaction.

    Schema (every record)::

        {
          "timestamp": "2026-07-02T11:43:50.123456Z",
          "level": "INFO",
          "message": "Fetched 200 rows",
          "module": "db",
          "function": "execute_query",
          "job_id": "etl-daily-sales",
          "request_id": null,
          "error": null
        }
    """

    # Fields injected by logging internals that we don't want in output.
    _INTERNAL_KEYS = frozenset(
        {
            "name",
            "msg",
            "args",
            "created",
            "relativeCreated",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "pathname",
            "filename",
            "levelno",
            "levelname",
            "module",
            "msecs",
            "process",
            "processName",
            "thread",
            "threadName",
            "taskName",
            "message",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        """Return a single-line JSON string for *record*."""
        try:
            return self._safe_format(record)
        except Exception:
            # Recursion / serialization guard: fallback to plain text.
            return json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "ERROR",
                    "message": f"[FORMATTER ERROR] {record.getMessage()}",
                    "module": getattr(record, "module", "unknown"),
                    "function": getattr(record, "funcName", "unknown"),
                    "_formatter_error": True,
                }
            )

    def _safe_format(self, record: logging.LogRecord) -> str:
        # Build the structured payload.
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "job_id": _ctx_job_id.get(),
            "request_id": _ctx_request_id.get(),
            "error": None,
        }

        # Merge user-supplied extra fields (redacted).
        extras: dict[str, Any] = {k: v for k, v in record.__dict__.items() if k not in self._INTERNAL_KEYS}
        if extras:
            payload.update(redact_dict(extras))

        # Serialise exception info if present.
        if record.exc_info and record.exc_info[0] is not None:
            exc_type, exc_value, exc_tb = record.exc_info
            payload["error"] = {
                "type": exc_type.__name__ if exc_type else "Unknown",
                "message": str(exc_value),
                "traceback": traceback.format_exception(exc_type, exc_value, exc_tb)[
                    -3:
                ],  # last 3 frames to keep logs concise
            }

        return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------
def get_logger(
    name: str,
    *,
    job_id: str | None = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """Return a stdlib :class:`~logging.Logger` with JSON formatting.

    Parameters
    ----------
    name:
        Logger name (typically the module or pipeline name).
    job_id:
        Optional default job identifier injected into every record.
        Can also be set/overridden at runtime via :class:`LogContext`.
    level:
        Logging level.  Defaults to ``INFO``.

    Returns
    -------
    logging.Logger
        A configured logger that writes JSON to *stderr*.
    """
    if job_id is not None:
        _ctx_job_id.set(job_id)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers on repeated calls.
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_JSONFormatter())
        logger.addHandler(handler)

    # Don't propagate to root logger to avoid double output.
    logger.propagate = False

    return logger
