"""Tests for de_pipeline_helpers.logger."""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from de_pipeline_helpers.logger import LogContext, get_logger


def _capture_log(logger: logging.Logger) -> StringIO:
    """Attach a StringIO handler and return the stream."""
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logger.handlers[0].formatter)
    logger.handlers = [handler]
    return stream


# ---------------------------------------------------------------------------
# Schema & JSON validity
# ---------------------------------------------------------------------------
class TestLoggerSchema:
    def test_output_is_valid_json(self):
        log = get_logger("test_json_valid")
        stream = _capture_log(log)
        log.info("hello")
        line = stream.getvalue().strip()
        parsed = json.loads(line)
        assert isinstance(parsed, dict)

    def test_required_fields_present(self):
        log = get_logger("test_fields")
        stream = _capture_log(log)
        log.info("check fields")
        record = json.loads(stream.getvalue().strip())
        for field in ("timestamp", "level", "message", "module", "function"):
            assert field in record, f"Missing field: {field}"

    def test_level_matches(self):
        log = get_logger("test_level")
        stream = _capture_log(log)
        log.warning("warn!")
        record = json.loads(stream.getvalue().strip())
        assert record["level"] == "WARNING"

    def test_message_content(self):
        log = get_logger("test_msg")
        stream = _capture_log(log)
        log.info("extracted %d rows", 42)
        record = json.loads(stream.getvalue().strip())
        assert record["message"] == "extracted 42 rows"


# ---------------------------------------------------------------------------
# Context injection
# ---------------------------------------------------------------------------
class TestLogContext:
    def test_job_id_injected(self):
        log = get_logger("test_ctx_job")
        stream = _capture_log(log)
        with LogContext(job_id="etl-daily"):
            log.info("inside context")
        record = json.loads(stream.getvalue().strip())
        assert record["job_id"] == "etl-daily"

    def test_request_id_injected(self):
        log = get_logger("test_ctx_req")
        stream = _capture_log(log)
        with LogContext(request_id="req-abc"):
            log.info("inside context")
        record = json.loads(stream.getvalue().strip())
        assert record["request_id"] == "req-abc"

    def test_context_resets_after_exit(self):
        log = get_logger("test_ctx_reset")
        stream = _capture_log(log)
        with LogContext(job_id="temp"):
            pass
        log.info("after context")
        record = json.loads(stream.getvalue().strip())
        # job_id should be None or whatever it was before the context.
        assert record.get("job_id") != "temp"


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------
class TestLogRedaction:
    def test_sensitive_extra_redacted(self):
        log = get_logger("test_redact")
        stream = _capture_log(log)
        log.info("connecting", extra={"db_password": "hunter2"})
        record = json.loads(stream.getvalue().strip())
        assert record.get("db_password") == "***REDACTED***"
        assert "hunter2" not in stream.getvalue()

    def test_nested_extra_redacted(self):
        log = get_logger("test_redact_nested")
        stream = _capture_log(log)
        log.info("config", extra={"config": {"client_secret": "s3cr3t"}})
        record = json.loads(stream.getvalue().strip())
        assert record["config"]["client_secret"] == "***REDACTED***"

    def test_non_sensitive_extra_preserved(self):
        log = get_logger("test_redact_safe")
        stream = _capture_log(log)
        log.info("data", extra={"row_count": 500})
        record = json.loads(stream.getvalue().strip())
        assert record["row_count"] == 500


# ---------------------------------------------------------------------------
# Exception serialisation
# ---------------------------------------------------------------------------
class TestLogExceptions:
    def test_exception_structured(self):
        log = get_logger("test_exc")
        stream = _capture_log(log)
        try:
            raise ValueError("bad value")
        except ValueError:
            log.exception("something broke")
        record = json.loads(stream.getvalue().strip())
        error = record["error"]
        assert error["type"] == "ValueError"
        assert "bad value" in error["message"]
        assert isinstance(error["traceback"], list)

    def test_no_exception_error_is_null(self):
        log = get_logger("test_no_exc")
        stream = _capture_log(log)
        log.info("all good")
        record = json.loads(stream.getvalue().strip())
        assert record["error"] is None


# ---------------------------------------------------------------------------
# Formatter safety
# ---------------------------------------------------------------------------
class TestFormatterSafety:
    def test_unserializable_extra_does_not_crash(self):
        """Objects that can't be JSON-serialised should not crash the logger."""
        log = get_logger("test_safe_format")
        stream = _capture_log(log)

        class Unpicklable:
            def __repr__(self):
                raise RuntimeError("boom")

        # This should not raise — the formatter's fallback catches it.
        log.info("test", extra={"bad": Unpicklable()})
        output = stream.getvalue().strip()
        # Either the normal JSON or the fallback JSON should appear.
        parsed = json.loads(output)
        assert "message" in parsed or "_formatter_error" in parsed
