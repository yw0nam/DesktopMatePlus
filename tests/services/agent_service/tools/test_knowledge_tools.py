from unittest.mock import MagicMock

import pytest

from src.services.agent_service.tools.knowledge.read_note import ReadNoteTool
from src.services.agent_service.tools.knowledge.search_knowledge import (
    SearchKnowledgeTool,
)
from src.services.knowledge_base_service.service import (
    KnowledgeBaseService,
    SearchResult,
)


@pytest.fixture
def mock_kb_service():
    svc = MagicMock(spec=KnowledgeBaseService)
    svc.search.return_value = [SearchResult(path="/kb/note.md", content="hello world")]
    svc.read.return_value = "---\ntitle: Note\n---\nhello world"
    return svc


def test_search_knowledge_tool_calls_service(mock_kb_service):
    tool = SearchKnowledgeTool(service=mock_kb_service)
    result = tool._run(query="hello", tags=[])
    mock_kb_service.search.assert_called_once_with(query="hello", tags=[])
    assert isinstance(result, list)
    assert len(result) == 1


def test_search_knowledge_tool_returns_dicts(mock_kb_service):
    tool = SearchKnowledgeTool(service=mock_kb_service)
    result = tool._run(query="hello", tags=[])
    assert result[0]["path"] == "/kb/note.md"
    assert result[0]["content"] == "hello world"


def test_search_knowledge_tool_default_tags(mock_kb_service):
    tool = SearchKnowledgeTool(service=mock_kb_service)
    tool._run(query="hello")  # no tags argument
    mock_kb_service.search.assert_called_once_with(query="hello", tags=[])


def test_search_knowledge_tool_empty_results(mock_kb_service):
    mock_kb_service.search.return_value = []
    tool = SearchKnowledgeTool(service=mock_kb_service)
    result = tool._run(query="no_match", tags=[])
    assert result == []


def test_read_note_tool_calls_service(mock_kb_service):
    tool = ReadNoteTool(service=mock_kb_service)
    result = tool._run(path="/kb/note.md")
    mock_kb_service.read.assert_called_once_with("/kb/note.md")
    assert "hello world" in result
