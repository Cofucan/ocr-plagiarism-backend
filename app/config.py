"""
Application configuration using pydantic-settings.
Loads environment variables from .env file.
"""

from pydantic import field_validator
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

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        """Accept common environment labels for DEBUG."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"debug", "dev", "development"}:
                return True
        return value

    # Database settings
    DATABASE_URL: str = "sqlite:///./plagiarism.db"

    # Plagiarism detection thresholds (0.0 to 1.0)
    PLAGIARISM_THRESHOLD_HIGH: float = 0.8  # >= 80% = High Probability of Plagiarism
    PLAGIARISM_THRESHOLD_MODERATE: float = 0.4  # >= 40% = Moderate Similarity

    # Number of top matches to return
    TOP_MATCHES_COUNT: int = 3

    # Similarity scoring weights. These should add up to 1.0.
    TFIDF_WEIGHT: float = 0.60
    FUZZY_WEIGHT: float = 0.20
    PHRASE_WEIGHT: float = 0.20

    # Limit how much OCR correction can raise a document score.
    OCR_MAX_SCORE_BOOST: float = 0.15

    # Chunk/evidence settings
    CHUNK_SENTENCE_COUNT: int = 2
    SUSPICIOUS_CHUNK_THRESHOLD: float = 0.55
    MAX_SUSPICIOUS_CHUNKS: int = 5
    MAX_MATCHED_PHRASES: int = 8

    # Fuzzy OCR correction settings
    FUZZY_CORRECTION_THRESHOLD: int = 88

    # CORS settings (for Android app access)
    CORS_ORIGINS: list[str] = ["*"]


# Global settings instance
settings = Settings()
