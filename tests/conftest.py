"""Test configuration and fixtures."""

import pytest


@pytest.fixture
def sample_user_id():
    """Return a sample user ID for testing."""
    return "test_user_123"


@pytest.fixture
def sample_thread_id():
    """Return a sample thread ID for testing."""
    return "test_thread_456"
