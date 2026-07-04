# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.4] - 2026-07-05

### Added
- **CI**: Lint job with `ruff` and `mypy`; Codecov coverage upload and badge.
- **Community**: GitHub Issue Templates (bug report, feature request), Pull Request Template.
- **Security**: `SECURITY.md` with responsible disclosure policy and scope definition.
- **Roadmap**: `ROADMAP.md` with planned features for v0.2 and v0.3.
- **Citation**: `CITATION.cff` for GitHub's "Cite this repository" feature.
- **Code Quality**: `.pre-commit-config.yaml` with `ruff`, `mypy`, and hygiene hooks.

### Changed
- **README**: Added Codecov badge, testing summary, Code Style section, Maintenance & Support statement.
- **CONTRIBUTING**: Expanded with pre-commit setup, code style table, and first-time contributor guidance.
- **pyproject.toml**: Added `ruff`, `mypy`, `pre-commit` to dev dependencies; added `[tool.ruff]` and `[tool.mypy]` configs.

---

## [0.1.3] - 2026-07-04

### Changed
- **Documentation**: Finalized icon replacement and successfully deployed to PyPI.

---

## [0.1.1] - 2026-07-04

### Changed
- **Documentation**: Professionalized README with visual assets (logo, architecture diagram), quickstart guide, and expanded PyPI metadata.
- **Repository**: Re-organized documentation into dedicated `docs/` folder with complete API Reference and runnable examples.

---

## [0.1.0] - 2026-07-03

### Added
- **`ResilientClient`**: Robust HTTP client with bounded retries, exponential backoff, random jitter, and a wall-clock-based `total_timeout` limit.
- **`DatabaseManager`**: Context-managed PostgreSQL-first connection pooling using SQLAlchemy, featuring pre-ping connection checks, pool timeouts, and lazy Pandas DataFrame integration.
- **`get_logger`**: Structured JSON formatter on top of standard `logging` with recursive dictionaries and URL parameter redaction for sensitive keys (e.g. passwords, tokens, private keys).
- **`LogContext`**: ContextVar-based context manager for injecting `job_id` and `request_id` fields across log records.
- **`NextLinkPagination`**: Type-validated paginator strategy yielding item-by-item records.
- **PEP 561 compliance**: Shipped `py.typed` inline type marker for downstream autocompletion and static type checkers.
- **CI Workflows**: Configured GHA CI matrix for Python 3.10 through 3.13, and OIDC Trusted Publishing to PyPI.
