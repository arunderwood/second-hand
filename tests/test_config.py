"""Tests for configuration management."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from second_hand.config import Settings, get_settings


class TestSettings:
    """Tests for Settings model."""

    def test_default_values(self) -> None:
        """Settings should have sensible defaults."""
        settings = Settings()
        assert settings.debug is False
        assert settings.host == "127.0.0.1"
        assert settings.port == 8000

    def test_debug_mode_from_env(self) -> None:
        """Debug mode should be configurable via environment variable."""
        with patch.dict(os.environ, {"SECOND_HAND_DEBUG": "true"}):
            settings = Settings()
            assert settings.debug is True

    def test_host_from_env(self) -> None:
        """Host should be configurable via environment variable."""
        with patch.dict(os.environ, {"SECOND_HAND_HOST": "0.0.0.0"}):
            settings = Settings()
            assert settings.host == "0.0.0.0"

    def test_port_from_env(self) -> None:
        """Port should be configurable via environment variable."""
        with patch.dict(os.environ, {"SECOND_HAND_PORT": "3000"}):
            settings = Settings()
            assert settings.port == 3000

    def test_invalid_port_too_low(self) -> None:
        """Port 0 should be rejected."""
        with (
            patch.dict(os.environ, {"SECOND_HAND_PORT": "0"}),
            pytest.raises(ValidationError),
        ):
            Settings()

    def test_invalid_port_too_high(self) -> None:
        """Port above 65535 should be rejected."""
        with (
            patch.dict(os.environ, {"SECOND_HAND_PORT": "70000"}),
            pytest.raises(ValidationError),
        ):
            Settings()

    def test_valid_port_boundaries(self) -> None:
        """Port 1 and 65535 should be valid."""
        with patch.dict(os.environ, {"SECOND_HAND_PORT": "1"}):
            settings = Settings()
            assert settings.port == 1

        with patch.dict(os.environ, {"SECOND_HAND_PORT": "65535"}):
            settings = Settings()
            assert settings.port == 65535


class TestGetSettings:
    """Tests for get_settings function."""

    def test_returns_settings_instance(self) -> None:
        """get_settings should return a Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)
