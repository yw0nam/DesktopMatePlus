"""DelegateToolMiddleware — injects DelegateTaskTool per request."""

from langchain.agents.middleware.types import AgentMiddleware
from langgraph.config import get_config

from src.services.agent_service.tools.delegate import DelegateTaskTool
from src.services.stm_service import STMService


class DelegateToolMiddleware(AgentMiddleware):
    """Middleware that injects DelegateTaskTool with per-request session_id.

    stm_service is passed at construction. session_id is read from
    RunnableConfig.configurable at call time via get_config().
    """

    def __init__(self, stm_service: STMService | None):
        self.stm_service = stm_service

    async def awrap_model_call(self, request, handler):
        if not self.stm_service:
            return await handler(request)
        session_id = get_config()["configurable"].get("session_id", "")
        delegate = DelegateTaskTool(stm_service=self.stm_service, session_id=session_id)
        return await handler(request.override(tools=[*request.tools, delegate]))

    async def awrap_tool_call(self, request, handler):
        _delegate_tool_name = DelegateTaskTool.model_fields["name"].default
        if request.tool_call["name"] != _delegate_tool_name:
            return await handler(request)
        session_id = get_config()["configurable"].get("session_id", "")
        delegate = DelegateTaskTool(stm_service=self.stm_service, session_id=session_id)
        return await handler(request.override(tool=delegate))
