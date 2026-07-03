"""Custom exceptions for de-pipeline-helpers.

Centralised exception hierarchy so every module raises from here
instead of scattering ad-hoc exceptions.
"""

__all__ = ["DPHError", "RetryError", "PaginationError", "DatabaseError"]


class DPHError(Exception):
    """Base exception for de-pipeline-helpers."""


class RetryError(DPHError):
    """Raised when all retry attempts are exhausted or total timeout exceeded.

    The original exception (connection error, timeout, etc.) is always
    preserved as ``__cause__`` via ``raise RetryError(...) from original``.

    Attributes:
        last_status: HTTP status code of the last attempt, or ``None``
            if the failure was a connection-level error.
        attempts: Total number of attempts made (including the first).
    """

    def __init__(
        self,
        message: str,
        *,
        last_status: int | None = None,
        attempts: int = 0,
    ) -> None:
        super().__init__(message)
        self.last_status = last_status
        self.attempts = attempts


class PaginationError(DPHError):
    """Raised on pagination failure.

    Carries items collected before the failure so callers can decide
    whether to use partial results.

    Attributes:
        collected_items: Items successfully fetched before the error.
    """

    def __init__(
        self,
        message: str,
        *,
        collected_items: list[dict] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.collected_items = collected_items or []
        if cause is not None:
            self.__cause__ = cause


class DatabaseError(DPHError):
    """Raised on database operation failures.

    Wraps SQLAlchemy or driver-level exceptions while keeping the
    original available via ``__cause__``.
    """
