"""Shared test fixtures."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


@pytest.fixture()
def env_vars():
    """Context manager fixture to temporarily set environment variables.

    Usage::

        def test_example(env_vars):
            with env_vars(DATABASE_URL="sqlite:///:memory:"):
                ...
    """

    class _EnvVarManager:
        def __call__(self, **kwargs: str):
            return patch.dict(os.environ, kwargs)

    return _EnvVarManager()
