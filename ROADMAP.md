# Roadmap

> **Status**: Actively maintained. Planned features are subject to change based on real-world usage and community feedback.

`dehelpers` is intentionally small. The goal is not to become a framework, but to remain a focused, production-hardened toolkit for the repetitive infrastructure behind data engineering pipelines.

---

## v0.2.x — Incremental Improvements

- [ ] **Async HTTP support**: Optional `aiohttp`-based `AsyncResilientClient` for pipelines that benefit from concurrent API calls.
- [ ] **Connection string builder**: A helper to construct `DATABASE_URL` from individual components (`host`, `port`, `dbname`, etc.) with validation.
- [ ] **Retry event hooks**: Callback support on retry attempts (e.g., for metrics emission or custom logging).
- [ ] **Configurable redaction placeholder**: Allow users to customize the `***REDACTED***` replacement string.
- [ ] **Health check endpoint helper**: A lightweight function to verify database connectivity and API reachability for use in container health probes.

## v0.3.x — Extended Utilities

- [ ] **Schema validation**: Optional Pydantic integration for validating API response shapes before database insertion.
- [ ] **Batch insert helper**: A `DatabaseManager.bulk_insert()` method using SQLAlchemy's `insert().values()` for high-throughput ingestion.
- [ ] **Rate limiter**: Token-bucket or sliding-window rate limiting for API clients that enforce request quotas.
- [ ] **MkDocs documentation site**: Publish the existing `docs/` as a searchable, themed documentation site via GitHub Pages.

---

## Design Principles (unchanged)

These principles guide what gets added and what gets rejected:

1. **Small is better.** Every new feature must justify its weight.
2. **Wrap, don't replace.** We build on top of `requests`, `SQLAlchemy`, and `logging` — never reimplementing them.
3. **Opinionated defaults, full override.** Sensible defaults out of the box, but every parameter is configurable.
4. **No magic.** Users should be able to read the source in under an hour.

---

## How to Influence the Roadmap

- Open an [issue](https://github.com/shard-c6/dehelpers/issues) with the `enhancement` label.
- Upvote (👍) existing feature requests to signal demand.
- Submit a PR — contributions are welcome for any roadmap item.
