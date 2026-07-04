# Migrating to dehelpers v0.2.0

Version 0.2.0 introduces a major architectural shift to `dehelpers`, focusing on modularity, modern HTTP stacks, and high-throughput data operations. 

While the core philosophy remains the same, several breaking changes were necessary to move away from the monolithic v0.1.x design.

## 1. Modular Installation (Extras)

In v0.1.x, `dehelpers` installed `requests`, `sqlalchemy`, and `psycopg` by default. 

In v0.2.0, dependencies are opt-in. You must specify which parts of the library you intend to use.

**Old (v0.1.x):**
```bash
pip install dehelpers
```

**New (v0.2.0):**
```bash
# For HTTP client only
pip install "dehelpers[http]"

# For database tools only
pip install "dehelpers[db]"

# For database + pandas output
pip install "dehelpers[db,dataframe]"

# For everything
pip install "dehelpers[all]"
```

If you attempt to use a component without its required dependencies, `dehelpers` will raise a clear `ImportError` guiding you to the correct installation command.

## 2. HTTP Client: `requests` -> `httpx`

The `ResilientClient` has been completely rewritten to use `httpx` and `tenacity`. This brings asynchronous support and much more robust retry mechanics, but requires minor syntax updates.

### Async Support
You can now use `AsyncResilientClient` for asynchronous workloads:

```python
from dehelpers import AsyncResilientClient

async with AsyncResilientClient() as client:
    resp = await client.get("https://api.example.com")
```

### Retry Configuration
The `RetryPolicy` is now a configuration object for `tenacity` rather than a custom backoff implementation. 

**Old (v0.1.x):**
```python
from dehelpers import RetryPolicy, ResilientClient

# max_retries
policy = RetryPolicy(max_retries=3)
```

**New (v0.2.0):**
```python
from dehelpers import RetryPolicy, ResilientClient

# max_attempts (includes the initial request)
policy = RetryPolicy(max_attempts=4) 
```

### Response Objects
Because `ResilientClient` now wraps `httpx.Client` instead of `requests.Session`, it returns `httpx.Response` objects instead of `requests.Response`. 

For basic usage (`resp.status_code`, `resp.json()`), the API is identical. However, advanced attributes (like `resp.request` vs `resp.url`) will follow `httpx` conventions.

## 3. Database Manager Updates

The `DatabaseManager` API is fully backwards-compatible for existing methods (`execute`, `fetch_one`, `session`, `to_dataframe`), provided you install the `[db]` extra.

However, v0.2.0 adds several high-throughput bulk operations. If you previously wrote custom looping logic to insert data, consider migrating to these built-in methods:

* **`bulk_insert`**: Batch insert lists of dictionaries using SQLAlchemy.
* **`copy_from_file`**: High-speed bulk load from CSV/TSV directly via PostgreSQL `COPY`.
* **`from_dataframe`**: Write Pandas DataFrames directly to the database.

See the `README.md` for examples of these new features.
