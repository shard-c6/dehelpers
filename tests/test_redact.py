"""Tests for dehelpers._redact."""

from __future__ import annotations

from dehelpers._redact import (
    DEFAULT_SENSITIVE_KEYS,
    REDACTED,
    redact_dict,
    redact_url,
)


# ---------------------------------------------------------------------------
# redact_dict
# ---------------------------------------------------------------------------
class TestRedactDict:
    def test_exact_key_match(self):
        result = redact_dict({"password": "hunter2"})
        assert result["password"] == REDACTED

    def test_substring_match(self):
        result = redact_dict({"db_password": "hunter2"})
        assert result["db_password"] == REDACTED

    def test_case_insensitive(self):
        result = redact_dict({"API_KEY": "abc-123"})
        assert result["API_KEY"] == REDACTED

    def test_nested_dict(self):
        data = {"config": {"client_secret": "s3cr3t", "host": "localhost"}}
        result = redact_dict(data)
        assert result["config"]["client_secret"] == REDACTED
        assert result["config"]["host"] == "localhost"

    def test_deeply_nested(self):
        data = {"a": {"b": {"c": {"token": "xyz"}}}}
        result = redact_dict(data)
        assert result["a"]["b"]["c"]["token"] == REDACTED

    def test_non_sensitive_untouched(self):
        data = {"username": "alice", "host": "db.example.com", "port": 5432}
        result = redact_dict(data)
        assert result == data

    def test_original_not_mutated(self):
        data = {"password": "hunter2"}
        _ = redact_dict(data)
        assert data["password"] == "hunter2"

    def test_extra_sensitive_keys(self):
        data = {"custom_field": "value123"}
        result = redact_dict(data, extra_sensitive_keys=frozenset({"custom_field"}))
        assert result["custom_field"] == REDACTED

    def test_custom_override_keys(self):
        """When sensitive_keys is overridden, only those are matched."""
        data = {"password": "ok", "my_key": "secret"}
        result = redact_dict(data, sensitive_keys=frozenset({"my_key"}))
        assert result["password"] == "ok"
        assert result["my_key"] == REDACTED

    def test_list_values_not_redacted(self):
        data = {"tags": ["alpha", "beta"]}
        result = redact_dict(data)
        assert result["tags"] == ["alpha", "beta"]

    def test_extended_keys_from_plan(self):
        """Verify the three extra keys from the approved plan."""
        for key in ("passphrase", "private_key", "client_secret"):
            assert key in DEFAULT_SENSITIVE_KEYS
            result = redact_dict({key: "value"})
            assert result[key] == REDACTED

    def test_empty_dict(self):
        assert redact_dict({}) == {}


# ---------------------------------------------------------------------------
# redact_url
# ---------------------------------------------------------------------------
class TestRedactUrl:
    def test_token_in_query(self):
        url = "https://api.example.com/v1?token=abc123&page=1"
        result = redact_url(url)
        assert "abc123" not in result
        assert f"token={REDACTED}" in result
        assert "page=1" in result

    def test_no_query_params(self):
        url = "https://api.example.com/v1"
        assert redact_url(url) == url

    def test_multiple_sensitive_params(self):
        url = "https://x.com?api_key=k&password=p&name=alice"
        result = redact_url(url)
        assert f"api_key={REDACTED}" in result
        assert f"password={REDACTED}" in result
        assert "name=alice" in result

    def test_case_insensitive_query(self):
        url = "https://x.com?Authorization=bearer-xyz"
        result = redact_url(url)
        assert "bearer-xyz" not in result
