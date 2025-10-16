"""Test that all core dependencies are properly installed and importable."""

import sys


def test_fastapi_stack():
    """Test FastAPI and related packages."""
    import fastapi
    import uvicorn
    import pydantic
    from pydantic import BaseModel
    from pydantic_settings import BaseSettings

    assert fastapi.__version__ >= "0.115.0"
    assert uvicorn is not None
    assert pydantic.__version__ >= "2.10.0"
    assert BaseModel is not None
    assert BaseSettings is not None
    print("✓ FastAPI stack imported successfully")


def test_langgraph_stack():
    """Test LangGraph and LangChain packages."""
    import langgraph
    import langchain
    from langchain_core.messages import HumanMessage, AIMessage
    from langchain_openai import ChatOpenAI
    from langgraph.graph import StateGraph

    assert langgraph is not None
    assert langchain is not None
    assert HumanMessage is not None
    assert AIMessage is not None
    assert ChatOpenAI is not None
    assert StateGraph is not None
    print("✓ LangGraph/LangChain stack imported successfully")


def test_memory_management():
    """Test memory management packages."""
    import mem0
    from mem0 import Memory

    assert mem0 is not None
    assert Memory is not None
    print("✓ Memory management packages imported successfully")


def test_database_clients():
    """Test database and storage clients."""
    import psycopg
    import psycopg2
    from qdrant_client import QdrantClient

    assert psycopg is not None
    assert psycopg2 is not None
    assert QdrantClient is not None
    print("✓ Database clients imported successfully")


def test_screen_capture():
    """Test screen capture libraries."""
    import mss
    from PIL import Image

    assert mss is not None
    assert Image is not None
    print("✓ Screen capture libraries imported successfully")


def test_http_clients():
    """Test HTTP client libraries."""
    import httpx
    import aiohttp
    import openai

    assert httpx is not None
    assert aiohttp is not None
    assert openai is not None
    print("✓ HTTP client libraries imported successfully")


def test_utilities():
    """Test utility packages."""
    import dotenv
    from loguru import logger
    from tenacity import retry, stop_after_attempt

    assert dotenv is not None
    assert logger is not None
    assert retry is not None
    assert stop_after_attempt is not None
    print("✓ Utility packages imported successfully")


def test_python_version():
    """Test Python version meets requirements."""
    assert sys.version_info >= (3, 11), f"Python {sys.version} is below minimum 3.11"
    print(f"✓ Python version {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} meets requirements")


def test_all_imports():
    """Run all dependency tests."""
    print("\n" + "=" * 60)
    print("Testing Core Dependencies Installation")
    print("=" * 60 + "\n")

    test_python_version()
    test_fastapi_stack()
    test_langgraph_stack()
    test_memory_management()
    test_database_clients()
    test_screen_capture()
    test_http_clients()
    test_utilities()

    print("\n" + "=" * 60)
    print("✅ All core dependencies are properly installed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    test_all_imports()
