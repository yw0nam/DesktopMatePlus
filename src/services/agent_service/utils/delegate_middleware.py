"""DelegateToolMiddleware — injects DelegateTaskTool per request."""

from langchain.agents.middleware.types import AgentMiddleware
from langgraph.config import get_config

from src.services.agent_service.tools.delegate import DelegateTaskTool


class DelegateToolMiddleware(AgentMiddleware):
    """Middleware that injects DelegateTaskTool with per-request session_id.

    stm_service is fetched from the service registry at call time so this
    middleware carries no STM dependency at construction.
    """

    async def awrap_model_call(self, request, handler):
        from src.services.service_manager import get_stm_service

        stm_service = get_stm_service()
        if not stm_service:
            return await handler(request)
        session_id = get_config()["configurable"].get("session_id", "")
        delegate = DelegateTaskTool(stm_service=stm_service, session_id=session_id)
        return await handler(request.override(tools=[*request.tools, delegate]))

    async def awrap_tool_call(self, request, handler):
        _delegate_tool_name = DelegateTaskTool.model_fields["name"].default
        if request.tool_call["name"] != _delegate_tool_name:
            return await handler(request)
        from src.services.service_manager import get_stm_service

        stm_service = get_stm_service()
        session_id = get_config()["configurable"].get("session_id", "")
        delegate = DelegateTaskTool(stm_service=stm_service, session_id=session_id)
        return await handler(request.override(tool=delegate))
