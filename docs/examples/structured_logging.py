"""Structured logging with dehelpers.

Demonstrates:
  - JSON logger setup with get_logger
  - LogContext for injecting job_id and request_id
  - Automatic secret redaction in extra fields
  - Error logging with traceback

No external services required — runs entirely locally.
"""

from dehelpers import LogContext, get_logger

# ---------------------------------------------------------------------------
# 1. Basic logger
# ---------------------------------------------------------------------------
logger = get_logger("logging_demo")

logger.info("Basic log message")
logger.info("Log with extra fields", extra={"source": "demo", "row_count": 42})


# ---------------------------------------------------------------------------
# 2. Logger with a default job_id
# ---------------------------------------------------------------------------
job_logger = get_logger("etl_job", job_id="daily-sales-2026-07-03")

job_logger.info("Starting extraction")
job_logger.info("Fetched data", extra={"endpoint": "/api/sales", "records": 150})


# ---------------------------------------------------------------------------
# 3. LogContext — scoped context injection
# ---------------------------------------------------------------------------
pipeline_logger = get_logger("pipeline")

# job_id and request_id appear in every log inside the block
with LogContext(job_id="nightly-sync", request_id="req-001"):
    pipeline_logger.info("Processing batch A")
    pipeline_logger.info("Batch A complete", extra={"processed": 500})

with LogContext(request_id="req-002"):
    pipeline_logger.info("Processing batch B")

# Outside the context — job_id and request_id revert
pipeline_logger.info("Pipeline finished")


# ---------------------------------------------------------------------------
# 4. Automatic secret redaction
# ---------------------------------------------------------------------------
secure_logger = get_logger("redaction_demo")

# These sensitive values are automatically replaced with ***REDACTED***
secure_logger.info(
    "Connecting to API",
    extra={
        "endpoint": "https://api.example.com/data",
        "api_key": "sk-secret-12345",  # ← REDACTED
        "authorization": "Bearer eyJhbGci...",  # ← REDACTED
        "user": "admin",  # ← kept (not sensitive)
    },
)

# Nested dictionaries are also redacted recursively
secure_logger.info(
    "Database config loaded",
    extra={
        "config": {
            "host": "db.example.com",
            "port": 5432,
            "db_password": "super-secret",  # ← REDACTED (matches "password")
            "pool_size": 5,
        }
    },
)


# ---------------------------------------------------------------------------
# 5. Error logging with traceback
# ---------------------------------------------------------------------------
error_logger = get_logger("error_demo")

try:
    result = 1 / 0
except ZeroDivisionError:
    error_logger.error("Calculation failed", exc_info=True)
    # The JSON output includes an "error" field with type, message,
    # and the last 3 traceback frames.
