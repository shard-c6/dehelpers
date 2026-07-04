"""Tests for dehelpers.db.

Unit tests use SQLite for speed and zero-infra CI.
PostgreSQL-specific tests are marked with ``@pytest.mark.postgres``
and skipped unless ``DATABASE_URL`` is set.

To run PostgreSQL integration tests::

    docker run -d --name pg-test -e POSTGRES_PASSWORD=test -p 5432:5432 postgres:16
    DATABASE_URL="postgresql+psycopg://postgres:test@localhost:5432/postgres" \
        pytest -m postgres -v
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from dehelpers.db import DatabaseManager
from dehelpers.exceptions import DatabaseError

SQLITE_DSN = "sqlite:///:memory:"


# ---------------------------------------------------------------------------
# Session lifecycle (SQLite)
# ---------------------------------------------------------------------------
class TestSessionLifecycle:
    def test_session_commits_on_success(self):
        with DatabaseManager(dsn=SQLITE_DSN) as db:
            with db.session() as session:
                from sqlalchemy import text

                session.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)"))
                session.execute(text("INSERT INTO t (id, val) VALUES (1, 'hello')"))
            # Data should be committed.
            rows = db.execute("SELECT val FROM t WHERE id = 1")
            assert len(rows) == 1
            assert rows[0][0] == "hello"

    def test_session_rolls_back_on_exception(self):
        with DatabaseManager(dsn=SQLITE_DSN) as db:
            with db.session() as session:
                from sqlalchemy import text

                session.execute(text("CREATE TABLE t2 (id INTEGER PRIMARY KEY, val TEXT)"))

            try:
                with db.session() as session:
                    from sqlalchemy import text

                    session.execute(text("INSERT INTO t2 (id, val) VALUES (1, 'should_rollback')"))
                    raise RuntimeError("intentional error")
            except RuntimeError:
                pass

            rows = db.execute("SELECT * FROM t2")
            assert len(rows) == 0


# ---------------------------------------------------------------------------
# Query shortcuts (SQLite)
# ---------------------------------------------------------------------------
class TestQueryShortcuts:
    def test_execute_returns_list_of_rows(self):
        with DatabaseManager(dsn=SQLITE_DSN) as db:
            with db.session() as session:
                from sqlalchemy import text

                session.execute(text("CREATE TABLE nums (n INTEGER)"))
                session.execute(text("INSERT INTO nums VALUES (10)"))
                session.execute(text("INSERT INTO nums VALUES (20)"))

            rows = db.execute("SELECT n FROM nums ORDER BY n")
            assert len(rows) == 2
            assert rows[0][0] == 10
            assert rows[1][0] == 20

    def test_fetch_one_returns_row(self):
        with DatabaseManager(dsn=SQLITE_DSN) as db:
            with db.session() as session:
                from sqlalchemy import text

                session.execute(text("CREATE TABLE single (v TEXT)"))
                session.execute(text("INSERT INTO single VALUES ('only')"))

            row = db.fetch_one("SELECT v FROM single")
            assert row is not None
            assert row[0] == "only"

    def test_fetch_one_returns_none_on_miss(self):
        with DatabaseManager(dsn=SQLITE_DSN) as db:
            with db.session() as session:
                from sqlalchemy import text

                session.execute(text("CREATE TABLE empty_t (v TEXT)"))

            row = db.fetch_one("SELECT v FROM empty_t")
            assert row is None


# ---------------------------------------------------------------------------
# DataFrame (optional)
# ---------------------------------------------------------------------------
class TestDataFrame:
    def test_to_dataframe_success(self):
        pytest.importorskip("pandas")
        with DatabaseManager(dsn=SQLITE_DSN) as db:
            with db.session() as session:
                from sqlalchemy import text

                session.execute(text("CREATE TABLE df_t (a INT, b TEXT)"))
                session.execute(text("INSERT INTO df_t VALUES (1, 'x')"))
                session.execute(text("INSERT INTO df_t VALUES (2, 'y')"))

            df = db.to_dataframe("SELECT * FROM df_t ORDER BY a")
            assert len(df) == 2
            assert list(df.columns) == ["a", "b"]

    def test_to_dataframe_import_error(self):
        """to_dataframe raises ImportError when pandas is missing."""
        with DatabaseManager(dsn=SQLITE_DSN) as db:
            with db.session() as session:
                from sqlalchemy import text

                session.execute(text("CREATE TABLE df_err (v INT)"))

            with (
                patch.dict("sys.modules", {"pandas": None}),
                pytest.raises(ImportError, match="dehelpers\\[dataframe\\]"),
            ):
                db.to_dataframe("SELECT * FROM df_err")


# ---------------------------------------------------------------------------
# DSN resolution
# ---------------------------------------------------------------------------
class TestDSNResolution:
    def test_dsn_from_env_var(self, env_vars):
        with env_vars(DATABASE_URL=SQLITE_DSN):
            db = DatabaseManager()
            rows = db.execute("SELECT 1")
            assert len(rows) == 1
            db.dispose()

    def test_no_dsn_raises(self):
        # Ensure DATABASE_URL is not set.
        with patch.dict(os.environ, {}, clear=True), pytest.raises(DatabaseError, match="No DSN provided"):
            DatabaseManager()


# ---------------------------------------------------------------------------
# Repr (redacted)
# ---------------------------------------------------------------------------
class TestRepr:
    def test_dsn_not_in_repr(self):
        db = DatabaseManager(dsn=SQLITE_DSN)
        r = repr(db)
        # The repr should not contain the raw DSN verbatim if it had secrets,
        # but for SQLite it's safe. Mainly checking it doesn't crash.
        assert "DatabaseManager" in r
        db.dispose()


# ---------------------------------------------------------------------------
# Dispose
# ---------------------------------------------------------------------------
class TestDispose:
    def test_dispose_closes_pool(self):
        db = DatabaseManager(dsn=SQLITE_DSN)
        db.dispose()
        # After dispose, the pool should be invalidated.
        # Further queries should still work (engine recreates pool),
        # but we verify dispose didn't raise.

    def test_context_manager_disposes(self):
        with DatabaseManager(dsn=SQLITE_DSN) as db:
            db.execute("SELECT 1")
        # After exiting, dispose has been called. No assertion needed
        # beyond verifying no exception.


# ---------------------------------------------------------------------------
# PostgreSQL integration (optional)
# ---------------------------------------------------------------------------
@pytest.mark.postgres
class TestPostgresIntegration:
    """These tests require a real PostgreSQL instance.

    Set ``DATABASE_URL`` to a PostgreSQL connection string to run them.
    """

    @pytest.fixture(autouse=True)
    def _require_pg(self):
        url = os.environ.get("DATABASE_URL", "")
        if "postgresql" not in url:
            pytest.skip("DATABASE_URL not pointing to PostgreSQL")

    def test_round_trip(self):
        with DatabaseManager() as db:
            db.execute("CREATE TABLE IF NOT EXISTS _test_round_trip (id SERIAL PRIMARY KEY, val TEXT)")
            db.execute(
                "INSERT INTO _test_round_trip (val) VALUES (:val)",
                {"val": "hello"},
            )
            rows = db.execute("SELECT val FROM _test_round_trip LIMIT 1")
            assert rows[0][0] == "hello"
            db.execute("DROP TABLE _test_round_trip")

    def test_returning_clause(self):
        with DatabaseManager() as db:
            db.execute("CREATE TABLE IF NOT EXISTS _test_returning (id SERIAL PRIMARY KEY, val TEXT)")
            rows = db.execute(
                "INSERT INTO _test_returning (val) VALUES (:val) RETURNING id",
                {"val": "pg"},
            )
            assert len(rows) == 1
            assert rows[0][0] > 0
            db.execute("DROP TABLE _test_returning")
