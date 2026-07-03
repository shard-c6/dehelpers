# dehelpers

<p align="left">
  <a href="https://pypi.org/project/dehelpers/"><img src="https://img.shields.io/pypi/v/dehelpers.svg?color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/dehelpers/"><img src="https://img.shields.io/pypi/pyversions/dehelpers.svg" alt="Python versions"></a>
  <a href="https://github.com/shard-c6/dehelpers/actions/workflows/ci.yml"><img src="https://github.com/shard-c6/dehelpers/actions/workflows/ci.yml/badge.svg" alt="CI Status"></a>
  <a href="https://github.com/shard-c6/dehelpers/blob/main/LICENSE"><img src="https://img.shields.io/github/license/shard-c6/dehelpers.svg" alt="License"></a>
  <a href="https://pypi.org/project/dehelpers/"><img src="https://img.shields.io/pypi/dm/dehelpers.svg" alt="Downloads"></a>
</p>

Lightweight, production-hardened Python utilities for data engineering pipelines.

**Resilient HTTP** · **PostgreSQL helpers** · **Structured JSON logging** — with automatic secret redaction, bounded retries, and safe connection pooling.

---

## Architecture & Flow

```mermaid
graph TD
    subgraph External [External APIs & Services]
        REST_API[REST API Source]
    end

    subgraph DPH [dehelpers Package]
        direction TB
        subgraph Client [Resilient Client]
            RC[ResilientClient] --> |Configured by| RP[RetryPolicy]
            RC --> |Iterates with| NLP[NextLinkPagination]
            RC --> |Sanitizes query| RU[redact_url]
        end

        subgraph Logger [Structured Logger]
            GL[get_logger] --> |Formats record| JF[JSONFormatter]
            LogCtx[LogContext] --> |Context injection| CV[job_id / request_id]
            JF --> |Deep-redacts secrets| RD[redact_dict]
        end

        subgraph Database [Database Manager]
            DBM[DatabaseManager] --> |Yields sessions| SC[_SessionContext]
            DBM --> |Manages pool| SQLA[SQLAlchemy Engine]
            DBM --> |Lazy Load| DF[Pandas DataFrame]
        end
    end

    subgraph Target [Storage / Logs]
        PG[(PostgreSQL DB)]
        Stderr[Stderr / Cloud Logs]
    end

    REST_API ==> |Inbound Data| RC
    RC --> |Yields items / logs events| GL
    GL ==> |JSON Output| Stderr
    RC --> |Normalized data| DBM
    DBM ==> |Pool connections| PG
```

---

## Boundaries & Capabilities

Here is exactly what this package **is** and what it **is not**:

| Category / Layer | What this IS | What this IS NOT |
|:---|:---|:---|
| **API / HTTP** | A retry-protected wrapper around `requests.Session` with exponential backoff, jitter, and simple pagination. | An asynchronous network library (like `aiohttp` or `httpx`), fully-fledged HTTP client replacement, or GraphQL API wrapper. |
| **Database** | A thread-safe connection manager for PostgreSQL with pooling configuration, automated transaction commits/rollbacks, and lazy DataFrame output. | An Object-Relational Mapper (ORM) (like SQLModel/SQLAlchemy ORM), schema migration engine (like Alembic), or database administration tool. |
| **Logging** | A zero-dependency structured JSON formatter on top of standard `logging` with automatic deep secrets redaction. | A log routing system (like Fluentd/Logstash), file logger, metrics exporter, or complex log management server. |
| **Execution Context** | Designed for batch execution environments like Airflow tasks, ETL scripts, and containerized Docker runtimes. | Suitable for high-throughput, low-latency, real-time web servers or async microservices. |

---

## Comparison with Standard Setup

How this package compares to a standard DIY setup:

| Feature / Criteria | Standard Setup (`requests` + `logging` + `psycopg`) | `dehelpers` |
|:---|:---|:---|
| **Secret Leakage Protection** | Manual / None. Secrets easily print to stdout or appear in exception tracebacks. | **Automatic & Deep Recursive:** Redacts predefined secrets from nested metadata, logs, and query parameters. |
| **Retry & Jitter Strategy** | Manual loops or boilerplate `urllib3` retry configurations. | **Out-of-the-box resilience:** Exponential backoff with random jitter and clock-based `total_timeout` limit. |
| **Pagination Handling** | Custom pagination loop logic required for every API endpoint. | **Next-link strategy Protocol:** Yields individual items transparently and safely with validation. |
| **Connection Safety** | Connection leaks or transaction rollback failures if block managers are missed. | **Context-managed Session:** Engine-pooled with pre-ping checks, pool timeout, and auto-rollback. |
| **Dependency Footprint** | Heavy setup if installing frameworks like Loguru, Structlog, or heavy database utilities. | **Ultra-lightweight:** Base dependencies are minimal. Pandas is entirely optional and lazy-loaded. |

---

## Roadmap & What's Next

| Phase | Feature / Expansion | Target Use Case | Status |
|:---|:---|:---|:---|
| **v1.0** | Core Resilient HTTP, Postgres Pool, Redacted Logger | Personal ETL scripts & Airflow workflows | **Released** |
| **v1.1** | Cursor-based Pagination (`CursorPagination`) | Handling APIs that use cursor-based cursors | *Planned* |
| **v1.2** | Async Client Support (`AsyncResilientClient`) | High-throughput concurrent API extraction pipelines | *Planned* |
| **v1.3** | Parquet / Arrow Ingestion Support | High-performance bulk column-based ingestion | *Planned* |
| **v2.0** | Schema Validation Layer (`pydantic` integration) | Ingestion payload sanitization and schema contracts | *Conceptual* |

---

## Install

```bash
# Core (HTTP + DB + logging)
pip install dehelpers

# With Pandas DataFrame support
pip install dehelpers[dataframe]

# Development (tests)
pip install dehelpers[dev,dataframe]
```

Requires Python ≥ 3.10.

---

## Quickstart

### Resilient HTTP Client

```python
from dehelpers import ResilientClient, RetryPolicy

# Custom policy: 5 retries, retry POST with opt-in
policy = RetryPolicy(max_retries=5, retry_non_idempotent=True)
client = ResilientClient(retry_policy=policy)

resp = client.get("https://api.example.com/data")
print(resp.json())

# Paginate through all items
for item in client.paginate("https://api.example.com/items"):
    process(item)
```

### PostgreSQL Database Helper

```python
from dehelpers import DatabaseManager

# Reads DATABASE_URL from environment by default
with DatabaseManager() as db:
    rows = db.execute(
        "SELECT * FROM users WHERE active = :active",
        {"active": True},
    )
    print(f"Found {len(rows)} active users")

    # Optional: load into a Pandas DataFrame
    df = db.to_dataframe("SELECT * FROM sales WHERE date > :d", {"d": "2026-01-01"})
```

### Structured JSON Logger

```python
from dehelpers import get_logger, LogContext

log = get_logger("my_etl", job_id="daily-sales")

with LogContext(request_id="req-abc"):
    log.info("Fetched data", extra={"row_count": 500})
    # Output: {"timestamp": "...", "level": "INFO", "message": "Fetched data",
    #          "module": "...", "job_id": "daily-sales", "request_id": "req-abc",
    #          "row_count": 500, "error": null}
```

---

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DATABASE_URL` (env var) | — | PostgreSQL connection string (fallback when `dsn` is not passed) |
| `pool_size` | 5 | Persistent connections in the pool |
| `max_overflow` | 2 | Extra connections beyond pool_size |
| `pool_recycle` | 1800 | Seconds before connection recycling |
| `pool_pre_ping` | True | Health-check connections before use |
| `pool_timeout` | 30 | Seconds to wait for a pool connection |

---

## Security

### Automatic Redaction

The logger and API client automatically redact values for these keys in log output:

`password`, `secret`, `token`, `api_key`, `authorization`, `dsn`, `connection_string`, `credential`, `passphrase`, `private_key`, `client_secret`

Matching is **case-insensitive substring** — e.g. `db_password` matches `password`.

You can extend the redaction list:

```python
from dehelpers._redact import redact_dict

result = redact_dict(
    {"my_custom_secret": "value"},
    extra_sensitive_keys=frozenset({"my_custom_secret"}),
)
```

### ⚠️ Never Embed Secrets in URLs

URL query parameter values are redacted, but **path segments are not**. Never construct URLs like:

```
https://api.example.com/v1/token/abc123/data  # BAD — token in path
```

Instead, pass secrets via headers or request body.

---

## Fork Safety (Airflow / Multiprocessing)

If you use `DatabaseManager` in a forked environment (e.g. Airflow workers, `multiprocessing`), you **must** either:

1. Create the `DatabaseManager` **inside each worker process**, or
2. Call `db.dispose()` **before** forking.

SQLAlchemy connection pools are not safe to share across forked processes.

---

## Testing

### Unit tests (no PostgreSQL required)

```bash
pip install -e ".[dev,dataframe]"
pytest -v --tb=short -m "not postgres"
```

### PostgreSQL integration tests

```bash
# Start a local PostgreSQL
docker run -d --name pg-test -e POSTGRES_PASSWORD=test -p 5432:5432 postgres:16

# Run integration tests
DATABASE_URL="postgresql+psycopg://postgres:test@localhost:5432/postgres" \
    pytest -m postgres -v
```

### Coverage

```bash
pytest --cov=dehelpers --cov-report=term-missing -m "not postgres"
```

---

## License

MIT — see [LICENSE](LICENSE).
