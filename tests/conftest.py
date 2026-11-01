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

    Route tests drive the real lifespan, which configures a resolver from the
    host's resolv.conf, and reverse DNS queries private addresses by design.
    Without this the suite resolves whatever LAN it happens to run on, so its
    results would differ between machines. A test that wants hostnames
    overrides this with a fake of its own.
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
