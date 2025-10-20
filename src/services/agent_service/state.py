"""State definitions for the memory-enabled LangGraph agent."""

from __future__ import annotations

from typing import List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from pydantic import BaseModel, Field
from typing_extensions import Annotated


class OverallState(TypedDict, total=False):
    """Graph state shared across nodes."""

    messages: Annotated[List[BaseMessage], add_messages]
    metadata_terms: List[str]


class Configuration(BaseModel):
    """Runtime configuration for the graph."""

    user_id: str = Field(default="default-user", description="Unique user identifier")
    agent_id: str = Field(
        default="default-agent", description="Identifier for this agent instance"
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="Optional thread identifier used for grouping interactions.",
    )
