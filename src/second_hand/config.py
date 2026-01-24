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
