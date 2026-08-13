"""Shared pytest fixtures for the Mechanical Datasheet Extraction project."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    """Return the absolute path to the project root directory."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def fixtures_dir(project_root: Path) -> Path:
    """Return the path to the test fixtures directory."""
    path = project_root / "tests" / "fixtures"
    path.mkdir(parents=True, exist_ok=True)
    return path
