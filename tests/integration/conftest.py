"""Pytest configuration for integration tests."""

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register integration marker."""
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test requiring chronyd"
    )


@pytest.fixture(scope="session")
def chrony_socket_path() -> str:
    """Get the chrony socket path for integration tests.

    Returns the default path or the value from CHRONY_SOCKET environment variable.
    """
    return os.environ.get("CHRONY_SOCKET", "/run/chrony/chronyd.sock")


@pytest.fixture(scope="session")
def check_chronyd_running(chrony_socket_path: str) -> bool:
    """Check if chronyd is running and accessible via pychrony.

    Returns True if chronyd is accessible.
    Fails the test if chronyd is not running or pychrony can't connect.

    Integration tests MUST run against a real chronyd server. If connection
    fails, the test should fail (not skip) to ensure CI catches configuration
    issues with the Docker test environment.
    """
    from pychrony import (
        ChronyConnection,
        ChronyConnectionError,
        ChronyLibraryError,
        ChronyPermissionError,
    )

    try:
        with ChronyConnection(chrony_socket_path) as conn:
            # Actually try to get data to verify full connectivity
            conn.get_tracking()
        return True
    except (
        ChronyConnectionError,
        ChronyLibraryError,
        ChronyPermissionError,
        OSError,
    ) as e:
        pytest.fail(
            f"chronyd not accessible at {chrony_socket_path}: {e}\n"
            "Integration tests require a running chronyd. "
            "Run via: docker compose -f docker/docker-compose.test.yml run --rm test-integration"
        )
