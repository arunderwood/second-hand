"""Configuration management for second-hand."""

from pydantic import field_validator
from pydantic_settings import BaseSettings


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

    # Security headers
    # HSTS is only meaningful over TLS, so it is disabled by default. Set a
    # non-zero max-age (e.g. 31536000) when the app is served over HTTPS,
    # either directly or behind a TLS-terminating reverse proxy.
    hsts_max_age: int = 0
    hsts_include_subdomains: bool = True

    model_config = {"env_prefix": "SECOND_HAND_"}

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


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()
