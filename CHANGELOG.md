# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-07-03

### Added
- **`ResilientClient`**: Robust HTTP client with bounded retries, exponential backoff, random jitter, and a wall-clock-based `total_timeout` limit.
- **`DatabaseManager`**: Context-managed PostgreSQL-first connection pooling using SQLAlchemy, featuring pre-ping connection checks, pool timeouts, and lazy Pandas DataFrame integration.
- **`get_logger`**: Structured JSON formatter on top of standard `logging` with recursive dictionaries and URL parameter redaction for sensitive keys (e.g. passwords, tokens, private keys).
- **`LogContext`**: ContextVar-based context manager for injecting `job_id` and `request_id` fields across log records.
- **`NextLinkPagination`**: Type-validated paginator strategy yielding item-by-item records.
- **PEP 561 compliance**: Shipped `py.typed` inline type marker for downstream autocompletion and static type checkers.
- **CI Workflows**: Configured GHA CI matrix for Python 3.10 through 3.13, and OIDC Trusted Publishing to PyPI.
