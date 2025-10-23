"""State definitions for the memory-enabled LangGraph agent."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict, cast

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import add_messages
from pydantic import Field
from typing_extensions import Annotated


def _resolve_configuration(config: Optional[RunnableConfig]) -> Configuration:
    raw_config: Dict[str, Any] = {}
    if config and "configurable" in config:
        # config["configurable"] may be a mapping-like object
        raw_config = dict(config["configurable"])  # type: ignore[arg-type]
    # model_validate expects a dict but its stub may be Any; cast to Configuration
    return cast(Configuration, Configuration.model_validate(raw_config))


class GraphState(TypedDict, total=False):
    """
    Simplified graph state for desktop assistant agent (POC version).

    This state tracks:
    - messages: Conversation history
    - visual_context: [OPTIONAL] Captured screen information (for proactive scenarios)
    - action_plan: Planned actions based on reasoning
    - user_id: User identifier for memory retrieval
    - relevant_memories: Retrieved memories from query_memory

    Removed for POC simplification:
    - metadata_terms: Will be added after v1.0
    """

    messages: Annotated[List[BaseMessage], add_messages]
    visual_context: Optional[str] = ""
    action_plan: Optional[str] = ""
    user_id: str = ""
    relevant_memories: List[Dict[str, Any]] = []


class Configuration(RunnableConfig):
    """Runtime configuration for the graph."""

    user_id: str = Field(default="default-user", description="Unique user identifier")
    agent_id: str = Field(
        default="default-agent", description="Identifier for this agent instance"
    )
    capture_screen: bool = Field(
        default=False,
        description="Whether to capture screen for visual context",
    )
