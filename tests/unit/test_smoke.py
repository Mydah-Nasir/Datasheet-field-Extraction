"""Smoke tests — verify project structure, imports, and critical dependencies.

These tests ensure Phase 0 setup is correct:
- All source packages are importable
- Core dependencies (LangGraph, Gemini SDK, Pydantic, etc.) are installed
- Configuration module loads without errors
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Package import tests
# ---------------------------------------------------------------------------


class TestSourcePackages:
    """Verify all source sub-packages are importable."""

    def test_import_src(self):
        import src  # noqa: F401

    def test_import_domain(self):
        import src.domain  # noqa: F401

    def test_import_document(self):
        import src.document  # noqa: F401

    def test_import_extraction(self):
        import src.extraction  # noqa: F401

    def test_import_graph(self):
        import src.graph  # noqa: F401

    def test_import_persistence(self):
        import src.persistence  # noqa: F401

    def test_import_api(self):
        import src.api  # noqa: F401

    def test_import_config(self):
        from src.config import settings  # noqa: F401


# ---------------------------------------------------------------------------
# Dependency verification tests
# ---------------------------------------------------------------------------


class TestCoreDependencies:
    """Verify critical third-party packages are installed and importable."""

    def test_langgraph_installed(self):
        """LangGraph is the orchestration engine — must be available."""
        import langgraph  # noqa: F401
        from langgraph.graph import StateGraph  # noqa: F401

    def test_langgraph_checkpoint_memory(self):
        """In-memory checkpointer needed for dev/test."""
        from langgraph.checkpoint.memory import MemorySaver  # noqa: F401

    def test_langgraph_types(self):
        """interrupt and Command are critical for HITL."""
        from langgraph.types import Command, interrupt  # noqa: F401

    def test_gemini_sdk_installed(self):
        """Google GenAI SDK — primary OCR/extraction engine."""
        import google.genai  # noqa: F401

    def test_langchain_google_genai_installed(self):
        """LangChain Gemini integration."""
        import langchain_google_genai  # noqa: F401

    def test_pydantic_installed(self):
        """Pydantic for data validation and schema definition."""
        import pydantic  # noqa: F401

    def test_pymupdf_installed(self):
        """PyMuPDF for PDF text extraction and rendering."""
        import pymupdf  # noqa: F401

    def test_fastapi_installed(self):
        """FastAPI for the REST API layer."""
        import fastapi  # noqa: F401

    def test_dotenv_installed(self):
        """python-dotenv for configuration loading."""
        import dotenv  # noqa: F401


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------


class TestConfiguration:
    """Verify the Settings dataclass loads correctly."""

    def test_settings_loads(self):
        from src.config import Settings

        s = Settings()
        assert isinstance(s.GEMINI_MODEL, str)
        assert isinstance(s.ENVIRONMENT, str)
        assert isinstance(s.MAX_UPLOAD_SIZE_MB, int)
        assert isinstance(s.CONFIDENCE_THRESHOLD, float)

    def test_settings_defaults(self, monkeypatch):
        from src.config import Settings

        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        s = Settings()
        assert s.ENVIRONMENT == "development"
        assert s.GEMINI_MODEL == "gemini-2.5-flash"
        assert s.MAX_UPLOAD_SIZE_MB == 50
        assert s.CONFIDENCE_THRESHOLD == 0.7

    def test_project_root_exists(self):
        from src.config import settings

        assert settings.project_root.exists()

    def test_is_not_production_by_default(self):
        from src.config import Settings

        s = Settings()
        assert not s.is_production
