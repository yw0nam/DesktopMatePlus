"""Graph construction utilities for the Phase 1 memory-enabled agent."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Sequence, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from mem0 import Memory

from src.configs.mem0_configs import MEM0_CONFIG, VOCABULARY_DB_CONFIG
from src.services.agent_service.llm_factory import LLMFactory
from src.services.agent_service.state import Configuration, OverallState
from src.services.agent_service.text_utils.message_util import trim_messages
from src.services.agent_service.tools.memory import AddMemoryTool, SearchMemoryTool
from src.services.agent_service.tools.memory.metadata_manager import (
    PostgreSQLVocabularyManager,
)

MEMORY_CONTEXT_PROMPT = (
    "You are natsume, who is the maid and secretary of user. You are a helpful assistant that personalises replies using stored memories. "
    "Always look at the provided memories before answering. When the user shares a "
    "durable fact about themselves (name, preferences, biography, commitments), call "
    "the `add_memory` tool with a concise summary. Use the `search_memory` tool when "
    "you need to retrieve additional details beyond what is already attached."
    "Make sure the metadata tags are used appropriately to categorize memories."
)


def _resolve_configuration(config: Optional[RunnableConfig]) -> Configuration:
    raw_config: Dict[str, Any] = {}
    if config and "configurable" in config:
        # config["configurable"] may be a mapping-like object
        raw_config = dict(config["configurable"])  # type: ignore[arg-type]
    # model_validate expects a dict but its stub may be Any; cast to Configuration
    return cast(Configuration, Configuration.model_validate(raw_config))


class MemoryAgentGraphBuilder:
    def __init__(
        self,
        mem0_client: Memory,
        llm: BaseChatModel,
        vocabulary_manager: PostgreSQLVocabularyManager,
        *,
        system_prompt: Optional[str] = None,
    ) -> None:
        self._mem0_client = mem0_client
        self._llm = llm
        self._vocabulary_manager = vocabulary_manager
        self._prompt = SystemMessage(content=(system_prompt or MEMORY_CONTEXT_PROMPT))

    async def build(self) -> CompiledStateGraph:
        """Build compiledStateGraph using the provided components.

        Returns:
            CompiledStateGraph: The constructed state graph.
        """
        checkpointer = InMemorySaver()
        builder = StateGraph(OverallState)
        builder.add_node("load_memories", self._load_memories)
        builder.add_node("agent", self._agent_node)
        builder.add_edge(START, "load_memories")
        builder.add_edge("load_memories", "agent")
        builder.add_edge("agent", END)
        return builder.compile(name="memory-agent", checkpointer=checkpointer)

    def _load_memories(
        self, state: OverallState, config: RunnableConfig
    ) -> OverallState:
        """
        Loads relevant memories and updates the state accordingly before processing the agent node.

        Args:
            state (OverallState): The current state of the overall process.
            config (RunnableConfig): The configuration for the runnable.
        Returns:
            OverallState: The updated state after loading memories.
        """
        conf = _resolve_configuration(config)
        user_messages = [
            m.content for m in state.get("messages", []) if isinstance(m, HumanMessage)
        ]
        query = user_messages[-1] if user_messages else ""
        search_tool = SearchMemoryTool(
            mem0_client=self._mem0_client,
            user_id=conf.user_id,
            agent_id=conf.agent_id,
            run_id=conf.thread_id,
            vocabulary_manager=self._vocabulary_manager,
        )
        results: List[Dict[str, Any]] = []
        try:
            results_json = search_tool._run(query=query, limit=5)
            if results_json:
                results = json.loads(results_json)
        except Exception:  # pragma: no cover - defensive parsing
            results = []

        categories = self._vocabulary_manager.get_all_terms()
        state["metadata_terms"] = categories

        # Build system messages as a list for consistent types
        system_messages: List[SystemMessage] = []
        if categories:
            system_messages.append(
                SystemMessage(
                    content=(
                        "Known metadata categories available for filtering: "
                        f"{', '.join(categories)}\n\n"
                    )
                )
            )

        if results:
            system_messages.append(
                SystemMessage(
                    content=(
                        "Previously saved memories relevant to this user:\n"
                        f"{str(results)}\n\n"
                    )
                )
            )

        previous_messages: Sequence[Any] = state.get("messages", [])
        # Ensure previous_messages is a list before concatenation
        previous_messages = trim_messages(
            previous_messages
        )  # Trim the message histroy to maintain context window
        state["messages"] = list(system_messages) + list(previous_messages)
        return state

    async def _agent_node(
        self, state: OverallState, config: RunnableConfig
    ) -> OverallState:
        """Handles the agent node processing.
        For handling MCP Tools, we need to create agent using async.

        Args:
            state (OverallState): The current state of the overall process.
            config (RunnableConfig): The configuration for the runnable.

        Returns:
            OverallState: The updated state after processing the agent node.
        """
        conf = _resolve_configuration(config)
        add_tool = AddMemoryTool(
            mem0_client=self._mem0_client,
            user_id=conf.user_id,
            agent_id=conf.agent_id,
            run_id=conf.thread_id,
            vocabulary_manager=self._vocabulary_manager,
        )
        search_tool = SearchMemoryTool(
            mem0_client=self._mem0_client,
            user_id=conf.user_id,
            agent_id=conf.agent_id,
            run_id=conf.thread_id,
            vocabulary_manager=self._vocabulary_manager,
        )
        agent = create_react_agent(
            self._llm,
            tools=[search_tool, add_tool],
            prompt=self._prompt,
        )
        agent_messages = state.get("messages", [])
        metadata_terms = state.get("metadata_terms", [])
        if metadata_terms:
            agent_messages = [
                SystemMessage(
                    content=(
                        "You can reference metadata categories when deciding whether "
                        "to apply filters or store new memories. Current categories: "
                        f"{', '.join(metadata_terms)}"
                    )
                )
            ] + agent_messages

        agent_state = await agent.ainvoke({"messages": agent_messages}, config=config)
        return {"messages": agent_state["messages"]}


if __name__ == "__main__":
    # Initialize Mem0 client
    mem0_client = Memory.from_config(MEM0_CONFIG)

    # Initialize vocabulary manager
    vocabulary_manager = PostgreSQLVocabularyManager(db_config=VOCABULARY_DB_CONFIG)
    llm = LLMFactory(
        service_type="openai",
        model=os.getenv("LLM_MODEL_NAME"),
        openai_api_key=os.getenv("LLM_API_KEY"),
        openai_api_base=os.getenv("LLM_BASE_URL"),
    )
    # Create graph builder
    graph_builder = MemoryAgentGraphBuilder(
        mem0_client=mem0_client,
        llm=llm,
        vocabulary_manager=vocabulary_manager,
    )

    # Build the graph
    compiled_graph = graph_builder.build()
    print("Compiled graph:", compiled_graph)
