# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | ✅ Yes              |
| < 0.1   | ❌ No               |

Only the latest release on PyPI receives security patches.

---

## Reporting a Vulnerability

If you discover a security vulnerability in `dehelpers`, **please do not open a public issue.**

Instead, report it through one of these channels:

1. **GitHub Security Advisories** (preferred):
   Go to [Security → Advisories → New draft advisory](https://github.com/shard-c6/dehelpers/security/advisories/new) on the repository. This keeps the report private until a fix is available.

2. **Email**:
   Send details to **shardulchogale1983@gmail.com** with the subject line `[SECURITY] dehelpers vulnerability report`.

### What to include

- A description of the vulnerability and its potential impact.
- Steps to reproduce or a minimal proof of concept.
- The version(s) of `dehelpers` and Python you tested against.

### What to expect

- **Acknowledgement** within **3 business days**.
- A fix or mitigation plan within **14 days** for confirmed issues.
- Credit in the release notes (unless you prefer to remain anonymous).

---

## Scope

The following areas are in scope for security reports:

- **Secret redaction bypass**: Any input that causes `redact_dict` or `redact_url` to leak sensitive values.
- **SQL injection**: Any path through `DatabaseManager` that allows unparameterized query execution.
- **Dependency vulnerabilities**: Issues in `requests`, `SQLAlchemy`, or `psycopg` that affect `dehelpers` users.
- **Log injection**: Crafted input that corrupts the structured JSON log output.

---

## Out of Scope

- Vulnerabilities in applications *using* `dehelpers` (e.g., misconfigured `DATABASE_URL`).
- Denial-of-service via intentionally large payloads (this is a library, not a server).
- Issues in development-only dependencies (`pytest`, `ruff`, etc.).
