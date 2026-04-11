"""Web search tool backed by DuckDuckGo."""

from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import BaseTool
from loguru import logger


def get_search_tools() -> list[BaseTool]:
    """Return a DuckDuckGoSearchRun tool.

    Returns:
        List containing one DuckDuckGoSearchRun instance.
    """
    logger.info("Web search tool (DuckDuckGo) enabled")
    return [DuckDuckGoSearchRun()]
