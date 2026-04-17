"""HitLMiddleware — Human-in-the-Loop approval gate driven by a category map."""

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from langchain.agents.middleware.types import AgentMiddleware, ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command, interrupt
from loguru import logger

from src.models.websocket import ToolCategory

# Single source of truth for built-in tool categories.
# When adding a new built-in tool, add an entry here. A missing entry falls back
# to `ToolCategory.DANGEROUS` at lookup time (fail-closed). The structural test
# `tests/structural/test_default_categories_coverage.py` enforces completeness.
_DEFAULT_CATEGORIES: dict[str, ToolCategory] = {
    # Filesystem tools (group: filesystem)
    "read_file": ToolCategory.READ_ONLY,
    "list_directory": ToolCategory.READ_ONLY,
    "write_file": ToolCategory.STATE_MUTATING,
    # Shell tools (group: shell)
    "terminal": ToolCategory.DANGEROUS,
    # Web search (group: web_search — actual tool name is "duckduckgo_search")
    "duckduckgo_search": ToolCategory.READ_ONLY,
    # Memory tools
    "add_memory": ToolCategory.STATE_MUTATING,
    "update_memory": ToolCategory.STATE_MUTATING,
    "delete_memory": ToolCategory.STATE_MUTATING,
    "search_memory": ToolCategory.READ_ONLY,
    # Knowledge tools
    "search_knowledge": ToolCategory.READ_ONLY,
    "read_note": ToolCategory.READ_ONLY,
    # Profile tool
    "update_user_profile": ToolCategory.STATE_MUTATING,
    # Delegate tool
    "delegate_task": ToolCategory.EXTERNAL,
}


class HitLMiddleware(AgentMiddleware):
    """Intercepts non-bypass tool calls and requests user approval via interrupt().

    Bypass categories execute without approval. All other categories interrupt
    with the category forwarded in the payload so the client can differentiate
    UX (warning color, copy, future batch-approval policy).
    """

    _BYPASS_CATEGORIES: frozenset[ToolCategory] = frozenset({ToolCategory.READ_ONLY})

    def __init__(self, category_map: dict[str, ToolCategory]) -> None:
        self._category_map = dict(category_map)

    def get_category(self, tool_name: str) -> ToolCategory:
        """Look up the category for a tool. Unknown tools are fail-closed `dangerous`."""
        return self._category_map.get(tool_name, ToolCategory.DANGEROUS)

    def requires_approval(self, tool_name: str) -> bool:
        """True when the tool's category is not in `_BYPASS_CATEGORIES`."""
        return self.get_category(tool_name) not in self._BYPASS_CATEGORIES

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any] | str:
        """Gate a tool call by category.

        Bypass categories (READ_ONLY) run the handler directly. Non-bypass
        categories interrupt and wait for user approval; denied calls return
        a user-facing Korean denial string in place of tool output.
        """
        tool_name: str = request.tool_call["name"]
        category = self.get_category(tool_name)

        if category in self._BYPASS_CATEGORIES:
            logger.debug(f"HitL gate: '{tool_name}' bypass (category={category.value})")
            return await handler(request)

        args = request.tool_call.get("args", {})
        request_id = str(uuid4())

        logger.info(
            f"HitL gate: requesting approval for '{tool_name}' "
            f"(category={category.value}, request_id={request_id})"
        )

        resume_value = interrupt(
            {
                "tool_name": tool_name,
                "tool_args": args,
                "request_id": request_id,
                "category": category.value,
            }
        )

        if resume_value.get("approved"):
            logger.info(
                f"HitL gate: '{tool_name}' approved "
                f"(category={category.value}, request_id={request_id})"
            )
            return await handler(request)

        logger.info(
            f"HitL gate: '{tool_name}' denied "
            f"(category={category.value}, request_id={request_id})"
        )
        return f"사용자가 '{tool_name}' 도구 실행을 거부했습니다. 다른 방법을 시도해 주세요."
