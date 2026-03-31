"""CustomAgentState for LangGraph checkpointer migration."""

from typing import NotRequired, TypedDict

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
    pending_tasks: NotRequired[list[PendingTask]]
    ltm_last_consolidated_at_turn: NotRequired[int]
    knowledge_saved: NotRequired[bool]
