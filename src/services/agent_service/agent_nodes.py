"""
LangGraph Agent Nodes for Desktop Assistant.

This module implements the core agent nodes:
- perceive_environment: [OPTIONAL] Capture and analyze screen context (for proactive scenarios)
- query_memory: Retrieve relevant memories
- reason_and_plan: Plan actions based on context
- generate_response: Generate text response with integrated memory tools

Note: VLM is now integrated directly into the chat model, so perceive_environment
is only used for proactive screen analysis scenarios.
Memory updates are handled asynchronously through tools in generate_response.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from loguru import logger
from mem0 import Memory

from src.services.agent_service.state import Configuration, GraphState
from src.services.agent_service.tools.memory import AddMemoryTool, SearchMemoryTool
from src.services.agent_service.tools.memory.metadata_manager import (
    PostgreSQLVocabularyManager,
)
from src.services.agent_service.utils.message_util import trim_messages
from src.services.screen_capture_service.screen_capture import ScreenCaptureService
from src.services.vlm_service.service import VLMService


def _resolve_configuration(config: Optional[RunnableConfig]) -> Configuration:
    """Resolve configuration from RunnableConfig."""
    raw_config: Dict[str, Any] = {}
    if config and "configurable" in config:
        raw_config = dict(config["configurable"])  # type: ignore[arg-type]
    return Configuration.model_validate(raw_config)


class AgentNodes:
    """
    Container for all agent node functions.

    This class provides the five core nodes for the LangGraph agent:
    1. perceive_environment - Captures screen and analyzes visual context
    2. query_memory - Retrieves relevant memories from mem0
    3. reason_and_plan - Creates action plan based on context
    4. generate_response - Generates final response
    5. update_memory - Stores new information in memory
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
        Initialize agent nodes with required services.

        Args:
            llm: Language model for reasoning and generation
            mem0_client: Memory client for storage/retrieval
            vocabulary_manager: Manages metadata categories
            vlm_service: Vision-Language Model for screen analysis
            screen_capture_service: Screen capture utility
        """
        self.llm = llm
        self.mem0_client = mem0_client
        self.vocabulary_manager = vocabulary_manager
        self.vlm_service = vlm_service
        self.screen_capture_service = screen_capture_service
        logger.info("AgentNodes initialized")

    async def perceive_environment(
        self, state: GraphState, config: RunnableConfig
    ) -> GraphState:
        """
        Node 1: Perceive Environment [OPTIONAL]

        This node is now OPTIONAL and only used for proactive screen analysis scenarios.
        VLM is integrated directly into the chat model for user queries with images.

        Use cases:
        - Proactive screen monitoring (agent initiates conversation about screen)
        - Scheduled screen analysis without user query
        - Screen context pre-loading before user interaction

        For normal user queries with screen sharing, VLM is handled in the chat model directly.

        Args:
            state: Current graph state
            config: Runtime configuration

        Returns:
            Updated state with visual_context
        """
        conf = _resolve_configuration(config)
        logger.info("Node: perceive_environment - Starting")

        visual_context = None

        # Only capture screen if explicitly requested and services are available
        if (
            conf.capture_screen
            and self.screen_capture_service is not None
            and self.vlm_service is not None
        ):
            try:
                # Capture primary screen
                screenshot_bytes = self.screen_capture_service.capture_primary_screen()
                logger.debug(f"Screen captured: {len(screenshot_bytes)} bytes")

                # Analyze with VLM
                screen_description = self.vlm_service.generate_response(
                    image=screenshot_bytes,
                    prompt="Describe what you see on the screen. Focus on key elements, applications, and any relevant context.",
                )
                visual_context = screen_description
                logger.info(f"Visual context generated: {screen_description[:100]}...")

            except Exception as e:
                logger.error(f"Failed to capture/analyze screen: {e}")
                visual_context = f"[Screen capture failed: {str(e)}]"

        return {
            "visual_context": visual_context,
            "user_id": conf.user_id,
        }

    async def query_memory(
        self, state: GraphState, config: RunnableConfig
    ) -> GraphState:
        """
        Node 2: Query Memory

        Retrieves relevant memories based on user message and context.

        Note: Metadata term extraction is disabled for POC simplification.
        This feature will be added after v1.0.

        Args:
            state: Current graph state
            config: Runtime configuration

        Returns:
            Updated state with relevant_memories
        """
        conf = _resolve_configuration(config)
        logger.info("Node: query_memory - Starting")

        # Extract user's latest message as query
        user_messages = [
            m.content for m in state.get("messages", []) if isinstance(m, HumanMessage)
        ]
        query = user_messages[-1] if user_messages else ""

        # Search memories
        search_tool = SearchMemoryTool(
            mem0_client=self.mem0_client,
            user_id=conf.user_id,
            agent_id=conf.agent_id,
            run_id=conf.thread_id,
            vocabulary_manager=self.vocabulary_manager,
        )

        relevant_memories: List[Dict[str, Any]] = []
        try:
            results_json = search_tool._run(query=query, limit=5)
            logger.info(f"Memory search executed Result {results_json}")
            if results_json:
                relevant_memories = json.loads(results_json)
                logger.info(f"Retrieved {len(relevant_memories)} relevant memories")
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            relevant_memories = []

        return {
            "relevant_memories": relevant_memories,
        }

    async def reason_and_plan(
        self, state: GraphState, config: RunnableConfig
    ) -> GraphState:
        """
        Node 3: Reason and Plan

        Analyzes context and creates action plan.
        Updates state with action_plan.

        Args:
            state: Current graph state
            config: Runtime configuration

        Returns:
            Updated state with action_plan
        """
        logger.info("Node: reason_and_plan - Starting")

        # Build context for reasoning
        context_parts = []

        logger.debug(f"State for reasoning: {state}, type: {type(state)}")

        if state["visual_context"]:
            context_parts.append(f"Screen Context:\n{state['visual_context']}")
        logger.debug("visual_context passed")

        if state["relevant_memories"]:
            context_parts.append(f"Relevant Memories:\n{state['relevant_memories']}")
        logger.debug("relevant_memories passed")

        # Get latest user message
        user_messages = [
            m.content for m in state.get("messages", []) if isinstance(m, HumanMessage)
        ]
        user_query = user_messages[-1] if user_messages else ""

        # Create reasoning prompt
        reasoning_prompt = f"""You are Natsume, a helpful desktop assistant. Analyze the context and create an action plan.

User Query: {user_query}

{chr(10).join(context_parts)}

Based on this information, create a brief action plan. Consider:
1. What information is most relevant?
2. What should be the focus of the response?
3. Should any new information be remembered?

Provide a concise action plan (2-3 sentences)."""

        try:
            # Use LLM for reasoning
            response = await self.llm.ainvoke([HumanMessage(content=reasoning_prompt)])
            action_plan = (
                response.content if hasattr(response, "content") else str(response)
            )
            logger.info(f"Action plan created: {action_plan[:100]}...")
        except Exception as e:
            logger.error(f"Reasoning failed: {e}")
            action_plan = "Provide helpful response based on available context."

        return {"action_plan": action_plan}

    async def generate_response(
        self, state: GraphState, config: RunnableConfig
    ) -> GraphState:
        """
        Node 4: Generate Response

        Generates final response based on all context.

        Memory tools (search_memory, add_memory) are bound to the LLM,
        allowing the agent to dynamically search and add memories during response generation.
        This approach avoids the overhead of synchronous memory updates.

        Args:
            state: Current graph state
            config: Runtime configuration

        Returns:
            Updated state with response message
        """
        logger.info("Node: generate_response - Starting")

        # Build comprehensive context
        system_message_parts = [
            "You are Natsume, a helpful and personable desktop assistant.",
            "You are the maid and secretary of the user.",
            "You can use search_memory to find relevant information and add_memory to store important facts.",
        ]
        conf = _resolve_configuration(config)

        logger.debug(f"state for response generation: {state}, type: {type(state)}")

        if state["action_plan"] != "":
            system_message_parts.append(f"Action Plan: {state['action_plan']}")

        if state["relevant_memories"]:
            system_message_parts.append(
                f"Relevant memories about the user:\n{state['relevant_memories']}"
            )

        system_message = SystemMessage(content="\n\n".join(system_message_parts))

        # Prepare messages for LLM
        logger.debug(f"State for response generation: {state}, type: {type(state)}")
        logger.debug(f"system_message content: {system_message.content[:200]}...")
        previous_messages = trim_messages(state.get("messages", []))
        messages_for_llm = [system_message] + list(previous_messages)

        # Bind memory tools to LLM for dynamic memory operations
        search_tool = SearchMemoryTool(
            mem0_client=self.mem0_client,
            user_id=conf.user_id,
            agent_id=conf.agent_id,
            run_id=conf.thread_id,
            vocabulary_manager=self.vocabulary_manager,
        )
        add_tool = AddMemoryTool(
            mem0_client=self.mem0_client,
            user_id=conf.user_id,
            agent_id=conf.agent_id,
            run_id=conf.thread_id,
            vocabulary_manager=self.vocabulary_manager,
        )

        try:
            # Bind tools and generate response
            llm_with_tools = self.llm.bind_tools([search_tool, add_tool])
            response = await llm_with_tools.ainvoke(messages_for_llm)
            response_content = (
                response.content if hasattr(response, "content") else str(response)
            )
            logger.info(f"Response generated: {response_content[:100]}...")

            return {"messages": [response]}

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            error_response = "I apologize, but I encountered an error generating a response. Please try again."
            return {"messages": [AIMessage(content=error_response)]}

    async def update_memory(
        self, state: GraphState, config: RunnableConfig
    ) -> GraphState:
        """
        Node 5: Update Memory [DEPRECATED]

        This node is DEPRECATED and should not be used in the main workflow.
        Memory updates are now handled asynchronously through tools bound to the LLM
        in generate_response node to avoid synchronous overhead.

        The agent can now:
        - Search memories dynamically during response generation (search_memory tool)
        - Add memories on-the-fly when needed (add_memory tool)

        This approach provides better performance and more natural memory management.

        Args:
            state: Current graph state
            config: Runtime configuration

        Returns:
            Empty dict (no state changes)
        """
        logger.warning(
            "update_memory node called but is deprecated. Memory updates should be handled via tools in generate_response."
        )
        return {}
