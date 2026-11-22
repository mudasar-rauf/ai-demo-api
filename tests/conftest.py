from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import TaskStore, get_store


@pytest.fixture
def store() -> TaskStore:
    """A fresh, empty store for each test."""
    return TaskStore()


@pytest.fixture
def client(store: TaskStore) -> Iterator[TestClient]:
    """A client whose requests use this test's store."""
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
