"""dehelpers: Lightweight utilities for data engineering pipelines."""

from typing import Any

from dehelpers.exceptions import (
    DatabaseError,
    DPHError,
    PaginationError,
    RetryError,
)
from dehelpers.logger import LogContext, get_logger

__all__ = [
    # API
    "ResilientClient",
    "AsyncResilientClient",
    "RetryPolicy",
    "NextLinkPagination",
    # Database
    "DatabaseManager",
    # Logger
    "get_logger",
    "LogContext",
    # Exceptions
    "DPHError",
    "RetryError",
    "PaginationError",
    "DatabaseError",
]

__version__ = "0.2.0"


def __getattr__(name: str) -> Any:
    if name in {"ResilientClient", "AsyncResilientClient", "RetryPolicy", "NextLinkPagination"}:
        try:
            import dehelpers.api as api
        except ImportError as exc:
            raise ImportError(
                f"{name} requires the 'http' extra. Install with: pip install dehelpers[http]"
            ) from exc
        return getattr(api, name)

    if name == "DatabaseManager":
        try:
            import dehelpers.db as db
        except ImportError as exc:
            raise ImportError(
                "DatabaseManager requires the 'db' extra. Install with: pip install dehelpers[db]"
            ) from exc
        return getattr(db, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
