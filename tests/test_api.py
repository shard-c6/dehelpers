"""Tests for de_pipeline_helpers.api."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
import requests
import responses

from de_pipeline_helpers.api import (
    NextLinkPagination,
    ResilientClient,
    RetryPolicy,
)
from de_pipeline_helpers.exceptions import PaginationError, RetryError

BASE = "https://api.example.com"


# ---------------------------------------------------------------------------
# Successful requests
# ---------------------------------------------------------------------------
class TestSuccess:
    @responses.activate
    def test_get_200(self):
        responses.get(f"{BASE}/data", json={"ok": True}, status=200)
        client = ResilientClient()
        resp = client.get(f"{BASE}/data")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    @responses.activate
    def test_post_201(self):
        responses.post(f"{BASE}/items", json={"id": 1}, status=201)
        client = ResilientClient()
        resp = client.post(f"{BASE}/items", json={"name": "x"})
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------
class TestRetry:
    @responses.activate
    def test_retry_on_500(self):
        """GET retries on 500 and eventually raises RetryError."""
        for _ in range(4):
            responses.get(f"{BASE}/fail", status=500)

        policy = RetryPolicy(max_retries=3, backoff_base=0.01, backoff_max=0.02)
        client = ResilientClient(retry_policy=policy)
        with pytest.raises(RetryError) as exc_info:
            client.get(f"{BASE}/fail")
        assert exc_info.value.last_status == 500
        assert exc_info.value.attempts == 4

    @responses.activate
    def test_retry_on_502_503_504(self):
        for status in (502, 503, 504):
            responses.reset()
            for _ in range(2):
                responses.get(f"{BASE}/fail", status=status)
            responses.get(f"{BASE}/fail", json={"ok": True}, status=200)

            policy = RetryPolicy(max_retries=3, backoff_base=0.01)
            client = ResilientClient(retry_policy=policy)
            resp = client.get(f"{BASE}/fail")
            assert resp.status_code == 200

    @responses.activate
    def test_retry_on_429_with_retry_after(self):
        responses.get(
            f"{BASE}/limited",
            status=429,
            headers={"Retry-After": "0.01"},
        )
        responses.get(f"{BASE}/limited", json={"ok": True}, status=200)

        policy = RetryPolicy(max_retries=2, backoff_base=0.01)
        client = ResilientClient(retry_policy=policy)
        resp = client.get(f"{BASE}/limited")
        assert resp.status_code == 200

    @responses.activate
    def test_no_retry_on_400(self):
        responses.get(f"{BASE}/bad", status=400)
        client = ResilientClient()
        with pytest.raises(Exception):  # HTTPError from raise_for_status
            client.get(f"{BASE}/bad")
        # Only one call should have been made.
        assert len(responses.calls) == 1

    @responses.activate
    def test_no_retry_on_401(self):
        responses.get(f"{BASE}/auth", status=401)
        client = ResilientClient()
        with pytest.raises(Exception):
            client.get(f"{BASE}/auth")
        assert len(responses.calls) == 1

    @responses.activate
    def test_no_retry_on_404(self):
        responses.get(f"{BASE}/missing", status=404)
        client = ResilientClient()
        with pytest.raises(Exception):
            client.get(f"{BASE}/missing")
        assert len(responses.calls) == 1


# ---------------------------------------------------------------------------
# Non-idempotent safety
# ---------------------------------------------------------------------------
class TestNonIdempotent:
    @responses.activate
    def test_post_not_retried_by_default(self):
        for _ in range(4):
            responses.post(f"{BASE}/create", status=500)

        policy = RetryPolicy(max_retries=3, backoff_base=0.01)
        client = ResilientClient(retry_policy=policy)
        with pytest.raises(RetryError) as exc_info:
            client.post(f"{BASE}/create")
        # Should have attempted only once.
        assert exc_info.value.attempts == 1

    @responses.activate
    def test_post_retried_with_opt_in(self):
        responses.post(f"{BASE}/create", status=500)
        responses.post(f"{BASE}/create", json={"id": 1}, status=201)

        policy = RetryPolicy(
            max_retries=3,
            backoff_base=0.01,
            retry_non_idempotent=True,
        )
        client = ResilientClient(retry_policy=policy)
        resp = client.post(f"{BASE}/create")
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Backoff timing
# ---------------------------------------------------------------------------
class TestBackoff:
    @responses.activate
    def test_exponential_backoff_called(self):
        for _ in range(3):
            responses.get(f"{BASE}/slow", status=500)
        responses.get(f"{BASE}/slow", json={"ok": True}, status=200)

        policy = RetryPolicy(
            max_retries=3, backoff_base=1.0, backoff_max=10.0, jitter=False
        )
        client = ResilientClient(retry_policy=policy)

        sleep_calls: list[float] = []
        original_sleep = time.sleep

        def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch("de_pipeline_helpers.api.time.sleep", side_effect=mock_sleep):
            resp = client.get(f"{BASE}/slow")

        assert resp.status_code == 200
        # Without jitter: delays should be 1.0, 2.0, 4.0
        assert len(sleep_calls) == 3
        assert sleep_calls[0] == pytest.approx(1.0)
        assert sleep_calls[1] == pytest.approx(2.0)
        assert sleep_calls[2] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# Total timeout
# ---------------------------------------------------------------------------
class TestTotalTimeout:
    @responses.activate
    def test_total_timeout_aborts_retries(self):
        for _ in range(10):
            responses.get(f"{BASE}/timeout", status=500)

        policy = RetryPolicy(
            max_retries=10,
            backoff_base=0.01,
            total_timeout=0.0,  # zero = expire immediately after first attempt
        )
        client = ResilientClient(retry_policy=policy)

        with pytest.raises(RetryError) as exc_info:
            client.get(f"{BASE}/timeout")
        # Should NOT have used all 10 retries.
        assert exc_info.value.attempts < 10


# ---------------------------------------------------------------------------
# RetryError preserves __cause__
# ---------------------------------------------------------------------------
class TestRetryErrorCause:
    @responses.activate
    def test_cause_preserved_on_connection_error(self):
        responses.get(
            f"{BASE}/down",
            body=requests.exceptions.ConnectionError("refused"),
        )
        policy = RetryPolicy(max_retries=0, backoff_base=0.01)
        client = ResilientClient(retry_policy=policy)
        with pytest.raises(RetryError) as exc_info:
            client.get(f"{BASE}/down")
        assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
class TestPagination:
    @responses.activate
    def test_normal_flow(self):
        responses.get(
            f"{BASE}/items?page=1",
            json={
                "results": [{"id": 1}, {"id": 2}],
                "next": f"{BASE}/items?page=2",
            },
        )
        responses.get(
            f"{BASE}/items?page=2",
            json={"results": [{"id": 3}], "next": None},
        )

        client = ResilientClient()
        items = list(client.paginate(f"{BASE}/items?page=1"))
        assert len(items) == 3
        assert items[0]["id"] == 1
        assert items[2]["id"] == 3

    @responses.activate
    def test_empty_page_stops(self):
        responses.get(
            f"{BASE}/items",
            json={"results": [], "next": f"{BASE}/items?page=2"},
        )
        client = ResilientClient()
        items = list(client.paginate(f"{BASE}/items"))
        assert items == []

    @responses.activate
    def test_invalid_next_field_raises(self):
        responses.get(
            f"{BASE}/items",
            json={"results": [{"id": 1}], "next": 12345},
        )
        client = ResilientClient()
        with pytest.raises(PaginationError) as exc_info:
            list(client.paginate(f"{BASE}/items"))
        assert "string URL or None" in str(exc_info.value)
        assert exc_info.value.collected_items == [{"id": 1}]

    @responses.activate
    def test_mid_pagination_failure(self):
        responses.get(
            f"{BASE}/items?page=1",
            json={
                "results": [{"id": 1}],
                "next": f"{BASE}/items?page=2",
            },
        )
        responses.get(f"{BASE}/items?page=2", status=500)

        policy = RetryPolicy(max_retries=0, backoff_base=0.01)
        client = ResilientClient(retry_policy=policy)

        with pytest.raises(PaginationError) as exc_info:
            list(client.paginate(f"{BASE}/items?page=1"))
        assert len(exc_info.value.collected_items) == 1
        assert exc_info.value.collected_items[0]["id"] == 1

    @responses.activate
    def test_max_pages_limit(self):
        """Pagination stops at max_pages."""
        for i in range(10):
            responses.get(
                f"{BASE}/items?page={i + 1}",
                json={
                    "results": [{"id": i}],
                    "next": f"{BASE}/items?page={i + 2}",
                },
            )

        client = ResilientClient()
        pag = NextLinkPagination(max_pages=3)
        items = list(client.paginate(f"{BASE}/items?page=1", pagination=pag))
        assert len(items) == 3


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------
class TestClientContext:
    def test_context_manager(self):
        with ResilientClient() as client:
            assert client is not None
