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

    @pytest.mark.parametrize("value", ["0", "86401"])
    def test_invalid_refresh_interval(self, value: str) -> None:
        """Refresh intervals setInterval cannot honor should be rejected."""
        with (
            patch.dict(os.environ, {"SECOND_HAND_REFRESH_INTERVAL": value}),
            pytest.raises(ValidationError),
        ):
            Settings()

    def test_valid_refresh_interval_boundaries(self) -> None:
        """Refresh intervals of 1 second and 1 day should be valid."""
        for value in (1, 86400):
            with patch.dict(os.environ, {"SECOND_HAND_REFRESH_INTERVAL": str(value)}):
                assert Settings().refresh_interval == value


class TestClientSettings:
    """The client-visibility settings shared by the dashboard and the reader."""

    def test_defaults(self) -> None:
        """The feature and the per-client table default to on."""
        settings = Settings()
        assert settings.clients_enabled is True
        assert settings.clients_table is True
        assert settings.clients_max_rows == 100
        assert str(settings.clients_snapshot_path) == (
            "/run/second-hand-reader/snapshot.json"
        )
        assert settings.reader_interval == 30

    def test_env_prefix_round_trip(self) -> None:
        """Every client setting is reachable through SECOND_HAND_* variables."""
        env = {
            "SECOND_HAND_CLIENTS_ENABLED": "false",
            "SECOND_HAND_CLIENTS_TABLE": "false",
            "SECOND_HAND_CLIENTS_MAX_ROWS": "250",
            "SECOND_HAND_CLIENTS_SNAPSHOT_PATH": "/tmp/snapshot.json",
            "SECOND_HAND_READER_INTERVAL": "60",
        }
        with patch.dict(os.environ, env):
            settings = Settings()
        assert settings.clients_enabled is False
        assert settings.clients_table is False
        assert settings.clients_max_rows == 250
        assert str(settings.clients_snapshot_path) == "/tmp/snapshot.json"
        assert settings.reader_interval == 60

    @pytest.mark.parametrize("value", ["0", "10001"])
    def test_invalid_max_rows(self, value: str) -> None:
        """Row caps outside 1-10000 are rejected."""
        with (
            patch.dict(os.environ, {"SECOND_HAND_CLIENTS_MAX_ROWS": value}),
            pytest.raises(ValidationError),
        ):
            Settings()

    def test_valid_max_rows_boundaries(self) -> None:
        """Row caps of 1 and 10000 are valid."""
        for value in (1, 10000):
            with patch.dict(os.environ, {"SECOND_HAND_CLIENTS_MAX_ROWS": str(value)}):
                assert Settings().clients_max_rows == value

    def test_reader_interval_floor(self) -> None:
        """Intervals under 10 seconds would poll chronyd too aggressively."""
        with (
            patch.dict(os.environ, {"SECOND_HAND_READER_INTERVAL": "9"}),
            pytest.raises(ValidationError),
        ):
            Settings()
        with patch.dict(os.environ, {"SECOND_HAND_READER_INTERVAL": "10"}):
            assert Settings().reader_interval == 10


class TestGetSettings:
    """Tests for get_settings function."""

    def test_returns_settings_instance(self) -> None:
        """get_settings should return a Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_is_cached(self) -> None:
        """Settings are read from the environment once, not on every call."""
        assert get_settings() is get_settings()
