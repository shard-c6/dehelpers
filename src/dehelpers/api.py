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
import random
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import requests

from dehelpers._redact import redact_url
from dehelpers.exceptions import PaginationError, RetryError

__all__ = ["RetryPolicy", "NextLinkPagination", "ResilientClient"]

# HTTP methods considered idempotent and therefore safe to retry.
_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


# ---------------------------------------------------------------------------
# Retry Policy
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RetryPolicy:
    """Configuration for retry behaviour.

    Attributes
    ----------
    max_retries:
        Maximum number of *retries* (not total attempts).  Total attempts
        = ``max_retries + 1``.
    backoff_base:
        Base delay in seconds for exponential backoff.
    backoff_max:
        Maximum delay cap in seconds.
    jitter:
        If ``True``, adds random jitter to the delay to prevent
        thundering-herd effects.
    total_timeout:
        Wall-clock cap in seconds measured from the **start of the first
        attempt**.  Retries abort if this is exceeded.
    retryable_statuses:
        HTTP status codes that trigger a retry.
    retry_non_idempotent:
        If ``True``, retries POST/PUT/DELETE.  Default is ``False``
        (only idempotent methods are retried).
    connect_timeout:
        Per-request TCP connect timeout in seconds.
    read_timeout:
        Per-request read timeout in seconds.
    """

    max_retries: int = 3
    backoff_base: float = 1.0
    backoff_max: float = 30.0
    jitter: bool = True
    total_timeout: float = 120.0
    retryable_statuses: frozenset[int] = field(default_factory=lambda: frozenset({429, 500, 502, 503, 504}))
    retry_non_idempotent: bool = False
    connect_timeout: float = 5.0
    read_timeout: float = 30.0


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
class NextLinkPagination:
    """Follows a ``next`` URL key in the JSON response.

    Parameters
    ----------
    next_key:
        Key in the JSON response that contains the next page URL.
    results_key:
        Key in the JSON response that contains the list of items.
    max_pages:
        Safety limit on the number of pages to fetch.
    """

    def __init__(
        self,
        next_key: str = "next",
        results_key: str = "results",
        max_pages: int = 100,
    ) -> None:
        self.next_key = next_key
        self.results_key = results_key
        self.max_pages = max_pages


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class ResilientClient:
    """HTTP client with automatic retries, backoff, and pagination.

    Parameters
    ----------
    retry_policy:
        Retry configuration.  Uses sensible defaults when ``None``.
    logger:
        Logger instance.  A default JSON logger is created when ``None``.
    """

    def __init__(
        self,
        retry_policy: RetryPolicy | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._policy = retry_policy or RetryPolicy()
        self._log = logger or logging.getLogger(__name__)
        self._session = requests.Session()

    # -- Public helpers -----------------------------------------------------

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        """Send a GET request with retry protection."""
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        """Send a POST request with retry protection."""
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> requests.Response:
        """Send a PUT request with retry protection."""
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> requests.Response:
        """Send a DELETE request with retry protection."""
        return self.request("DELETE", url, **kwargs)

    # -- Core request -------------------------------------------------------

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Send an HTTP request with bounded retries and backoff.

        Raises
        ------
        RetryError
            When all retry attempts are exhausted or the total timeout
            is exceeded.  The original exception is preserved as
            ``__cause__``.
        requests.HTTPError
            On non-retryable HTTP errors (e.g. 400, 401, 403, 404).
        """
        policy = self._policy
        method_upper = method.upper()
        can_retry = method_upper in _IDEMPOTENT_METHODS or policy.retry_non_idempotent

        timeout_tuple = kwargs.pop("timeout", (policy.connect_timeout, policy.read_timeout))

        safe_url = redact_url(url)
        start = time.monotonic()
        last_exception: Exception | None = None
        last_status: int | None = None

        for attempt in range(policy.max_retries + 1):
            # Total-timeout guard.
            elapsed = time.monotonic() - start
            if attempt > 0 and elapsed >= policy.total_timeout:
                raise RetryError(
                    f"Total timeout ({policy.total_timeout}s) exceeded after "
                    f"{attempt} attempt(s) for {method_upper} {safe_url}",
                    last_status=last_status,
                    attempts=attempt,
                ) from last_exception

            try:
                resp = self._session.request(method_upper, url, timeout=timeout_tuple, **kwargs)
                last_status = resp.status_code

                self._log.info(
                    "HTTP %s %s -> %d (attempt %d/%d)",
                    method_upper,
                    safe_url,
                    resp.status_code,
                    attempt + 1,
                    policy.max_retries + 1,
                )

                # Success — return immediately.
                if resp.status_code < 400:
                    return resp

                # Retryable status?
                if can_retry and resp.status_code in policy.retryable_statuses and attempt < policy.max_retries:
                    delay = self._compute_delay(attempt, resp)
                    self._log.warning(
                        "Retryable %d for %s %s — sleeping %.2fs",
                        resp.status_code,
                        method_upper,
                        safe_url,
                        delay,
                    )
                    time.sleep(delay)
                    continue

                # Non-retryable HTTP error — raise immediately.
                resp.raise_for_status()

            except requests.exceptions.HTTPError as exc:
                # If the status is in retryable_statuses but we ran out of retries,
                # wrap it in a RetryError.  Otherwise (like 400, 401, 404), raise it immediately.
                if last_status in policy.retryable_statuses:
                    raise RetryError(
                        f"All {policy.max_retries + 1} attempts exhausted for "
                        f"{method_upper} {safe_url} (last status: {last_status})",
                        last_status=last_status,
                        attempts=attempt + 1,
                    ) from exc
                raise exc
            except requests.RequestException as exc:
                last_exception = exc
                if can_retry and attempt < policy.max_retries:
                    delay = self._compute_delay(attempt)
                    self._log.warning(
                        "Connection error for %s %s (attempt %d/%d) — %s — sleeping %.2fs",
                        method_upper,
                        safe_url,
                        attempt + 1,
                        policy.max_retries + 1,
                        type(exc).__name__,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise RetryError(
                    f"Request failed after {attempt + 1} attempt(s) for {method_upper} {safe_url}: {exc}",
                    last_status=last_status,
                    attempts=attempt + 1,
                ) from exc

        # All retries exhausted with an HTTP error status.
        raise RetryError(
            f"All {policy.max_retries + 1} attempts exhausted for "
            f"{method_upper} {safe_url} (last status: {last_status})",
            last_status=last_status,
            attempts=policy.max_retries + 1,
        ) from last_exception

    # -- Pagination ---------------------------------------------------------

    def paginate(
        self,
        url: str,
        pagination: NextLinkPagination | None = None,
        **kwargs: Any,
    ) -> Iterator[dict]:
        """Yield individual items across paginated responses.

        Parameters
        ----------
        url:
            Initial page URL.
        pagination:
            Pagination strategy.  Defaults to :class:`NextLinkPagination`.
        **kwargs:
            Extra keyword arguments forwarded to each GET request.

        Yields
        ------
        dict
            Individual items from each page.

        Raises
        ------
        PaginationError
            On any failure.  ``PaginationError.collected_items``
            contains items fetched before the failure.
        """
        pag = pagination or NextLinkPagination()
        collected: list[dict] = []
        current_url: str | None = url

        for page_num in range(1, pag.max_pages + 1):
            if current_url is None:
                return

            try:
                resp = self.get(current_url, **kwargs)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                raise PaginationError(
                    f"Failed on page {page_num}: {exc}",
                    collected_items=collected,
                    cause=exc,
                ) from exc

            items = data.get(pag.results_key, [])
            if not items:
                return

            collected.extend(items)
            yield from items

            # Validate the 'next' field.
            next_val = data.get(pag.next_key)
            if next_val is None:
                return
            if not isinstance(next_val, str):
                raise PaginationError(
                    f"Expected '{pag.next_key}' to be a string URL or None, "
                    f"got {type(next_val).__name__}: {next_val!r}",
                    collected_items=collected,
                )
            current_url = next_val

        self._log.warning("Reached max_pages limit (%d)", pag.max_pages)

    # -- Internal -----------------------------------------------------------

    def _compute_delay(
        self,
        attempt: int,
        response: requests.Response | None = None,
    ) -> float:
        """Calculate backoff delay for the given attempt.

        Respects ``Retry-After`` header on 429 responses when available.
        """
        policy = self._policy

        # Honour Retry-After header if present (429 responses).
        if response is not None and response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    return max(0.0, float(retry_after))
                except (ValueError, TypeError):
                    pass  # Fall through to normal backoff.

        delay: float = min(policy.backoff_base * (2**attempt), policy.backoff_max)
        if policy.jitter:
            delay += random.uniform(0, delay * 0.25)  # noqa: S311
        return delay

    # -- Cleanup ------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying requests session."""
        self._session.close()

    def __enter__(self) -> ResilientClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
