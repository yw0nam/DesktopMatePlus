"""
LangGraph Agent Graph Builder.

This module constructs the simplified agent workflow graph:
perceive_environment [OPTIONAL] -> query_memory -> reason_and_plan -> generate_response

Note:
- perceive_environment is optional (VLM integrated in chat model)
- update_memory removed (handled via tools in generate_response)
- Memory operations are now asynchronous via tool binding
"""

from __future__ import annotations

from typing import Optional

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from loguru import logger
from mem0 import Memory

from src.services.agent_service.agent_nodes import AgentNodes
from src.services.agent_service.state import GraphState
from src.services.agent_service.tools.memory.metadata_manager import (
    PostgreSQLVocabularyManager,
)
from src.services.screen_capture_service.screen_capture import ScreenCaptureService
from src.services.vlm_service.service import VLMService


class AgentGraphBuilder:
    """
    Builds the LangGraph agent workflow.

    Simplified workflow for POC:
    START -> perceive_environment [OPTIONAL] -> query_memory -> reason_and_plan ->
    generate_response -> END

    Changes from original design:
    - perceive_environment is optional (only for proactive scenarios)
    - update_memory removed (memory tools bound to LLM in generate_response)
    - Metadata term extraction disabled for simplification
    """

    def __init__(
        self,
        llm: BaseChatModel,
        mem0_client: Memory,
        vocabulary_manager: PostgreSQLVocabularyManager,
        vlm_service: Optional[VLMService] = None,
        screen_capture_service: Optional[ScreenCaptureService] = None,
    ):
        """
        Initialize graph builder with required services.

        Args:
            llm: Language model for reasoning and generation
            mem0_client: Memory client for storage/retrieval
            vocabulary_manager: Manages metadata categories
            vlm_service: Vision-Language Model for screen analysis (optional)
            screen_capture_service: Screen capture utility (optional)
        """
        self.agent_nodes = AgentNodes(
            llm=llm,
            mem0_client=mem0_client,
            vocabulary_manager=vocabulary_manager,
            vlm_service=vlm_service,
            screen_capture_service=screen_capture_service,
        )
        logger.info("AgentGraphBuilder initialized")

    def build(self) -> CompiledStateGraph:
        """
        Build and compile the simplified agent graph.

        Returns:
            CompiledStateGraph: The compiled agent workflow graph
        """
        logger.info("Building simplified agent graph (POC version)...")

        # Create state graph
        builder = StateGraph(GraphState)

        # Add nodes
        builder.add_node("perceive_environment", self.agent_nodes.perceive_environment)
        builder.add_node("query_memory", self.agent_nodes.query_memory)
        builder.add_node("reason_and_plan", self.agent_nodes.reason_and_plan)
        builder.add_node("generate_response", self.agent_nodes.generate_response)
        # Note: update_memory node removed - memory operations handled via tools

        # Define edges (simplified workflow)
        builder.add_edge(START, "perceive_environment")
        builder.add_edge("perceive_environment", "query_memory")
        builder.add_edge("query_memory", "reason_and_plan")
        builder.add_edge("reason_and_plan", "generate_response")
        builder.add_edge("generate_response", END)  # Direct to END (no update_memory)

        # Compile with checkpointer for conversation state
        checkpointer = MemorySaver()
        graph = builder.compile(checkpointer=checkpointer)

        logger.info("Simplified agent graph built successfully")
        return graph


def create_agent_graph(
    llm: BaseChatModel,
    mem0_client: Memory,
    vocabulary_manager: PostgreSQLVocabularyManager,
    vlm_service: Optional[VLMService] = None,
    screen_capture_service: Optional[ScreenCaptureService] = None,
) -> CompiledStateGraph:
    """
    Convenience function to create an agent graph.

    Args:
        llm: Language model for reasoning and generation
        mem0_client: Memory client for storage/retrieval
        vocabulary_manager: Manages metadata categories
        vlm_service: Vision-Language Model for screen analysis (optional)
        screen_capture_service: Screen capture utility (optional)

    Returns:
        CompiledStateGraph: The compiled agent workflow graph
    """
    builder = AgentGraphBuilder(
        llm=llm,
        mem0_client=mem0_client,
        vocabulary_manager=vocabulary_manager,
        vlm_service=vlm_service,
        screen_capture_service=screen_capture_service,
    )
    return builder.build()
