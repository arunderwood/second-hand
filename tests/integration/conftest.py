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
    """Check if chronyd is running and accessible.

    Returns True if chronyd is accessible, False otherwise.
    Skips the test if chronyd is not running.
    """
    import socket

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.settimeout(1.0)
        sock.connect(chrony_socket_path)
        sock.close()
        return True
    except OSError:
        pytest.skip("chronyd not running or socket not accessible")
        return False
