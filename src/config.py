"""Application configuration loaded from environment variables.

Usage:
    from src.config import settings
    print(settings.GOOGLE_API_KEY)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env file if present (development convenience)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)


@dataclass(frozen=True)
class Settings:
    """Immutable application settings derived from environment variables."""

    # --- Gemini ---
    GEMINI_API_KEY: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
    )
    GEMINI_MODEL: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    # --- Application ---
    ENVIRONMENT: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))

    # Document Ingestion Configuration
    MAX_DOCUMENT_SIZE_MB: int = field(
        default_factory=lambda: int(os.getenv("MAX_DOCUMENT_SIZE_MB", "20"))
    )
    MIN_MEANINGFUL_TEXT_CHARS: int = field(
        default_factory=lambda: int(os.getenv("MIN_MEANINGFUL_TEXT_CHARS", "50"))
    )
    MIN_MEANINGFUL_ALPHANUMERIC_CHARS: int = field(
        default_factory=lambda: int(os.getenv("MIN_MEANINGFUL_ALPHANUMERIC_CHARS", "20"))
    )

    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # --- Document Upload ---
    MAX_UPLOAD_SIZE_MB: int = field(
        default_factory=lambda: int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    )

    # --- Extraction ---
    CONFIDENCE_THRESHOLD: float = field(
        default_factory=lambda: float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
    )

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def project_root(self) -> Path:
        return _PROJECT_ROOT


# Singleton instance — import this throughout the application
settings = Settings()
