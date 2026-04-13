"""CustomAgentState for LangGraph checkpointer migration."""

from typing import NotRequired

from langchain.agents import AgentState


class CustomAgentState(AgentState):
    user_id: str
    agent_id: str
    ltm_last_consolidated_at_turn: NotRequired[int]
    knowledge_saved: NotRequired[bool]
    user_profile_loaded: NotRequired[bool]
    summary_last_consolidated_at_turn: NotRequired[int]
