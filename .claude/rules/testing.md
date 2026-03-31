---
description: Test file rules (applies when creating or editing test files)
paths: "tests/**/*.py"
---

# Testing Rules

## Principles

1. **Boundary tests**: always cover edge cases and boundary values
2. **Happy + error paths**: cover both success and failure cases
3. **Independence**: each test must not depend on other test state
4. **Clear naming**: test name must describe what is being tested

## Naming Convention

```python
class TestServiceName:
    async def test_does_expected_behavior_when_condition(self): ...
```

## Pytest Config

- `asyncio_mode = "auto"` in pyproject.toml — no `@pytest.mark.asyncio` needed
- Mark slow tests with `@pytest.mark.slow` (hits real MongoDB/Qdrant/LLM)
- Run fast tests only: `uv run pytest -m "not slow"`

## Do Not

- Mock the database for integration tests — real MongoDB/Qdrant for integration coverage
- Share mutable state between tests
- Test implementation internals — test behavior via public interfaces
