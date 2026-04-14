"""HitLMiddleware — Human-in-the-Loop approval gate for dangerous tool calls."""

from uuid import uuid4

from langchain.agents.middleware.types import AgentMiddleware
from langgraph.types import interrupt
from loguru import logger

# Hardcoded deny-list for Phase 1 MVP
_STATIC_DENY_LIST: frozenset[str] = frozenset()

# delegate_task tool name — matches DelegateTaskTool.name field
_DELEGATE_TOOL_NAME = "delegate_task"


class HitLMiddleware(AgentMiddleware):
    """Intercepts dangerous tool calls and requests user approval via interrupt().

    Dangerous tools: MCP tools (dynamic, from agent init) + delegate_task + static deny-list.
    Safe tools pass through unchanged.
    """

    def __init__(self, mcp_tool_names: set[str] | None = None) -> None:
        self._dangerous_names: frozenset[str] = frozenset(
            (mcp_tool_names or set()) | _STATIC_DENY_LIST | {_DELEGATE_TOOL_NAME}
        )

    def is_dangerous(self, tool_name: str) -> bool:
        """Check if a tool requires HitL approval."""
        return tool_name in self._dangerous_names

    async def awrap_tool_call(self, request, handler):
        """Wrap tool call with interrupt() for dangerous tools."""
        tool_name: str = request.tool_call["name"]

        if not self.is_dangerous(tool_name):
            return await handler(request)

        args = request.tool_call.get("args", {})
        request_id = str(uuid4())

        logger.info(
            f"HitL gate: requesting approval for '{tool_name}' (request_id={request_id})"
        )

        # interrupt() raises GraphInterrupt, caught by LangGraph runtime
        # Returns the resume value from Command(resume=...) when graph is resumed
        resume_value = interrupt(
            {
                "tool_name": tool_name,
                "tool_args": args,
                "request_id": request_id,
            }
        )

        if resume_value.get("approved"):
            logger.info(f"HitL gate: '{tool_name}' approved (request_id={request_id})")
            return await handler(request)

        logger.info(f"HitL gate: '{tool_name}' denied (request_id={request_id})")
        return f"User denied execution of '{tool_name}'. Try a different approach."
