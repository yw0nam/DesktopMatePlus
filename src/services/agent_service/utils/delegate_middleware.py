"""DelegateToolMiddleware — injects DelegateTaskTool per request. No STM dependency."""

from langchain.agents.middleware.types import AgentMiddleware

from src.services.agent_service.tools.delegate import DelegateTaskTool


class DelegateToolMiddleware(AgentMiddleware):
    """Injects a fresh DelegateTaskTool instance into every model and tool call."""

    async def awrap_model_call(self, request, handler):
        delegate = DelegateTaskTool()
        return await handler(request.override(tools=[*request.tools, delegate]))

    async def awrap_tool_call(self, request, handler):
        _name = DelegateTaskTool.model_fields["name"].default
        if request.tool_call["name"] != _name:
            return await handler(request)
        return await handler(request.override(tool=DelegateTaskTool()))
