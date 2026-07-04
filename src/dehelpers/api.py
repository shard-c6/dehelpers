"""Resilient HTTP client with bounded retries, exponential backoff,
jitter, total-timeout guard, and next-link pagination.

Usage::

    from dehelpers import ResilientClient, RetryPolicy

    client = ResilientClient()
    resp = client.get("https://api.example.com/data")

    # Paginate through all items
    for item in client.paginate("https://api.example.com/items"):
        process(item)
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential_jitter,
)

from dehelpers._redact import redact_url
from dehelpers.exceptions import PaginationError, RetryError

__all__ = ["RetryPolicy", "NextLinkPagination", "ResilientClient", "AsyncResilientClient"]

_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclass(frozen=True)
class RetryPolicy:
    """Configuration for retry behaviour mapped to tenacity."""
    max_attempts: int = 4
    backoff_base: float = 1.0
    backoff_max: float = 30.0
    total_timeout: float = 120.0
    retryable_statuses: frozenset[int] = field(default_factory=lambda: frozenset({429, 500, 502, 503, 504}))
    retry_non_idempotent: bool = False
    connect_timeout: float = 5.0
    read_timeout: float = 30.0

    def build_tenacity_kwargs(self, method: str) -> dict[str, Any]:
        can_retry = method.upper() in _IDEMPOTENT_METHODS or self.retry_non_idempotent
        if not can_retry:
            return {"stop": stop_after_attempt(1), "reraise": True}

        return {
            "stop": stop_after_attempt(self.max_attempts) | stop_after_delay(self.total_timeout),
            "wait": wait_exponential_jitter(initial=self.backoff_base, max=self.backoff_max),
            "retry": retry_if_exception(
                lambda exc: isinstance(exc, httpx.RequestError)
                or (isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in self.retryable_statuses)
            ),
            "reraise": True,
        }


class NextLinkPagination:
    def __init__(
        self,
        next_key: str = "next",
        results_key: str = "results",
        max_pages: int = 100,
    ) -> None:
        self.next_key = next_key
        self.results_key = results_key
        self.max_pages = max_pages


def _log_before_sleep(logger: logging.Logger, safe_url: str, method: str) -> Any:
    def callback(retry_state: RetryCallState) -> None:
        if retry_state.outcome and retry_state.outcome.failed:
            exc = retry_state.outcome.exception()
            status = getattr(exc.response, "status_code", "N/A") if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
            logger.warning(
                "Retryable error %s for %s %s (attempt %d). Sleeping...",
                status, method, safe_url, retry_state.attempt_number
            )
    return callback


class ResilientClient:
    def __init__(
        self,
        retry_policy: RetryPolicy | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._policy = retry_policy or RetryPolicy()
        self._log = logger or logging.getLogger(__name__)
        self._client = httpx.Client(
            timeout=httpx.Timeout(
                self._policy.read_timeout,
                connect=self._policy.connect_timeout
            )
        )

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        safe_url = redact_url(url)
        method_upper = method.upper()
        tenacity_kwargs = self._policy.build_tenacity_kwargs(method_upper)
        tenacity_kwargs["before_sleep"] = _log_before_sleep(self._log, safe_url, method_upper)

        try:
            for attempt in Retrying(**tenacity_kwargs):
                with attempt:
                    self._log.info("HTTP %s %s (attempt %d)", method_upper, safe_url, attempt.retry_state.attempt_number)
                    resp = self._client.request(method_upper, url, **kwargs)
                    resp.raise_for_status()
                    return resp
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            # Only wrap if it was retryable or failed on connect
            if isinstance(exc, httpx.RequestError) or (isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in self._policy.retryable_statuses):
                raise RetryError(
                    f"Request failed for {method_upper} {safe_url}: {exc}",
                    last_status=last_status,
                    attempts=self._policy.max_attempts,
                ) from exc
            raise exc

        raise RuntimeError("Unreachable")

    def paginate(
        self,
        url: str,
        pagination: NextLinkPagination | None = None,
        **kwargs: Any,
    ) -> Iterator[dict]:
        pag = pagination or NextLinkPagination()
        collected: list[dict] = []
        current_url: str | None = url

        for page_num in range(1, pag.max_pages + 1):
            if current_url is None:
                return

            try:
                resp = self.get(current_url, **kwargs)
                data = resp.json()
            except Exception as exc:
                raise PaginationError(f"Failed on page {page_num}: {exc}", collected_items=collected, cause=exc) from exc

            items = data.get(pag.results_key, [])
            if not items:
                return

            collected.extend(items)
            yield from items

            next_val = data.get(pag.next_key)
            if next_val is None:
                return
            if not isinstance(next_val, str):
                raise PaginationError(f"Expected '{pag.next_key}' to be a string URL, got {type(next_val).__name__}", collected_items=collected)
            current_url = next_val

        self._log.warning("Reached max_pages limit (%d)", pag.max_pages)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ResilientClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class AsyncResilientClient:
    def __init__(
        self,
        retry_policy: RetryPolicy | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._policy = retry_policy or RetryPolicy()
        self._log = logger or logging.getLogger(__name__)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                self._policy.read_timeout,
                connect=self._policy.connect_timeout
            )
        )

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", url, **kwargs)

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        safe_url = redact_url(url)
        method_upper = method.upper()
        tenacity_kwargs = self._policy.build_tenacity_kwargs(method_upper)
        tenacity_kwargs["before_sleep"] = _log_before_sleep(self._log, safe_url, method_upper)

        try:
            async for attempt in AsyncRetrying(**tenacity_kwargs):
                with attempt:
                    self._log.info("HTTP %s %s (attempt %d)", method_upper, safe_url, attempt.retry_state.attempt_number)
                    resp = await self._client.request(method_upper, url, **kwargs)
                    resp.raise_for_status()
                    return resp
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            if isinstance(exc, httpx.RequestError) or (isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in self._policy.retryable_statuses):
                raise RetryError(
                    f"Request failed for {method_upper} {safe_url}: {exc}",
                    last_status=last_status,
                    attempts=self._policy.max_attempts,
                ) from exc
            raise exc

        raise RuntimeError("Unreachable")

    async def paginate(
        self,
        url: str,
        pagination: NextLinkPagination | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict]:
        pag = pagination or NextLinkPagination()
        collected: list[dict] = []
        current_url: str | None = url

        for page_num in range(1, pag.max_pages + 1):
            if current_url is None:
                return

            try:
                resp = await self.get(current_url, **kwargs)
                data = resp.json()
            except Exception as exc:
                raise PaginationError(f"Failed on page {page_num}: {exc}", collected_items=collected, cause=exc) from exc

            items = data.get(pag.results_key, [])
            if not items:
                return

            collected.extend(items)
            for item in items:
                yield item

            next_val = data.get(pag.next_key)
            if next_val is None:
                return
            if not isinstance(next_val, str):
                raise PaginationError(f"Expected '{pag.next_key}' to be a string URL, got {type(next_val).__name__}", collected_items=collected)
            current_url = next_val

        self._log.warning("Reached max_pages limit (%d)", pag.max_pages)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsyncResilientClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()
