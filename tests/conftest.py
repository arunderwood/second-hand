"""Pytest fixtures for second-hand tests."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from second_hand.config import Settings
from second_hand.main import app, get_rdns
from second_hand.services.rdns import ReverseDNSService


@pytest.fixture(autouse=True)
def offline_rdns() -> Generator[None, None, None]:
    """Keep every test off a real resolver.

    Reverse DNS resolves private addresses, so without this the route tests
    query whatever LAN they run on.
    """
    app.dependency_overrides[get_rdns] = lambda: ReverseDNSService(None)
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_rdns, None)


@pytest.fixture
def settings() -> Settings:
    """Provide test settings instance."""
    return Settings()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Provide test client for FastAPI app."""
    with TestClient(app) as c:
        yield c
