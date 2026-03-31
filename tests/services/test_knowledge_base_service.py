from src.services.knowledge_base_service.service import KnowledgeBaseService


def test_search_returns_results(tmp_path):
    note = tmp_path / "20260312-test.md"
    note.write_text("---\ntitle: Test\ntags: [test]\n---\ntest content here")

    svc = KnowledgeBaseService(kb_path=str(tmp_path))
    results = svc.search(query="test content", tags=[])
    assert len(results) > 0
    assert "test content" in results[0].content


def test_search_returns_empty_for_no_match(tmp_path):
    note = tmp_path / "20260312-test.md"
    note.write_text("---\ntitle: Test\n---\nhello world")

    svc = KnowledgeBaseService(kb_path=str(tmp_path))
    results = svc.search(query="zzz_no_match_xyz", tags=[])
    assert results == []


def test_read_returns_file_content(tmp_path):
    note = tmp_path / "20260312-test.md"
    note.write_text("---\ntitle: Test\n---\ncontent")

    svc = KnowledgeBaseService(kb_path=str(tmp_path))
    content = svc.read(str(note))
    assert "content" in content
