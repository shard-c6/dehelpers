"""de-pipeline-helpers: Lightweight utilities for data engineering pipelines."""

from de_pipeline_helpers.api import NextLinkPagination, ResilientClient, RetryPolicy
from de_pipeline_helpers.db import DatabaseManager
from de_pipeline_helpers.exceptions import (
    DatabaseError,
    DPHError,
    PaginationError,
    RetryError,
)
from de_pipeline_helpers.logger import LogContext, get_logger

__all__ = [
    # API
    "ResilientClient",
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

__version__ = "0.1.0"
