"""Smoke test for the Streamlit UI."""


def test_streamlit_app_imports():
    """Verify that the Streamlit app can be imported without syntax errors."""
    try:
        import app  # noqa: F401
    except ImportError as e:
        import pytest

        pytest.fail(f"Failed to import app: {e}")

