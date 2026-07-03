"""Shared redaction utilities.

Private module — not part of the public API.  Used by the logger,
API client, and database manager to strip sensitive values before
they reach log output or ``__repr__`` strings.
"""

from __future__ import annotations

import copy
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

DEFAULT_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "authorization",
        "dsn",
        "connection_string",
        "credential",
        "passphrase",
        "private_key",
        "client_secret",
    }
)

REDACTED = "***REDACTED***"


def _is_sensitive(key: str, sensitive_keys: frozenset[str]) -> bool:
    """Return True if *key* contains any sensitive substring (case-insensitive)."""
    key_lower = key.lower()
    return any(s in key_lower for s in sensitive_keys)


def redact_dict(
    d: dict,
    sensitive_keys: frozenset[str] | None = None,
    extra_sensitive_keys: frozenset[str] | None = None,
) -> dict:
    """Deep-clone *d* and replace values whose keys match the sensitive set.

    Matching is **case-insensitive substring** — e.g. a key named
    ``db_password`` matches ``password``.

    Parameters
    ----------
    d:
        The dictionary to redact.  Not mutated.
    sensitive_keys:
        Override the full sensitive-key set.  When ``None``, uses
        :data:`DEFAULT_SENSITIVE_KEYS`.
    extra_sensitive_keys:
        Additional keys to treat as sensitive, merged with *sensitive_keys*.

    Returns
    -------
    dict
        A deep copy of *d* with sensitive values replaced by
        ``'***REDACTED***'``.
    """
    keys = sensitive_keys if sensitive_keys is not None else DEFAULT_SENSITIVE_KEYS
    if extra_sensitive_keys:
        keys = keys | extra_sensitive_keys

    return _redact_recursive(d, keys)


def _redact_recursive(obj: object, sensitive_keys: frozenset[str]) -> object:
    """Recursively redact sensitive keys in nested structures."""
    if isinstance(obj, dict):
        result: dict = {}
        for k, v in obj.items():
            if isinstance(k, str) and _is_sensitive(k, sensitive_keys):
                result[k] = REDACTED
            else:
                result[k] = _redact_recursive(v, sensitive_keys)
        return result
    if isinstance(obj, (list, tuple)):
        redacted = [_redact_recursive(item, sensitive_keys) for item in obj]
        return type(obj)(redacted)
    return copy.deepcopy(obj) if isinstance(obj, (set, frozenset)) else obj


def redact_url(
    url: str,
    sensitive_keys: frozenset[str] | None = None,
) -> str:
    """Return *url* with query-parameter values redacted for sensitive keys.

    Parameters
    ----------
    url:
        The URL to redact.
    sensitive_keys:
        Override the full sensitive-key set.  When ``None``, uses
        :data:`DEFAULT_SENSITIVE_KEYS`.

    Returns
    -------
    str
        The URL with matching query-parameter values replaced by
        ``'***REDACTED***'``.
    """
    keys = sensitive_keys if sensitive_keys is not None else DEFAULT_SENSITIVE_KEYS

    parts = urlsplit(url)
    if not parts.query:
        return url

    params = parse_qs(parts.query, keep_blank_values=True)
    redacted_params: dict[str, list[str]] = {}
    for k, values in params.items():
        if _is_sensitive(k, keys):
            redacted_params[k] = [REDACTED] * len(values)
        else:
            redacted_params[k] = values

    new_query = urlencode(redacted_params, doseq=True, quote_via=lambda s, safe="", encoding=None, errors=None: s)
    return urlunsplit(parts._replace(query=new_query))
