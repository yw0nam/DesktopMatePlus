"""
Unit tests for LangGraph agent nodes.

Tests each node with mock inputs and validates state transitions.
"""

import json

# Mock environment variables before any imports
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

os.environ.setdefault("EMB_MODEL_NAME", "test-model")
os.environ.setdefault("EMB_BASE_URL", "http://test")
os.environ.setdefault("EMB_API_KEY", "test-key")
os.environ.setdefault("LLM_BASE_URL", "http://test")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("QDRANT_URL", "http://test")
os.environ.setdefault("QDRANT_COLLECTION_NAME", "test")
os.environ.setdefault("NEO4J_URI", "bolt://test")
os.environ.setdefault("NEO4J_USER", "test")
os.environ.setdefault("NEO4J_PASSWORD", "test")

from src.services.agent_service.agent_nodes import AgentNodes
from src.services.agent_service.state import GraphState


@pytest.fixture
def mock_llm():
    """Create mock LLM."""
    llm = AsyncMock()
    llm.ainvoke = AsyncMock()
    return llm


@pytest.fixture
def mock_mem0_client():
    """Create mock mem0 client."""
    return MagicMock()


@pytest.fixture
def mock_vocabulary_manager():
    """Create mock vocabulary manager."""
    manager = MagicMock()
    manager.get_all_terms.return_value = ["preferences", "work_context", "personal"]
    return manager


@pytest.fixture
def mock_vlm_service():
    """Create mock VLM service."""
    vlm = MagicMock()
    vlm.generate_response.return_value = "Screen shows a text editor with Python code."
    return vlm


@pytest.fixture
def mock_screen_capture_service():
    """Create mock screen capture service."""
    capture = MagicMock()
    capture.capture_primary_screen.return_value = b"fake_image_bytes"
    return capture


@pytest.fixture
def agent_nodes(
    mock_llm,
    mock_mem0_client,
    mock_vocabulary_manager,
    mock_vlm_service,
    mock_screen_capture_service,
):
    """Create AgentNodes instance with mocks."""
    return AgentNodes(
        llm=mock_llm,
        mem0_client=mock_mem0_client,
        vocabulary_manager=mock_vocabulary_manager,
        vlm_service=mock_vlm_service,
        screen_capture_service=mock_screen_capture_service,
    )


@pytest.fixture
def base_state():
    """Create base state for testing."""
    return GraphState(
        messages=[HumanMessage(content="What's on my screen?")],
        visual_context=None,
        action_plan=None,
        user_id="test-user",
        metadata_terms=[],
        relevant_memories=[],
    )


@pytest.fixture
def config():
    """Create test configuration."""
    return {
        "configurable": {
            "user_id": "test-user",
            "agent_id": "test-agent",
            "thread_id": "test-thread",
            "capture_screen": True,
        }
    }


@pytest.mark.asyncio
async def test_perceive_environment_with_screen_capture(
    agent_nodes, base_state, config, mock_screen_capture_service, mock_vlm_service
):
    """Test perceive_environment node with screen capture enabled."""
    # Act
    result = await agent_nodes.perceive_environment(base_state, config)

    # Assert
    assert result["visual_context"] == "Screen shows a text editor with Python code."
    assert result["user_id"] == "test-user"
    mock_screen_capture_service.capture_primary_screen.assert_called_once()
    mock_vlm_service.generate_response.assert_called_once()


@pytest.mark.asyncio
async def test_perceive_environment_without_screen_capture(agent_nodes, base_state):
    """Test perceive_environment node with screen capture disabled."""
    config = {
        "configurable": {
            "user_id": "test-user",
            "agent_id": "test-agent",
            "thread_id": "test-thread",
            "capture_screen": False,
        }
    }

    # Act
    result = await agent_nodes.perceive_environment(base_state, config)

    # Assert
    assert result["visual_context"] is None
    assert result["user_id"] == "test-user"


@pytest.mark.asyncio
async def test_perceive_environment_capture_failure(
    agent_nodes, base_state, config, mock_screen_capture_service
):
    """Test perceive_environment node when screen capture fails."""
    mock_screen_capture_service.capture_primary_screen.side_effect = Exception(
        "Capture failed"
    )

    # Act
    result = await agent_nodes.perceive_environment(base_state, config)

    # Assert
    assert "[Screen capture failed:" in result["visual_context"]


@pytest.mark.asyncio
async def test_query_memory(agent_nodes, base_state, config, mock_vocabulary_manager):
    """Test query_memory node."""
    # Mock search tool
    with patch(
        "src.services.agent_service.agent_nodes.SearchMemoryTool"
    ) as mock_search_tool_class:
        mock_search_tool = MagicMock()
        mock_search_tool._run.return_value = json.dumps(
            [
                {"memory": "User prefers dark mode", "category": "preferences"},
                {"memory": "User is working on Python", "category": "work_context"},
            ]
        )
        mock_search_tool_class.return_value = mock_search_tool

        # Act
        result = await agent_nodes.query_memory(base_state, config)

        # Assert
        assert len(result["relevant_memories"]) == 2
        assert result["relevant_memories"][0]["memory"] == "User prefers dark mode"
        # metadata_terms removed in POC simplification


@pytest.mark.asyncio
async def test_query_memory_with_visual_context(
    agent_nodes, base_state, config, mock_vocabulary_manager
):
    """Test query_memory node (visual context not added to query in POC)."""
    state_with_visual = base_state.copy()
    state_with_visual["visual_context"] = "Screen shows IDE"

    with patch(
        "src.services.agent_service.agent_nodes.SearchMemoryTool"
    ) as mock_search_tool_class:
        mock_search_tool = MagicMock()
        mock_search_tool._run.return_value = json.dumps([])
        mock_search_tool_class.return_value = mock_search_tool

        # Act
        await agent_nodes.query_memory(state_with_visual, config)

        # Assert
        mock_search_tool._run.assert_called_once()
        # In POC, visual context is NOT added to query (VLM integrated in chat model)


@pytest.mark.asyncio
async def test_reason_and_plan(agent_nodes, base_state, config, mock_llm):
    """Test reason_and_plan node."""
    # Setup
    state = base_state.copy()
    state["visual_context"] = "Screen shows code editor"
    state["relevant_memories"] = [{"memory": "User is learning Python"}]

    mock_response = MagicMock()
    mock_response.content = (
        "1. Analyze the code 2. Provide helpful suggestions 3. Remember progress"
    )
    mock_llm.ainvoke.return_value = mock_response

    # Act
    result = await agent_nodes.reason_and_plan(state, config)

    # Assert
    assert "action_plan" in result
    assert "Analyze the code" in result["action_plan"]
    mock_llm.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_reason_and_plan_without_context(
    agent_nodes, base_state, config, mock_llm
):
    """Test reason_and_plan node without additional context."""
    mock_response = MagicMock()
    mock_response.content = "Provide helpful response"
    mock_llm.ainvoke.return_value = mock_response

    # Act
    result = await agent_nodes.reason_and_plan(base_state, config)

    # Assert
    assert "action_plan" in result
    assert result["action_plan"] == "Provide helpful response"


@pytest.mark.asyncio
async def test_generate_response(agent_nodes, base_state, config, mock_llm):
    """Test generate_response node with tool binding."""
    # Setup
    state = base_state.copy()
    state["visual_context"] = "Screen shows Python code"
    state["action_plan"] = "Analyze and help with code"
    state["relevant_memories"] = [{"memory": "User is learning Python"}]

    mock_response = MagicMock()
    mock_response.content = "I can see you're working on Python code. How can I help?"
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke.return_value = mock_response

    # Mock the tool initialization to avoid validation errors
    with (
        patch("src.services.agent_service.agent_nodes.SearchMemoryTool"),
        patch("src.services.agent_service.agent_nodes.AddMemoryTool"),
    ):
        # Act
        result = await agent_nodes.generate_response(state, config)

        # Assert
        assert "messages" in result
        assert len(result["messages"]) == 1
        mock_llm.bind_tools.assert_called_once()
        mock_llm.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_generate_response_error_handling(
    agent_nodes, base_state, config, mock_llm
):
    """Test generate_response node error handling."""
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    mock_llm.ainvoke.side_effect = Exception("LLM failed")

    with (
        patch("src.services.agent_service.agent_nodes.SearchMemoryTool"),
        patch("src.services.agent_service.agent_nodes.AddMemoryTool"),
    ):
        # Act
        result = await agent_nodes.generate_response(base_state, config)

        # Assert
        assert "messages" in result
        assert "error" in result["messages"][0].content.lower()


@pytest.mark.asyncio
async def test_update_memory(agent_nodes, base_state, config, mock_llm):
    """Test update_memory node (now deprecated - returns empty dict)."""
    # Setup
    state = base_state.copy()
    state["messages"] = [
        HumanMessage(content="I prefer using dark mode"),
        AIMessage(content="I'll remember that you prefer dark mode!"),
    ]

    # Act
    result = await agent_nodes.update_memory(state, config)

    # Assert - node is deprecated and returns empty dict
    assert result == {}


@pytest.mark.asyncio
async def test_update_memory_no_facts(agent_nodes, base_state, config, mock_llm):
    """Test update_memory node when no facts to remember."""
    # Setup
    state = base_state.copy()
    state["messages"] = [
        HumanMessage(content="Hello"),
        AIMessage(content="Hi there!"),
    ]

    mock_response = MagicMock()
    mock_response.content = "[]"
    mock_llm.ainvoke.return_value = mock_response

    with patch(
        "src.services.agent_service.agent_nodes.AddMemoryTool"
    ) as mock_add_tool_class:
        mock_add_tool = MagicMock()
        mock_add_tool_class.return_value = mock_add_tool

        # Act
        await agent_nodes.update_memory(state, config)

        # Assert
        mock_add_tool._run.assert_not_called()


@pytest.mark.asyncio
async def test_update_memory_json_parsing_error(
    agent_nodes, base_state, config, mock_llm
):
    """Test update_memory node with JSON parsing error."""
    # Setup
    state = base_state.copy()
    state["messages"] = [HumanMessage(content="Test")]

    mock_response = MagicMock()
    mock_response.content = "Invalid JSON"
    mock_llm.ainvoke.return_value = mock_response

    # Act - should not raise exception
    result = await agent_nodes.update_memory(state, config)

    # Assert
    assert result == {}


@pytest.mark.asyncio
async def test_state_transitions():
    """Test that state transitions work correctly through nodes."""
    # This test validates that the simplified state structure is correct
    initial_state = GraphState(
        messages=[HumanMessage(content="Test")],
        visual_context=None,
        action_plan=None,
        user_id="test-user",
        relevant_memories=[],
    )

    # Simulate state updates through nodes
    state = initial_state.copy()

    # After perceive_environment
    state["visual_context"] = "Screen captured"
    assert state["visual_context"] is not None

    # After query_memory
    state["relevant_memories"] = [{"memory": "test"}]
    # metadata_terms removed in POC
    assert len(state["relevant_memories"]) == 1

    # After reason_and_plan
    state["action_plan"] = "Test plan"
    assert state["action_plan"] is not None

    # After generate_response
    state["messages"].append(AIMessage(content="Response"))
    assert len(state["messages"]) == 2

    # State should maintain all fields
    assert all(
        key in state
        for key in [
            "messages",
            "visual_context",
            "action_plan",
            "user_id",
            "relevant_memories",
        ]
    )
