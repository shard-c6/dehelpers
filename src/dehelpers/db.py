"""PostgreSQL-first database helper with safe connection pooling.

Built on SQLAlchemy 2.0 with context-managed sessions, pre-ping
health checks, connection recycling, and optional Pandas DataFrame
output.

Usage::

    from dehelpers import DatabaseManager

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

from dehelpers._redact import redact_url
from dehelpers.exceptions import DatabaseError

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
        :class:`~dehelpers.exceptions.DatabaseError`.
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
            raise DatabaseError("No DSN provided and DATABASE_URL environment variable is not set.")
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

            pip install dehelpers[dataframe]

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
                "pandas is required for to_dataframe(). Install it with: pip install dehelpers[dataframe]"
            ) from None

        try:
            with self._engine.connect() as conn:
                return pd.read_sql(text(sql), conn, params=params or {})
        except SQLAlchemyError as exc:
            raise DatabaseError(f"DataFrame query failed: {exc}") from exc

    def bulk_insert(
        self,
        table_name: str,
        records: list[dict[str, Any]],
        chunk_size: int = 1000,
    ) -> None:
        """Insert multiple records into a table efficiently using batches.

        Parameters
        ----------
        table_name:
            Target table name.
        records:
            List of dictionaries representing rows.
        chunk_size:
            Number of rows to insert per batch.
        """
        if not records:
            return

        from sqlalchemy import MetaData, Table, insert

        try:
            with self._engine.connect() as conn:
                metadata = MetaData()
                table = Table(table_name, metadata, autoload_with=conn)

                for i in range(0, len(records), chunk_size):
                    chunk = records[i:i + chunk_size]
                    conn.execute(insert(table), chunk)

                conn.commit()
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Bulk insert failed: {exc}") from exc

    def copy_from_file(
        self,
        table_name: str,
        file_path: str,
        columns: tuple[str, ...] | None = None,
        delimiter: str = ",",
        header: bool = True,
    ) -> None:
        """High-throughput load via PostgreSQL COPY (requires psycopg).

        Parameters
        ----------
        table_name:
            Target table name.
        file_path:
            Path to the local CSV/TSV file.
        columns:
            Optional tuple of column names to load.
        delimiter:
            Field delimiter.
        header:
            If True, skips the first row (header).
        """
        if "psycopg" not in str(self._engine.driver):
            raise DatabaseError("copy_from_file is only supported with PostgreSQL (psycopg3 driver).")

        try:
            with self._engine.connect() as conn:
                raw_conn = conn.connection.dbapi_connection

                cols_str = f"({', '.join(columns)})" if columns else ""
                header_str = "HEADER" if header else ""

                sql = f"COPY {table_name} {cols_str} FROM STDIN WITH (FORMAT CSV, DELIMITER '{delimiter}', {header_str})"

                with raw_conn.cursor() as cur, cur.copy(sql) as copy, open(file_path, "rb") as f:  # type: ignore
                    while data := f.read(8192):
                        copy.write(data)

                conn.commit()
        except Exception as exc:
            raise DatabaseError(f"COPY operation failed: {exc}") from exc

    def from_dataframe(
        self,
        df: Any,
        table_name: str,
        if_exists: str = "append",
        index: bool = False,
        chunksize: int | None = None,
    ) -> None:
        """Write a Pandas DataFrame directly to the database.

        Requires the ``[dataframe]`` extra::

            pip install dehelpers[dataframe]

        Parameters
        ----------
        df:
            The Pandas DataFrame to write.
        table_name:
            Target table name.
        if_exists:
            Action to take if the table already exists ('fail', 'replace', 'append').
        index:
            Whether to write the DataFrame index as a column.
        chunksize:
            Number of rows to write at a time.
        """
        try:
            import pandas  # noqa: F401
        except ImportError:
            raise ImportError(
                "pandas is required for from_dataframe(). Install it with: pip install dehelpers[dataframe]"
            ) from None

        try:
            with self._engine.connect() as conn:
                df.to_sql(
                    name=table_name,
                    con=conn,
                    if_exists=if_exists,
                    index=index,
                    chunksize=chunksize,
                )
                conn.commit()
        except SQLAlchemyError as exc:
            raise DatabaseError(f"DataFrame write failed: {exc}") from exc

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
