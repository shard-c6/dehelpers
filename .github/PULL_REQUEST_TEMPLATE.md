## Summary

<!-- One-sentence description of what this PR does. -->

## Motivation

<!-- Why is this change needed? Link to any related issue(s). -->

Closes #<!-- issue number -->

## Changes Made

<!-- Brief list of what was changed/added/removed. -->

-

## Checklist

Please confirm the following before requesting review:

- [ ] **Tests**: I have added or updated tests that cover the changes.
- [ ] **Type Hints**: All new public functions and parameters have type annotations.
- [ ] **Documentation**: I have updated docstrings, README, or `docs/` as needed.
- [ ] **Changelog**: I have added a note to `CHANGELOG.md` under `[Unreleased]`.
- [ ] **Lint & Format**: I have run `pre-commit run --all-files` and all checks pass.

## How to Test

<!-- Steps for the reviewer to verify the change works. -->

```bash
pytest -v --tb=short -m "not postgres"
```

---

*See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full contribution workflow.*
