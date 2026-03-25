# Testing Guide

Updated: 2026-03-23

## 1. Synopsis

- **Purpose**: Standardized testing conventions for DesktopMate+ Backend to ensure code quality and maintainability across AI, vision, speech, and memory services.
- **I/O**: Test functions → Pass/Fail results with clear assertions and coverage reports.

## 2. Core Logic

### 2.1 Test Structure

**Directory Layout:**
The test suite mirrors the `src/` directory structure to make finding tests intuitive.

```
tests/
  ├── agents/          # Agent factory and service manager tests
  ├── api/             # REST API endpoint tests (FastAPI)
  ├── config/          # Settings and environment configuration tests
  ├── core/            # Core logic, middleware, and message processing tests
  ├── services/        # Individual service tests (TTS, LTM, STM, Screen Capture, etc.)
  ├── storage/         # Database and vector store integration tests
  └── websocket/       # WebSocket gateway and message processor tests
```

**File Naming Convention:**

- Test files: `test_<module_name>.py` (mirrors `src/<module_path>/<module_name>.py`)
- Test functions: `test_<specific_behavior>()` (descriptive names)
- Test classes: `Test<ComponentName>` (grouping related tests)

### 2.2 Testing Patterns & Guidelines

**Arrange-Act-Assert Pattern:**
All tests should follow the AAA structure:

1. **Arrange**: Set up test data, mocks, and dependencies.
2. **Act**: Execute the function or method under test.
3. **Assert**: Verify the expected outcome using `assert` statements.

**Test Categories:**

| Category | Purpose | Example |
|----------|---------|---------|
| **Unit Tests** | Test individual functions/classes in isolation | Slug generation, config defaults |
| **Integration Tests** | Test service-to-service or service-to-DB interactions | STM MongoDB operations, LTM memory storage |
| **API/E2E Tests** | Test full request/response cycles | `/health` endpoint, WebSocket message flow |
| **Async Tests** | Test asynchronous code using `pytest-asyncio` | Service `is_healthy` checks, async API calls |

**What to Test:**

- **Core Service Logic**: Business logic for TTS synthesis, LTM/STM management, and agent task delegation.
- **API Contracts**: Ensure endpoints return correct status codes and response models.
- **Data Persistence**: Verify correct data is stored and retrieved from MongoDB/Qdrant.
- **Error Handling**: Graceful handling of invalid inputs, service timeouts, and connection failures.
- **WebSocket Protocols**: Correct message sequencing and error message propagation.

**What NOT to Test (in Unit/Integration Tests):**

- External AI APIs (OpenAI, Claude, etc.) - **Use Mocks**.
- Network availability - **Use Mocks**.
- Third-party library internals.

### 2.3 Async Testing & Mocking

**Async Tests:**
`asyncio_mode = "auto"` in `pyproject.toml` — no `@pytest.mark.asyncio` decorator needed.

```python
async def test_service_initialization():
    service = MyService()
    result = await service.initialize()
    assert result is True
```

**Mocking Strategy:**
Use `unittest.mock` (`patch`, `AsyncMock`, `MagicMock`) to isolate the code under test.

```python
from unittest.mock import AsyncMock, patch

async def test_api_with_mock_service(client):
    with patch("src.services.my_service.get_data", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"status": "success"}
        response = client.get("/my-endpoint")
        assert response.status_code == 200
```

### 2.4 Shared Fixtures

Common fixtures are defined in `tests/conftest.py`:

- `client`: A FastAPI `TestClient` for testing REST endpoints.
- `sample_user_id`: Returns "test_user_123".
- `sample_thread_id`: Returns "test_thread_456".
- `initialize_test_settings`: Resets settings to a controlled test configuration.

### 2.5 Running Tests

```bash
uv run pytest                                                          # all tests
uv run pytest tests/services/test_tts_synthesis.py                    # specific file
uv run pytest tests/api/test_health.py::TestHealth::test_check        # single test
uv run pytest -m slow                                                  # E2E (real services)
uv run pytest --cov=src                                                # with coverage
```

### 2.6 Constraints & Standards

- **Isolation**: Tests must not depend on each other. Use fresh instances or reset state in fixtures.
- **No External Side Effects**: Unit tests should not write to production databases or call real AI APIs.
- `slow` tests hit real MongoDB/Qdrant/LLM — skip in CI unless services are available.

## 3. Usage Examples

### Unit Test Example

```python
def test_normalize_tags_dedup():
    """Verify that tags are lowercased and duplicated tags are removed."""
    from src.services.knowledge_base_service.slug import normalize_tags
    assert normalize_tags(["NanoClaw", "nanoclaw"]) == ["nanoclaw"]
```

### API Test Example

```python
async def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

---

## Appendix

### PatchNote

2026-03-23: Initial version.
2026-03-25: Moved from `.claude/rules/TESTING_GUIDE.md` → `tests/CLAUDE.md`. Removed redundant `@pytest.mark.asyncio` note (covered by pyproject.toml asyncio_mode=auto).
