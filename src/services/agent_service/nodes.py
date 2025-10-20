"""Graph construction utilities for the Phase 1 memory-enabled agent."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, Sequence, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent
from mem0 import Memory

from src.services.agent_service.message_util import trim_messages
from src.services.agent_service.state import Configuration, OverallState
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
        llm_factory: Callable[[], BaseChatModel],
        vocabulary_manager: PostgreSQLVocabularyManager,
        *,
        system_prompt: Optional[str] = None,
    ) -> None:
        self._mem0_client = mem0_client
        self._llm_factory = llm_factory
        self._vocabulary_manager = vocabulary_manager
        self._prompt = SystemMessage(content=(system_prompt or MEMORY_CONTEXT_PROMPT))

    def build(self) -> Any:
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

    def _agent_node(self, state: OverallState, config: RunnableConfig) -> OverallState:
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
        llm = self._llm_factory()
        agent = create_react_agent(
            llm,
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

        agent_state = agent.invoke({"messages": agent_messages}, config=config)
        return {"messages": agent_state["messages"]}


def build_memory_agent_graph(
    mem0_client: Memory,
    llm_factory: Callable[[], BaseChatModel],
    vocabulary_manager: PostgreSQLVocabularyManager,
    *,
    system_prompt: Optional[str] = None,
) -> Any:
    """Compile the Phase 1 LangGraph agent ready for ``agent.invoke``."""

    builder = MemoryAgentGraphBuilder(
        mem0_client=mem0_client,
        llm_factory=llm_factory,
        vocabulary_manager=vocabulary_manager,
        system_prompt=system_prompt,
    )
    return builder.build()


__all__ = ["MemoryAgentGraphBuilder", "build_memory_agent_graph"]
