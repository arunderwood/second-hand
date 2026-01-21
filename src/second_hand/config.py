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
    dns_timeout: float = 3.0  # DNS lookup timeout in seconds
    dns_cache_ttl: int = 3600  # DNS cache TTL in seconds (1 hour)
    dns_cache_maxsize: int = 1024  # Maximum DNS cache entries
    dns_max_concurrent: int = 10  # Maximum concurrent DNS lookups

    model_config = {"env_prefix": "SECOND_HAND_"}

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is within valid range."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()
