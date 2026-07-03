"""PostgreSQL-first database helper with safe connection pooling.

Built on SQLAlchemy 2.0 with context-managed sessions, pre-ping
health checks, connection recycling, and optional Pandas DataFrame
output.

Usage::

    from de_pipeline_helpers import DatabaseManager

    with DatabaseManager() as db:          # reads DATABASE_URL env var
        rows = db.execute("SELECT * FROM users WHERE active = :active",
                          {"active": True})
        df = db.to_dataframe("SELECT * FROM sales")

.. warning::

    If using in forked environments (Airflow, multiprocessing), create
    the ``DatabaseManager`` **inside each worker process** or call
    :meth:`dispose` before forking.
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import Row, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from de_pipeline_helpers._redact import redact_url
from de_pipeline_helpers.exceptions import DatabaseError

__all__ = ["DatabaseManager"]


class DatabaseManager:
    """PostgreSQL connection manager with safe pooling defaults.

    Parameters
    ----------
    dsn:
        SQLAlchemy connection URL.  Falls back to the ``DATABASE_URL``
        environment variable when ``None``.
    pool_size:
        Number of persistent connections in the pool.
    max_overflow:
        Maximum additional connections beyond *pool_size*.
    pool_recycle:
        Seconds before a connection is recycled (replaced).
    pool_pre_ping:
        If ``True``, issues a lightweight ``SELECT 1`` before checking
        out a connection to verify it is still alive.
    pool_timeout:
        Seconds to wait for a connection from the pool before raising
        :class:`~de_pipeline_helpers.exceptions.DatabaseError`.
    """

    def __init__(
        self,
        dsn: str | None = None,
        *,
        pool_size: int = 5,
        max_overflow: int = 2,
        pool_recycle: int = 1800,
        pool_pre_ping: bool = True,
        pool_timeout: int = 30,
    ) -> None:
        resolved_dsn = dsn or os.environ.get("DATABASE_URL")
        if not resolved_dsn:
            raise DatabaseError(
                "No DSN provided and DATABASE_URL environment variable is not set."
            )
        self._dsn = resolved_dsn

        # SQLite uses SingletonThreadPool which doesn't support pool_size,
        # max_overflow, or pool_timeout.  Only pass those for real backends.
        engine_kwargs: dict[str, object] = {
            "pool_recycle": pool_recycle,
            "pool_pre_ping": pool_pre_ping,
        }
        if not resolved_dsn.startswith("sqlite"):
            engine_kwargs.update(
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=pool_timeout,
            )
        self._engine = create_engine(resolved_dsn, **engine_kwargs)
        self._session_factory = sessionmaker(bind=self._engine)

    # -- Context manager ----------------------------------------------------

    def __enter__(self) -> DatabaseManager:
        return self

    def __exit__(self, *_: object) -> None:
        self.dispose()

    # -- Session management -------------------------------------------------

    def session(self) -> _SessionContext:
        """Return a context manager that yields a SQLAlchemy ``Session``.

        Auto-commits on clean exit and auto-rolls-back on exception.

        Example::

            with db.session() as session:
                session.execute(text("INSERT INTO logs ..."))
        """
        return _SessionContext(self._session_factory)

    # -- Query shortcuts ----------------------------------------------------

    def execute(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> list[Row]:
        """Execute *sql* and return all rows as a ``list[Row]``.

        The connection is returned to the pool immediately after.

        Parameters
        ----------
        sql:
            SQL string (use ``:param`` style placeholders).
        params:
            Bind parameters.

        Returns
        -------
        list[Row]
            Rows from the query result.  Each :class:`~sqlalchemy.engine.Row`
            supports both index and attribute access.
        """
        try:
            with self._engine.connect() as conn:
                result = conn.execute(text(sql), params or {})
                rows = list(result.fetchall())
                conn.commit()
                return rows
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Query execution failed: {exc}") from exc

    def fetch_one(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> Row | None:
        """Execute *sql* and return the first row, or ``None``.

        Parameters
        ----------
        sql:
            SQL string.
        params:
            Bind parameters.
        """
        try:
            with self._engine.connect() as conn:
                result = conn.execute(text(sql), params or {})
                row = result.fetchone()
                conn.commit()
                return row
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Query execution failed: {exc}") from exc

    def to_dataframe(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> Any:  # -> pd.DataFrame (lazy import)
        """Execute *sql* and return the result as a Pandas DataFrame.

        Requires the ``[dataframe]`` extra::

            pip install de-pipeline-helpers[dataframe]

        Raises
        ------
        ImportError
            If ``pandas`` is not installed.
        DatabaseError
            On query failure.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for to_dataframe(). "
                "Install it with: pip install de-pipeline-helpers[dataframe]"
            ) from None

        try:
            with self._engine.connect() as conn:
                return pd.read_sql(text(sql), conn, params=params or {})
        except SQLAlchemyError as exc:
            raise DatabaseError(
                f"DataFrame query failed: {exc}"
            ) from exc

    # -- Cleanup ------------------------------------------------------------

    def dispose(self) -> None:
        """Dispose the engine and close all pooled connections."""
        self._engine.dispose()

    # -- Repr (redacted) ----------------------------------------------------

    def __repr__(self) -> str:
        safe = redact_url(self._dsn)
        return f"DatabaseManager(dsn={safe!r})"


# ---------------------------------------------------------------------------
# Session context manager
# ---------------------------------------------------------------------------
class _SessionContext:
    """Internal context manager wrapping a SQLAlchemy Session.

    Commits on clean exit, rolls back on exception.
    """

    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory
        self._session: Session | None = None

    def __enter__(self) -> Session:
        self._session = self._factory()
        return self._session

    def __exit__(self, exc_type: type | None, *_: object) -> None:
        if self._session is None:
            return
        try:
            if exc_type is None:
                self._session.commit()
            else:
                self._session.rollback()
        finally:
            self._session.close()
