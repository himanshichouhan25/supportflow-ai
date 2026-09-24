"""
config.py — Application configuration.

Loads settings from the .env file using pydantic-settings.
Secrets are never hardcoded here; they come from environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from the .env file."""

    # PostgreSQL connection URL (postgresql+psycopg://...)
    DATABASE_URL: str

    # Gemini API key — optional; agents degrade gracefully when absent
    GEMINI_API_KEY: str | None = None

    model_config = SettingsConfigDict(
        # Look for a .env file in the project root (one level above backend/)
        env_file=".env",
        env_file_encoding="utf-8",
        # Ignore any extra variables in .env that we haven't declared
        extra="ignore",
    )


# Single shared instance — import this everywhere instead of re-creating it.
settings = Settings()
