"""Complete API → PostgreSQL ingestion pipeline with pagination.

Demonstrates:
  - ResilientClient with paginated fetching
  - DatabaseManager with session-based transactions
  - Structured logging with LogContext
  - Graceful error handling and cleanup

Requires:
  - A running PostgreSQL instance
  - DATABASE_URL environment variable set, e.g.:
    DATABASE_URL="postgresql+psycopg://postgres:test@localhost:5432/postgres"

Uses the free JSONPlaceholder API — no API key required.
"""

import sys

from dehelpers import (
    DatabaseManager,
    LogContext,
    PaginationError,
    ResilientClient,
    get_logger,
)

# ---------------------------------------------------------------------------
# 1. Initialize logging
# ---------------------------------------------------------------------------
logger = get_logger("user_ingestion", job_id="paginated-sync")


# ---------------------------------------------------------------------------
# 2. Connect to the database
# ---------------------------------------------------------------------------
try:
    db = DatabaseManager()  # Reads DATABASE_URL from environment
except Exception as exc:
    logger.error("Cannot connect to database", exc_info=exc)
    sys.exit(1)


# ---------------------------------------------------------------------------
# 3. Create target table (idempotent)
# ---------------------------------------------------------------------------
with db.session() as session:
    session.execute(
        "CREATE TABLE IF NOT EXISTS demo_users ("
        "  id INTEGER PRIMARY KEY,"
        "  name VARCHAR(100),"
        "  email VARCHAR(100),"
        "  company VARCHAR(100)"
        ")"
    )
logger.info("Target table verified")


# ---------------------------------------------------------------------------
# 4. Fetch and ingest users
# ---------------------------------------------------------------------------
client = ResilientClient()

# JSONPlaceholder returns a flat list (no pagination links), so we
# fetch it as a single request here.  For APIs that return paginated
# responses with a "next" URL, use client.paginate() instead:
#
#   for user in client.paginate("https://api.example.com/v1/users"):
#       ...

try:
    resp = client.get("https://jsonplaceholder.typicode.com/users")
    users = resp.json()
    logger.info("Fetched users from API", extra={"count": len(users)})

    for user in users:
        with LogContext(request_id=f"user-{user['id']}"):
            with db.session() as session:
                session.execute(
                    "INSERT INTO demo_users (id, name, email, company) "
                    "VALUES (:id, :name, :email, :company) "
                    "ON CONFLICT (id) DO UPDATE "
                    "SET name = EXCLUDED.name, "
                    "    email = EXCLUDED.email, "
                    "    company = EXCLUDED.company",
                    {
                        "id": user["id"],
                        "name": user["name"],
                        "email": user["email"],
                        "company": user.get("company", {}).get("name", "N/A"),
                    },
                )
            logger.info("Ingested user", extra={"name": user["name"]})

except PaginationError as exc:
    logger.error(
        "Pagination failed — partial results available",
        extra={"collected": len(exc.collected_items)},
    )
    sys.exit(1)

except Exception as exc:
    logger.error("Pipeline failed", exc_info=exc)
    sys.exit(1)

finally:
    client.close()
    db.dispose()


# ---------------------------------------------------------------------------
# 5. Verify results
# ---------------------------------------------------------------------------
db2 = DatabaseManager()
rows = db2.execute("SELECT id, name, email FROM demo_users ORDER BY id")
logger.info("Pipeline complete", extra={"total_rows": len(rows)})

for row in rows:
    print(f"  [{row[0]}] {row[1]} <{row[2]}>")

db2.dispose()
