"""CustomAgentState for LangGraph checkpointer migration."""

from typing import TypedDict

from langchain.agents import AgentState


class ReplyChannel(TypedDict):
    provider: str  # "slack" | "websocket"
    channel_id: str


class PendingTask(TypedDict):
    task_id: str
    description: str
    status: str  # "running" | "done" | "failed"
    created_at: str
    reply_channel: ReplyChannel | None


class CustomAgentState(AgentState):
    user_id: str
    agent_id: str
    pending_tasks: list[PendingTask]
    ltm_last_consolidated_at_turn: int
    knowledge_saved: bool
