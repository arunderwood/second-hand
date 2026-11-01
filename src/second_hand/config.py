"""Configuration management for second-hand."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings are optional and have sensible defaults for development.
    Environment variables use the SECOND_HAND_ prefix.
    """

    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000

    # UI Enhancement settings
    refresh_interval: int = 30  # Dashboard auto-refresh interval in seconds

    # chronyd address: "host", "host:port", or a Unix socket path. The command
    # port is chrony's read-only channel; the Unix socket is its privileged
    # control channel.
    chrony_address: str = "127.0.0.1:323"

    # Root of the TrueType fonts installed by the Debian font packages; see
    # second_hand.fonts for the files served from it.
    fonts_dir: Path = Path("/usr/share/fonts/truetype")

    # Security headers
    # HSTS is only meaningful over TLS, so it is disabled by default. Set a
    # non-zero max-age (e.g. 31536000) when the app is served over HTTPS,
    # either directly or behind a TLS-terminating reverse proxy.
    hsts_max_age: int = 0
    hsts_include_subdomains: bool = True

    model_config = SettingsConfigDict(env_prefix="SECOND_HAND_")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is within valid range."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    @field_validator("hsts_max_age")
    @classmethod
    def validate_hsts_max_age(cls, v: int) -> int:
        """Validate HSTS max-age is non-negative."""
        if v < 0:
            raise ValueError("HSTS max-age must be non-negative")
        return v


@lru_cache
def get_settings() -> Settings:
    """Get the process-wide settings, read from the environment once.

    Tests that change ``SECOND_HAND_*`` variables must call
    ``get_settings.cache_clear()`` for the change to be seen.
    """
    return Settings()
