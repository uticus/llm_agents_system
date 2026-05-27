"""Shared pytest fixtures.

Unit tests must not make real network calls to LLM providers. Use the provided
fixtures (or your own mocks) to stub the provider boundary.
"""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Directory holding recorded traces and other test fixtures."""
    return FIXTURES_DIR
