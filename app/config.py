"""
Application configuration using pydantic-settings.
Loads environment variables from .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application settings
    APP_NAME: str = "OCR Plagiarism Detection API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database settings
    DATABASE_URL: str = "sqlite:///./plagiarism.db"

    # Plagiarism detection thresholds (0.0 to 1.0)
    PLAGIARISM_THRESHOLD_HIGH: float = 0.8  # >= 80% = High Probability of Plagiarism
    PLAGIARISM_THRESHOLD_MODERATE: float = 0.4  # >= 40% = Moderate Similarity

    # Number of top matches to return
    TOP_MATCHES_COUNT: int = 3

    # CORS settings (for Android app access)
    CORS_ORIGINS: list[str] = ["*"]

    # Crossref API settings (official free academic metadata)
    CROSSREF_BASE_URL: str = "https://api.crossref.org"
    CROSSREF_MAILTO: str = "your-email@example.com"
    CROSSREF_TIMEOUT: int = 15
    CROSSREF_MAX_RESULTS: int = 10
    CROSSREF_MAX_KEYWORDS: int = 10
    CROSSREF_MIN_TOKEN_LEN: int = 3
    CROSSREF_SNIPPET_LEN: int = 400


# Global settings instance
settings = Settings()
