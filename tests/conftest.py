"""Shared pytest fixtures for the ModDB tracker test suite."""

import pytest

import storage as storage_mod


@pytest.fixture()
def db():
    """In-memory SQLite Storage, fresh per test."""
    s = storage_mod.Storage(":memory:")
    yield s
    s.close()
