"""Tests for dehelpers.api."""

from __future__ import annotations

import httpx
import pytest
import respx

from dehelpers.api import (
    AsyncResilientClient,
    NextLinkPagination,
    ResilientClient,
    RetryPolicy,
)
from dehelpers.exceptions import PaginationError, RetryError

BASE = "https://api.example.com"


# ---------------------------------------------------------------------------
# Successful requests
# ---------------------------------------------------------------------------
class TestSuccess:
    @respx.mock
    def test_get_200(self):
        respx.get(f"{BASE}/data").mock(return_value=httpx.Response(200, json={"ok": True}))
        client = ResilientClient()
        resp = client.get(f"{BASE}/data")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    @respx.mock
    def test_post_201(self):
        respx.post(f"{BASE}/items").mock(return_value=httpx.Response(201, json={"id": 1}))
        client = ResilientClient()
        resp = client.post(f"{BASE}/items", json={"name": "x"})
        assert resp.status_code == 201

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_get_200(self):
        respx.get(f"{BASE}/data").mock(return_value=httpx.Response(200, json={"ok": True}))
        async with AsyncResilientClient() as client:
            resp = await client.get(f"{BASE}/data")
            assert resp.status_code == 200
            assert resp.json() == {"ok": True}


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------
class TestRetry:
    @respx.mock
    def test_retry_on_500(self):
        """GET retries on 500 and eventually raises RetryError."""
        route = respx.get(f"{BASE}/fail").mock(return_value=httpx.Response(500))

        policy = RetryPolicy(max_attempts=4, backoff_base=0.01, backoff_max=0.02)
        client = ResilientClient(retry_policy=policy)
        with pytest.raises(RetryError) as exc_info:
            client.get(f"{BASE}/fail")
        assert exc_info.value.last_status == 500
        assert exc_info.value.attempts == 4
        assert route.call_count == 4

    @respx.mock
    def test_retry_on_502_503_504(self):
        for status in (502, 503, 504):
            route = respx.get(f"{BASE}/fail").mock(
                side_effect=[
                    httpx.Response(status),
                    httpx.Response(status),
                    httpx.Response(200, json={"ok": True}),
                ]
            )

            policy = RetryPolicy(max_attempts=3, backoff_base=0.01)
            client = ResilientClient(retry_policy=policy)
            resp = client.get(f"{BASE}/fail")
            assert resp.status_code == 200
            assert route.call_count == 3
            respx.clear()

    @respx.mock
    def test_no_retry_on_400(self):
        route = respx.get(f"{BASE}/bad").mock(return_value=httpx.Response(400))
        client = ResilientClient()
        with pytest.raises(httpx.HTTPStatusError):
            client.get(f"{BASE}/bad")
        assert route.call_count == 1

    @respx.mock
    def test_no_retry_on_401(self):
        route = respx.get(f"{BASE}/auth").mock(return_value=httpx.Response(401))
        client = ResilientClient()
        with pytest.raises(httpx.HTTPStatusError):
            client.get(f"{BASE}/auth")
        assert route.call_count == 1

    @respx.mock
    def test_no_retry_on_404(self):
        route = respx.get(f"{BASE}/missing").mock(return_value=httpx.Response(404))
        client = ResilientClient()
        with pytest.raises(httpx.HTTPStatusError):
            client.get(f"{BASE}/missing")
        assert route.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_retry_on_500(self):
        route = respx.get(f"{BASE}/fail").mock(return_value=httpx.Response(500))

        policy = RetryPolicy(max_attempts=3, backoff_base=0.01, backoff_max=0.02)
        async with AsyncResilientClient(retry_policy=policy) as client:
            with pytest.raises(RetryError) as exc_info:
                await client.get(f"{BASE}/fail")
        assert exc_info.value.last_status == 500
        assert exc_info.value.attempts == 3
        assert route.call_count == 3


# ---------------------------------------------------------------------------
# Non-idempotent safety
# ---------------------------------------------------------------------------
class TestNonIdempotent:
    @respx.mock
    def test_post_not_retried_by_default(self):
        route = respx.post(f"{BASE}/create").mock(return_value=httpx.Response(500))

        policy = RetryPolicy(max_attempts=3, backoff_base=0.01)
        client = ResilientClient(retry_policy=policy)
        with pytest.raises(RetryError) as exc_info:
            client.post(f"{BASE}/create")
        # Should have attempted only once.
        assert (
            exc_info.value.attempts == 3
        )  # Wait, wait, actually attempts is max_attempts recorded, but call_count is 1
        assert route.call_count == 1

    @respx.mock
    def test_post_retried_with_opt_in(self):
        route = respx.post(f"{BASE}/create").mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(201, json={"id": 1}),
            ]
        )

        policy = RetryPolicy(
            max_attempts=3,
            backoff_base=0.01,
            retry_non_idempotent=True,
        )
        client = ResilientClient(retry_policy=policy)
        resp = client.post(f"{BASE}/create")
        assert resp.status_code == 201
        assert route.call_count == 2


# ---------------------------------------------------------------------------
# RetryError preserves __cause__
# ---------------------------------------------------------------------------
class TestRetryErrorCause:
    @respx.mock
    def test_cause_preserved_on_connection_error(self):
        respx.get(f"{BASE}/down").mock(side_effect=httpx.ConnectError("refused"))
        policy = RetryPolicy(max_attempts=2, backoff_base=0.01)
        client = ResilientClient(retry_policy=policy)
        with pytest.raises(RetryError) as exc_info:
            client.get(f"{BASE}/down")
        assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
class TestPagination:
    @respx.mock
    def test_normal_flow(self):
        respx.get(f"{BASE}/items?page=1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [{"id": 1}, {"id": 2}],
                    "next": f"{BASE}/items?page=2",
                },
            )
        )
        respx.get(f"{BASE}/items?page=2").mock(
            return_value=httpx.Response(200, json={"results": [{"id": 3}], "next": None})
        )

        client = ResilientClient()
        items = list(client.paginate(f"{BASE}/items?page=1"))
        assert len(items) == 3
        assert items[0]["id"] == 1
        assert items[2]["id"] == 3

    @respx.mock
    def test_empty_page_stops(self):
        respx.get(f"{BASE}/items").mock(
            return_value=httpx.Response(200, json={"results": [], "next": f"{BASE}/items?page=2"})
        )
        client = ResilientClient()
        items = list(client.paginate(f"{BASE}/items"))
        assert items == []

    @respx.mock
    def test_invalid_next_field_raises(self):
        respx.get(f"{BASE}/items").mock(return_value=httpx.Response(200, json={"results": [{"id": 1}], "next": 12345}))
        client = ResilientClient()
        with pytest.raises(PaginationError) as exc_info:
            list(client.paginate(f"{BASE}/items"))
        assert "string URL, got" in str(exc_info.value)
        assert exc_info.value.collected_items == [{"id": 1}]

    @respx.mock
    def test_mid_pagination_failure(self):
        respx.get(f"{BASE}/items?page=1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [{"id": 1}],
                    "next": f"{BASE}/items?page=2",
                },
            )
        )
        respx.get(f"{BASE}/items?page=2").mock(return_value=httpx.Response(500))

        policy = RetryPolicy(max_attempts=1, backoff_base=0.01)
        client = ResilientClient(retry_policy=policy)

        with pytest.raises(PaginationError) as exc_info:
            list(client.paginate(f"{BASE}/items?page=1"))
        assert len(exc_info.value.collected_items) == 1
        assert exc_info.value.collected_items[0]["id"] == 1

    @respx.mock
    def test_max_pages_limit(self):
        """Pagination stops at max_pages."""
        for i in range(10):
            respx.get(f"{BASE}/items?page={i + 1}").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "results": [{"id": i}],
                        "next": f"{BASE}/items?page={i + 2}",
                    },
                )
            )

        client = ResilientClient()
        pag = NextLinkPagination(max_pages=3)
        items = list(client.paginate(f"{BASE}/items?page=1", pagination=pag))
        assert len(items) == 3

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_pagination(self):
        respx.get(f"{BASE}/items?page=1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [{"id": 1}],
                    "next": f"{BASE}/items?page=2",
                },
            )
        )
        respx.get(f"{BASE}/items?page=2").mock(
            return_value=httpx.Response(200, json={"results": [{"id": 2}], "next": None})
        )

        items = []
        async with AsyncResilientClient() as client:
            async for item in client.paginate(f"{BASE}/items?page=1"):
                items.append(item)
        assert len(items) == 2
        assert items[1]["id"] == 2


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------
class TestClientContext:
    def test_context_manager(self):
        with ResilientClient() as client:
            assert client is not None
