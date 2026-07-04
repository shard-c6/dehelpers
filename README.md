<p align="center">
  <img src="https://raw.githubusercontent.com/shard-c6/dehelpers/main/docs/images/logo.png" alt="dehelpers logo" width="400">
</p>

<p align="center">
  <em>Lightweight, production-hardened Python utilities for data engineering pipelines.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/dehelpers/"><img src="https://img.shields.io/pypi/v/dehelpers.svg?color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/dehelpers/"><img src="https://img.shields.io/pypi/pyversions/dehelpers.svg" alt="Python versions"></a>
  <a href="https://github.com/shard-c6/dehelpers/actions/workflows/ci.yml"><img src="https://github.com/shard-c6/dehelpers/actions/workflows/ci.yml/badge.svg" alt="CI Status"></a>
  <a href="https://codecov.io/gh/shard-c6/dehelpers"><img src="https://codecov.io/gh/shard-c6/dehelpers/branch/main/graph/badge.svg" alt="Coverage"></a>
  <a href="https://github.com/shard-c6/dehelpers/blob/main/LICENSE"><img src="https://img.shields.io/github/license/shard-c6/dehelpers.svg" alt="License"></a>
  <a href="https://pypi.org/project/dehelpers/"><img src="https://img.shields.io/pypi/dm/dehelpers.svg" alt="Downloads"></a>
</p>

---

## What It Does

- 🌐 **Resilient HTTP client** for ETL pipelines with bounded retries and exponential backoff.
- 🗄️ **PostgreSQL helper** with safe pooling, sessions, and auto-rollback.
- 📝 **Structured JSON logging** with automatic deep secret redaction.

> **~60 tests · ~94% coverage · CI on Python 3.10–3.13 · Linted with ruff · Type-checked with mypy**

---

## Quickstart

```bash
pip install dehelpers
```

A complete pipeline in under 15 lines:

```python
from dehelpers import ResilientClient, DatabaseManager, get_logger

log = get_logger("my_pipeline", job_id="daily-sync")
client = ResilientClient()

# Connects automatically via DATABASE_URL env var
with DatabaseManager() as db, client:
    users = client.get("https://jsonplaceholder.typicode.com/users").json()
    log.info("Fetched users", extra={"count": len(users)})

    with db.session() as session:
        for user in users:
            session.execute(
                "INSERT INTO users (id, name) VALUES (:id, :name) ON CONFLICT DO NOTHING",
                {"id": user["id"], "name": user["name"]}
            )
    log.info("Ingestion complete")
```

---

## Documentation & Links

- 📚 **[Documentation](https://github.com/shard-c6/dehelpers/tree/main/docs)**: Installation, Getting Started, and FAQ
- 📖 **[API Reference](https://github.com/shard-c6/dehelpers/blob/main/docs/api-reference.md)**: Full details on every class and function
- 💡 **[Examples](https://github.com/shard-c6/dehelpers/tree/main/docs/examples)**: Runnable scripts for HTTP, DB, and Logging
- 🗺️ **[Roadmap](ROADMAP.md)**: Planned features for v0.2 and beyond
- 📝 **[Medium Article](https://medium.com/@shardulchogale1983)**: The story behind building this library

---

## Architecture & Flow

![dehelpers architecture](https://raw.githubusercontent.com/shard-c6/dehelpers/main/docs/images/architecture.png)

*(For an interactive version of this diagram, see the [Architecture Docs](https://github.com/shard-c6/dehelpers/blob/main/docs/architecture.md))*

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

## Code Style & Tools

We use automated tooling to enforce consistent code quality:

| Tool | Purpose |
|------|----------|
| [ruff](https://docs.astral.sh/ruff/) | Linting & formatting |
| [mypy](https://mypy.readthedocs.io/) | Static type checking |
| [pre-commit](https://pre-commit.com/) | Runs all checks on `git commit` |

```bash
# Set up after cloning
pip install -e ".[dev,dataframe]"
pre-commit install
```

---

## Developer Resources & Standards

To ensure the library remains production-grade, reliable, and easily maintainable, we enforce the following open-source standards:

*   **[CONTRIBUTING.md](CONTRIBUTING.md):** Guidelines for cloning the fork, setting up local editable environments, running unit tests, and opening PRs.
*   **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md):** Our pledge to foster an inclusive, welcoming, and harassment-free community.
*   **[SECURITY.md](SECURITY.md):** Responsible disclosure policy for reporting vulnerabilities.
*   **[ROADMAP.md](ROADMAP.md):** Planned features and design direction.
*   **[CHANGELOG.md](CHANGELOG.md):** Structured history of features, bugfixes, and breaking changes.
*   **[LICENSE](LICENSE):** Permissive MIT License.

---

## Maintenance & Support

This library is actively maintained by the author for personal and internal data engineering workflows. It is built with production-minded practices — comprehensive tests, CI, type checking, and structured documentation — but it is not a certified enterprise product.

**Release policy:** Semantic-ish versioning (`v0.x.y`) for incremental features and fixes.

Issues, bug reports, and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.
