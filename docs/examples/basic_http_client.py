"""Basic HTTP client usage with dehelpers.

Demonstrates:
  - Default retry policy (3 retries, exponential backoff, jitter)
  - Custom retry policy
  - Context manager usage
  - Error handling with RetryError

Uses the free JSONPlaceholder API — no API key required.
"""

from dehelpers import ResilientClient, RetryError, RetryPolicy

# ---------------------------------------------------------------------------
# 1. Simple GET with default retry policy
# ---------------------------------------------------------------------------
client = ResilientClient()

resp = client.get("https://jsonplaceholder.typicode.com/posts/1")
post = resp.json()
print(f"Fetched post: {post['title']}")

client.close()


# ---------------------------------------------------------------------------
# 2. Custom retry policy
# ---------------------------------------------------------------------------
policy = RetryPolicy(
    max_retries=5,              # 6 total attempts
    backoff_base=0.5,           # Start with 0.5s delay
    backoff_max=10.0,           # Cap delay at 10s
    total_timeout=60.0,         # Give up after 60s total
    retry_non_idempotent=True,  # Also retry POST requests
)

client = ResilientClient(retry_policy=policy)
resp = client.get("https://jsonplaceholder.typicode.com/users")
users = resp.json()
print(f"Fetched {len(users)} users with custom policy")
client.close()


# ---------------------------------------------------------------------------
# 3. Context manager (auto-closes the session)
# ---------------------------------------------------------------------------
with ResilientClient() as client:
    resp = client.get("https://jsonplaceholder.typicode.com/todos", params={"_limit": 5})
    todos = resp.json()
    print(f"Fetched {len(todos)} todos")


# ---------------------------------------------------------------------------
# 4. Handling retry exhaustion
# ---------------------------------------------------------------------------
try:
    with ResilientClient(retry_policy=RetryPolicy(max_retries=1, total_timeout=5)) as client:
        # This URL will return 404 — a non-retryable error, so it raises immediately
        client.get("https://jsonplaceholder.typicode.com/nonexistent")
except RetryError as exc:
    print(f"RetryError: {exc} (last status: {exc.last_status}, attempts: {exc.attempts})")
except Exception as exc:
    print(f"Non-retry error: {type(exc).__name__}: {exc}")
