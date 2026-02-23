"""Test environment setup."""


def test_imports():
    """Test that core dependencies can be imported."""
    import fastapi
    import langgraph
    import mem0
    from pydantic import BaseModel

    assert fastapi is not None
    assert langgraph is not None
    assert mem0 is not None
    assert BaseModel is not None


def test_python_version():
    """Test that we're using Python 3.11+."""
    import sys

    assert sys.version_info >= (3, 11), f"Python version {sys.version} is too old"
