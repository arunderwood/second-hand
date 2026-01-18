"""Pytest fixtures for second-hand tests."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from second_hand.config import Settings
from second_hand.main import app


@pytest.fixture
def settings() -> Settings:
    """Provide test settings instance."""
    return Settings()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Provide test client for FastAPI app."""
    with TestClient(app) as c:
        yield c
