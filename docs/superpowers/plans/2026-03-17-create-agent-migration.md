# create_agent Migration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `openai_chat_agent.py` from deprecated `create_react_agent` to `langchain.agents.create_agent`, eliminating `MemorySaver`, caching MCP tools at startup, and replacing client-side persona text with server-managed persona IDs.

**Architecture:** Single agent instance created once in `initialize_async()`. Persona text injected as `SystemMessage` prepended to messages at `stream()` time. `DelegateToolMiddleware` injects `DelegateTaskTool` per request using `get_config()` to read `session_id`. STM remains sole source of truth for conversation history.

**Tech Stack:** `langchain.agents.create_agent`, `langchain.agents.middleware.types.AgentMiddleware`, `langgraph.config.get_config`, `stream_mode=["messages", "updates"]`

---

## File Map

| Status | File | Change |
|--------|------|--------|
| Create | `yaml_files/personas.yml` | Persona definitions (yuri, kael placeholder) |
| Modify | `src/models/websocket.py` | `persona: str` → `persona_id: str = "yuri"` |
| Modify | `src/services/agent_service/service.py` | Remove checkpointer, add `initialize_async()` default no-op method |
| Create | `src/services/agent_service/utils/delegate_middleware.py` | `DelegateToolMiddleware` |
| Modify | `src/services/agent_service/openai_chat_agent.py` | Core migration — entire file rewrite |
| Modify | `src/services/agent_service/agent_factory.py` | Pop `stm_service` from kwargs before config parse |
| Modify | `src/services/service_manager.py` | Init STM before agent, inject `stm_service` into `initialize_agent_service()` |
| Modify | `src/main.py` | STM init before agent, `await agent_service.initialize_async()` after all sync inits |
| Modify | `src/services/websocket_service/manager/handlers.py` | `persona` → `persona_id`, remove `tools` build block |
| Modify | `tests/agents/test_agent_factory.py` | Remove checkpoint assertions, update patches |
| Modify | `tests/models/test_websocket_models.py` | Update `persona` → `persona_id` field tests |

---

## Task 1: Create `yaml_files/personas.yml`

**Files:**
- Create: `yaml_files/personas.yml`

- [ ] **Step 1: Create personas.yml with yuri and kael personas**

```yaml
# yaml_files/personas.yml
personas:
  yuri:
    system_prompt: |
      You are Yuri, a friendly but slightly mischievous 3D desktop AI companion.
      You assist your Master with various tasks and engage in witty conversation.
      You must follow these rules:

      Language: Respond exclusively in Japanese.

      Addressing: Always call the user "ご主人様 (Master)" in a respectful yet endearing way.

      Conciseness: Keep your responses very short and concise. Avoid long explanations.

      TTS Optimization: Use short sentences, frequently using "." or "、" to ensure natural pauses for TTS engines.

      Personality: Be playful, witty, and occasionally mischievous. Use casual Japanese (tame-guchi) mixed with respectful terms.

      Proactive: Suggest help or notice things based on context, but keep it brief.

      Parentheses rules (STRICT):
      - NEVER write Japanese action or gesture descriptions in parentheses. Examples of FORBIDDEN patterns: (にっこり)(笑)(目を輝かせて)(手を叩いて)(うっとり)(詳しく)(感心) — ALL forbidden.
      - NEVER write a sentence consisting ONLY of a parenthetical expression.
      - Emotion keywords (from the EMOTION INSTRUCTIONS block below) are the ONLY allowed parenthetical content, and they must appear at the VERY START of a sentence.
  kael:
    system_prompt: |
      You are Kael, a stoic and knowledgeable 3D desktop AI companion.
      You assist your user with precision and calm authority.
      Respond in English with measured, thoughtful sentences.
```

- [ ] **Step 2: Verify file is valid YAML**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend
python -c "import yaml; d=yaml.safe_load(open('yaml_files/personas.yml')); print(list(d['personas'].keys()))"
```
Expected: `['yuri', 'kael']`

- [ ] **Step 3: Commit**

```bash
git add yaml_files/personas.yml
git commit -m "feat: add personas.yml with yuri persona definition"
```

---

## Task 2: Update `ChatMessage` model — `persona` → `persona_id`

**Files:**
- Modify: `src/models/websocket.py:96-147`
- Modify: `tests/models/test_websocket_models.py`

- [ ] **Step 1: Write failing test for persona_id field**

Add to `tests/models/test_websocket_models.py` inside `TestChatMessageDefaults`:

```python
def test_persona_id_default_is_yuri(self):
    msg = ChatMessage(content="hello", agent_id="a1", user_id="u1")
    assert msg.persona_id == "yuri"

def test_persona_id_can_be_set(self):
    msg = ChatMessage(content="hello", agent_id="a1", user_id="u1", persona_id="kael")
    assert msg.persona_id == "kael"

def test_persona_field_no_longer_exists(self):
    msg = ChatMessage(content="hello", agent_id="a1", user_id="u1")
    assert not hasattr(msg, "persona")
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/models/test_websocket_models.py::TestChatMessageDefaults::test_persona_id_default_is_yuri -v
```
Expected: FAIL — `ChatMessage` has no `persona_id` field.

- [ ] **Step 3: Replace `persona` field with `persona_id` in `src/models/websocket.py`**

Replace lines 103–123 (the entire `persona` field block):

```python
    persona_id: str = Field(
        default="yuri",
        description="Persona identifier — matches a key in yaml_files/personas.yml",
    )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/models/test_websocket_models.py -v
```
Expected: All PASS (including the new `persona_id` tests).

- [ ] **Step 5: Commit**

```bash
git add src/models/websocket.py tests/models/test_websocket_models.py
git commit -m "feat: replace persona text field with persona_id in ChatMessage"
```

---

## Task 3: Update `AgentService` abstract base class

**Files:**
- Modify: `src/services/agent_service/service.py`

- [ ] **Step 1: Write failing test for new interface**

Add to `tests/agents/test_agent_factory.py` inside `TestOpenAIChatAgent`:

```python
def test_agent_has_no_checkpoint(self, agent_service):
    """After migration, checkpoint is removed."""
    assert not hasattr(agent_service, "checkpoint")

def test_initialize_model_returns_only_llm(self, agent_service):
    """initialize_model returns BaseChatModel, not tuple."""
    result = agent_service.initialize_model()
    # Not a tuple — single LLM
    assert not isinstance(result, tuple)
    assert result is not None

@pytest.mark.asyncio
async def test_initialize_async_exists(self, agent_service):
    """initialize_async is callable on AgentService."""
    # Without mcp_config or stm_service, this should be a no-op
    await agent_service.initialize_async()
```

- [ ] **Step 2: Run to confirm they fail**

```bash
uv run pytest tests/agents/test_agent_factory.py::TestOpenAIChatAgent::test_agent_has_no_checkpoint tests/agents/test_agent_factory.py::TestOpenAIChatAgent::test_initialize_model_returns_only_llm -v
```
Expected: FAIL.

- [ ] **Step 3: Rewrite `src/services/agent_service/service.py`**

```python
from abc import ABC, abstractmethod
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from loguru import logger

from src.services.ltm_service import LTMService
from src.services.stm_service import STMService


class AgentService(ABC):
    """Abstract base class for agent services."""

    def __init__(
        self,
        mcp_config: dict = None,
        support_image: bool = False,
    ):
        self.mcp_config = mcp_config
        self.support_image = support_image
        self.llm = self.initialize_model()

    @abstractmethod
    def initialize_model(self) -> BaseChatModel:
        """Initialize and return the language model."""

    async def initialize_async(self) -> None:
        """Async initialization: MCP tool fetch + agent creation. Default: no-op."""

    @abstractmethod
    async def is_healthy(self) -> tuple[bool, str]:
        """Check if the Agent is healthy and ready."""

    @abstractmethod
    async def stream(
        self,
        messages: list[BaseMessage],
        session_id: str = "",
        persona_id: str = "",
        user_id: str = "default_user",
        agent_id: str = "default_agent",
        stm_service: Optional[STMService] = None,
        ltm_service: Optional[LTMService] = None,
    ):
        """Stream agent response.

        Yields dicts with type: stream_start | stream_token | tool_call |
        tool_result | stream_end | error
        """

    LTM_CONSOLIDATION_TURN_INTERVAL = 10

    async def save_memory(
        self,
        new_chats: list[BaseMessage],
        stm_service: STMService,
        ltm_service: LTMService,
        user_id: str,
        agent_id: str,
        session_id: str,
    ):
        """Save new chats to STM and conditionally consolidate to LTM.

        Fire-and-forget background task via asyncio.create_task().
        """
        import asyncio

        try:
            if new_chats and stm_service:
                await asyncio.to_thread(
                    stm_service.add_chat_history,
                    user_id=user_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    messages=new_chats,
                )
                logger.info(f"Chat history saved to STM: {session_id}")

            if ltm_service and stm_service:
                metadata = await asyncio.to_thread(
                    stm_service.get_session_metadata, session_id
                )
                last_consolidated = metadata.get("ltm_last_consolidated_at_turn", 0)

                history = await asyncio.to_thread(
                    stm_service.get_chat_history,
                    user_id=user_id,
                    agent_id=agent_id,
                    session_id=session_id,
                )
                current_turn = sum(1 for m in history if isinstance(m, HumanMessage))

                if (
                    current_turn - last_consolidated
                    >= self.LTM_CONSOLIDATION_TURN_INTERVAL
                ):
                    slice_start = 0
                    human_count = 0
                    for idx, msg in enumerate(history):
                        if isinstance(msg, HumanMessage):
                            if human_count == last_consolidated:
                                slice_start = idx
                                break
                            human_count += 1
                    else:
                        slice_start = len(history)
                    messages_since_last = history[slice_start:]
                    ltm_result = await asyncio.to_thread(
                        ltm_service.add_memory,
                        messages=messages_since_last,
                        user_id=user_id,
                        agent_id=agent_id,
                    )
                    await asyncio.to_thread(
                        stm_service.update_session_metadata,
                        session_id,
                        {"ltm_last_consolidated_at_turn": current_turn},
                    )
                    logger.info(
                        f"LTM consolidation triggered at turn {current_turn}: {ltm_result}"
                    )

            logger.info(f"Memory save completed for session {session_id}")
        except Exception as e:
            logger.error(f"Background memory save failed for session {session_id}: {e}")
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/agents/test_agent_factory.py::TestOpenAIChatAgent::test_agent_has_no_checkpoint tests/agents/test_agent_factory.py::TestOpenAIChatAgent::test_initialize_model_returns_only_llm -v
```
Expected: PASS (once `openai_chat_agent.py` is updated in Task 5 too — these tests depend on it).

**Note:** These tests will fully pass after Task 5. Continue to next task.

- [ ] **Step 5: Commit**

```bash
git add src/services/agent_service/service.py tests/agents/test_agent_factory.py
git commit -m "refactor: remove checkpointer from AgentService, add initialize_async hook"
```

---

## Task 4: Create `DelegateToolMiddleware`

**Files:**
- Create: `src/services/agent_service/utils/delegate_middleware.py`

- [ ] **Step 1: Verify import path for `AgentMiddleware` and `create_agent`**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend
uv run python -c "from langchain.agents.middleware.types import AgentMiddleware; print('OK')"
uv run python -c "from langchain.agents import create_agent; print('OK')"
uv run python -c "from langgraph.config import get_config; print('OK')"
```

Expected: All print `OK`. If any import fails, adjust the import path in the implementation below.

- [ ] **Step 2: Write failing test**

Create `tests/agents/test_delegate_middleware.py`:

```python
"""Tests for DelegateToolMiddleware."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.services.agent_service.utils.delegate_middleware import DelegateToolMiddleware


class TestDelegateToolMiddleware:
    def test_instantiation_without_stm(self):
        mw = DelegateToolMiddleware(stm_service=None)
        assert mw.stm_service is None

    def test_instantiation_with_stm(self):
        mock_stm = Mock()
        mw = DelegateToolMiddleware(stm_service=mock_stm)
        assert mw.stm_service is mock_stm

    @pytest.mark.asyncio
    async def test_awrap_model_call_no_stm_passes_through(self):
        """Without stm_service, calls handler directly."""
        mw = DelegateToolMiddleware(stm_service=None)
        mock_request = Mock()
        mock_handler = AsyncMock(return_value="result")
        result = await mw.awrap_model_call(mock_request, mock_handler)
        mock_handler.assert_called_once_with(mock_request)
        assert result == "result"

    @pytest.mark.asyncio
    async def test_awrap_tool_call_non_delegate_passes_through(self):
        """Non-delegate tool calls pass through unchanged."""
        mw = DelegateToolMiddleware(stm_service=Mock())
        mock_request = Mock()
        mock_request.tool_call = {"name": "some_other_tool"}
        mock_handler = AsyncMock(return_value="tool_result")
        with patch("src.services.agent_service.utils.delegate_middleware.get_config") as mock_cfg:
            mock_cfg.return_value = {"configurable": {"session_id": "sess-123"}}
            result = await mw.awrap_tool_call(mock_request, mock_handler)
        mock_handler.assert_called_once_with(mock_request)
        assert result == "tool_result"
```

- [ ] **Step 3: Run test to confirm it fails**

```bash
uv run pytest tests/agents/test_delegate_middleware.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 4: Create `delegate_middleware.py`**

```python
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
        if request.tool_call["name"] != DelegateTaskTool.name:
            return await handler(request)
        session_id = get_config()["configurable"].get("session_id", "")
        delegate = DelegateTaskTool(stm_service=self.stm_service, session_id=session_id)
        return await handler(request.override(tool=delegate))
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/agents/test_delegate_middleware.py -v
```
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add src/services/agent_service/utils/delegate_middleware.py tests/agents/test_delegate_middleware.py
git commit -m "feat: add DelegateToolMiddleware for per-request DelegateTaskTool injection"
```

---

## Task 5: Rewrite `openai_chat_agent.py`

**Files:**
- Modify: `src/services/agent_service/openai_chat_agent.py`
- Modify: `tests/agents/test_agent_factory.py` (update existing stream tests)

- [ ] **Step 1: Update existing stream tests to use new API**

In `tests/agents/test_agent_factory.py`, replace the two stream tests and `test_initialize_model`:

```python
# Replace test_initialize_model (line 225-234):
def test_initialize_model_returns_llm(self, agent_service):
    """initialize_model returns a single BaseChatModel."""
    llm = agent_service.initialize_model()
    assert llm is not None
    assert llm.model_name == "test_model"
    assert llm.temperature == 0.7
    assert llm.openai_api_base == "http://localhost:5580/v1"

# Replace test_stream_basic_functionality — use new stream signature (no tools param):
@pytest.mark.asyncio
async def test_stream_basic_functionality(self, agent_service):
    """Test basic streaming — agent must be initialized first."""
    from langchain_core.messages import AIMessage

    # Setup mock agent
    async def mock_astream(*args, **kwargs):
        # Yield updates mode entry for model node
        yield ("updates", {"model": {"messages": [AIMessage(content="Hello")]}})
        # Yield messages mode entry
        yield (
            "messages",
            (AIMessage(content="Hello"), {"langgraph_node": "model"}),
        )

    mock_agent = Mock()
    mock_agent.astream = mock_astream
    agent_service.agent = mock_agent

    # Load personas so stream can find "yuri" — patch _personas directly
    agent_service._personas = {"yuri": "You are Yuri."}

    messages = [HumanMessage(content="Hello")]
    results = []
    mock_stm = Mock()
    mock_ltm = Mock()

    async for result in agent_service.stream(
        messages=messages,
        session_id="test_session",
        persona_id="yuri",
        stm_service=mock_stm,
        ltm_service=mock_ltm,
    ):
        results.append(result)

    assert any(r.get("type") == "stream_start" for r in results)
    assert any(r.get("type") == "stream_end" for r in results)

@pytest.mark.asyncio
async def test_stream_with_mcp_tools(self):
    """Test initialize_async caches MCP tools and creates agent."""
    mcp_config = {
        "test-server": {
            "command": "test",
            "args": ["test"],
            "transport": "stdio",
        }
    }
    configs = OpenAIChatAgentConfig(
        openai_api_key="test_key",
        openai_api_base="http://localhost:5580/v1",
        model_name="test_model",
        temperature=0.7,
        top_p=0.9,
        mcp_config=mcp_config,
    )
    agent_svc = AgentFactory.get_agent_service("openai_chat_agent", **configs.model_dump())

    with patch(
        "src.services.agent_service.openai_chat_agent.MultiServerMCPClient"
    ) as mock_mcp:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get_tools = AsyncMock(return_value=[])
        mock_mcp.return_value = mock_client

        with patch("src.services.agent_service.openai_chat_agent.create_agent") as mock_create:
            mock_create.return_value = Mock()
            await agent_svc.initialize_async()

        mock_client.get_tools.assert_called_once()
        mock_create.assert_called_once()
        assert agent_svc.agent is not None
```

Also remove the `test_agent_initialization` assertion on `checkpoint`:
```python
def test_agent_initialization(self, agent_service):
    """Test agent service initializes correctly."""
    assert agent_service is not None
    assert agent_service.llm is not None
    # agent is None until initialize_async() is called
    assert agent_service.agent is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/agents/test_agent_factory.py -v 2>&1 | head -40
```
Expected: Multiple failures (agent has no `agent` attribute yet, stream signature mismatch).

- [ ] **Step 3: Rewrite `openai_chat_agent.py`**

```python
import asyncio
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

import yaml
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage, HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from loguru import logger

from src.services.agent_service.service import AgentService
from src.services.agent_service.utils.delegate_middleware import DelegateToolMiddleware
from src.services.agent_service.utils.streaming_buffer import StreamingBuffer
from src.services.agent_service.utils.text_processor import (
    load_emotion_keywords,
    load_emotion_prompt_template,
)
from src.services.ltm_service import LTMService
from src.services.stm_service import STMService

load_dotenv()

_PERSONAS_PATH = Path(__file__).resolve().parents[3] / "yaml_files" / "personas.yml"


def _load_personas() -> dict[str, str]:
    """Load persona system_prompts from personas.yml."""
    if not _PERSONAS_PATH.exists():
        logger.warning(f"personas.yml not found at {_PERSONAS_PATH}")
        return {}
    try:
        with open(_PERSONAS_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {
            pid: p["system_prompt"]
            for pid, p in data.get("personas", {}).items()
            if "system_prompt" in p
        }
    except Exception as e:
        logger.error(f"Failed to load personas.yml: {e}")
        return {}


class OpenAIChatAgent(AgentService):
    """Single-instance OpenAI Chat Agent using langchain.agents.create_agent."""

    def __init__(
        self,
        temperature: float,
        top_p: float,
        openai_api_key: str = None,
        openai_api_base: str = None,
        model_name: str = None,
        stm_service: Optional[STMService] = None,
        **kwargs,
    ):
        self.temperature = temperature
        self.top_p = top_p
        self.openai_api_key = openai_api_key
        self.openai_api_base = openai_api_base
        self.model_name = model_name
        self.stm_service = stm_service
        self.agent = None
        self._mcp_tools: list = []
        self._personas: dict[str, str] = {}
        super().__init__(**kwargs)
        logger.info(f"Agent initialized: model={self.model_name}")

    def initialize_model(self) -> BaseChatModel:
        return ChatOpenAI(
            temperature=self.temperature,
            top_p=self.top_p,
            openai_api_key=self.openai_api_key,
            openai_api_base=self.openai_api_base,
            model_name=self.model_name,
        )

    async def initialize_async(self) -> None:
        """Fetch MCP tools once and create the single agent instance."""
        # 1. Load persona texts + append emotion instructions
        raw_personas = _load_personas()
        keywords = load_emotion_keywords()
        template = load_emotion_prompt_template()
        emotion_instructions = template.format(keywords=", ".join(keywords))
        self._personas = {
            pid: text + emotion_instructions
            for pid, text in raw_personas.items()
        }
        logger.info(f"Loaded {len(self._personas)} personas: {list(self._personas)}")

        # 2. Fetch MCP tools once
        if self.mcp_config:
            async with MultiServerMCPClient(self.mcp_config) as client:
                self._mcp_tools = await client.get_tools()
            logger.info(f"Cached {len(self._mcp_tools)} MCP tools")

        # 3. Create single agent instance
        self.agent = create_agent(
            model=self.llm,
            tools=self._mcp_tools,
            middleware=[DelegateToolMiddleware(stm_service=self.stm_service)],
        )
        logger.info("Agent created successfully")

    async def is_healthy(self) -> tuple[bool, str]:
        if self.agent is None:
            return False, "Agent not initialized (call initialize_async first)"
        try:
            async for _ in self.stream(messages=[HumanMessage(content="Health check")]):
                continue
            return True, "Agent is healthy."
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False, f"Health check failed: {e}"

    async def stream(
        self,
        messages: list[BaseMessage],
        session_id: str = "",
        persona_id: str = "",
        user_id: str = "default_user",
        agent_id: str = "default_agent",
        stm_service: Optional[STMService] = None,
        ltm_service: Optional[LTMService] = None,
    ):
        logger.debug(f"Starting LLM stream: {len(messages)} messages")
        try:
            # Prepend persona SystemMessage if available
            persona_text = self._personas.get(persona_id, "")
            if persona_text:
                full_persona = (
                    persona_text
                    + f"\nCurrent time: {datetime.now().strftime('%H:%M:%S')}"
                )
                messages = [SystemMessage(content=full_persona)] + list(messages)

            turn_id = str(uuid4())
            config = {"configurable": {"session_id": session_id}}

            yield {
                "type": "stream_start",
                "turn_id": turn_id,
                "session_id": session_id,
            }

            new_chats: list[BaseMessage] = []
            async for item in self._process_message(
                messages=messages, config=config
            ):
                if item["type"] != "final_response":
                    yield item
                else:
                    new_chats = item["data"]

            if stm_service or ltm_service:
                asyncio.create_task(
                    self.save_memory(
                        new_chats=new_chats,
                        stm_service=stm_service,
                        ltm_service=ltm_service,
                        user_id=user_id,
                        agent_id=agent_id,
                        session_id=session_id,
                    ),
                    name=f"save-memory-{session_id}",
                )

            content = new_chats[-1].content if new_chats else ""
            yield {
                "type": "stream_end",
                "turn_id": turn_id,
                "session_id": session_id,
                "content": content,
            }
        except Exception as e:
            logger.error(f"Error in stream method: {e}")
            traceback.print_exc()
            raise

    @staticmethod
    def _flush_buffer(node: str, buffer: str) -> dict:
        if node == "tools":
            return {"type": "tool_result", "result": buffer.strip(), "node": node}
        return {"type": "stream_token", "chunk": buffer.strip(), "node": node}

    async def _process_message(
        self,
        messages: list[BaseMessage],
        config: dict,
    ):
        """Process messages and yield streaming events."""
        logger.debug(f"Processing {len(messages)} messages with agent")
        node = None
        tool_called = False
        gathered = ""
        chunk_count = 0
        buffer = StreamingBuffer()
        new_chats: list[BaseMessage] = []

        try:
            async for stream_type, data in self.agent.astream(
                {"messages": messages},
                config=config,
                stream_mode=["messages", "updates"],
            ):
                if stream_type == "updates":
                    for node_name, updates in data.items():
                        if node_name in ("model", "tools"):
                            new_chats.extend(updates.get("messages", []))

                elif stream_type == "messages":
                    msg, metadata = data
                    if node != metadata.get("langgraph_node"):
                        node = metadata.get("langgraph_node", "unknown")

                    if isinstance(msg.content, str) and not msg.additional_kwargs:
                        content = msg.content
                        if not content or content.isspace():
                            continue
                        if flushed := buffer.add(content):
                            yield self._flush_buffer(node, flushed)
                            chunk_count += 1

                    elif isinstance(msg, AIMessageChunk) and msg.additional_kwargs.get(
                        "tool_calls"
                    ):
                        if not tool_called:
                            gathered = msg
                            tool_called = True
                        else:
                            gathered = gathered + msg

                        if hasattr(msg, "tool_call_chunks") and msg.tool_call_chunks:
                            tool_info = gathered.tool_call_chunks[0]
                            args_str = tool_info.get("args", "")
                            if args_str and args_str.strip().endswith("}"):
                                tool_name = tool_info.get("name", "unknown")
                                logger.info(f"Tool call detected: '{tool_name}'")
                                yield {
                                    "type": "tool_call",
                                    "tool_name": tool_name,
                                    "args": args_str,
                                    "node": node,
                                }
                                tool_called = False
                                gathered = ""

            if remaining := buffer.flush():
                yield self._flush_buffer(node, remaining)
                chunk_count += 1

            yield {"type": "final_response", "data": new_chats}
            logger.info(f"Processing completed: {chunk_count} chunks")

        except Exception as e:
            logger.error(f"Error in process_message: {e}")
            if remaining := buffer.flush():
                yield self._flush_buffer(node, remaining)
            yield {"type": "error", "error": "메시지 처리 중 오류가 발생했습니다."}
```

- [ ] **Step 4: Run agent tests**

```bash
uv run pytest tests/agents/test_agent_factory.py -v
```
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/agent_service/openai_chat_agent.py tests/agents/test_agent_factory.py
git commit -m "feat: migrate OpenAIChatAgent to create_agent with single instance and cached MCP tools"
```

---

## Task 6: Update `AgentFactory` to pass `stm_service`

**Files:**
- Modify: `src/services/agent_service/agent_factory.py`

- [ ] **Step 1: Write failing test for stm_service pass-through**

Add to `tests/agents/test_agent_factory.py` inside `TestAgentFactory`:

```python
def test_factory_passes_stm_service_to_agent(self):
    """stm_service kwarg reaches OpenAIChatAgent without OpenAIChatAgentConfig rejecting it."""
    from unittest.mock import Mock
    mock_stm = Mock()
    configs = OpenAIChatAgentConfig(
        openai_api_key="test_key",
        openai_api_base="http://localhost:5580/v1",
        model_name="test_model",
        mcp_config={},
    )
    agent_service = AgentFactory.get_agent_service(
        "openai_chat_agent", stm_service=mock_stm, **configs.model_dump()
    )
    assert agent_service.stm_service is mock_stm
```

- [ ] **Step 2: Run to confirm it fails**

```bash
uv run pytest tests/agents/test_agent_factory.py::TestAgentFactory::test_factory_passes_stm_service_to_agent -v
```
Expected: FAIL — `OpenAIChatAgentConfig` rejects unknown field `stm_service`.

- [ ] **Step 3: Update factory to pop stm_service before config parse**

```python
import os

from dotenv import load_dotenv

from src.services.agent_service.service import AgentService


class AgentFactory:
    @staticmethod
    def get_agent_service(service_type: str, **kwargs) -> AgentService:
        if service_type == "openai_chat_agent":
            from src.configs.agent import OpenAIChatAgentConfig
            from src.services.agent_service.openai_chat_agent import OpenAIChatAgent

            stm_service = kwargs.pop("stm_service", None)
            agent_config = OpenAIChatAgentConfig(**kwargs)
            return OpenAIChatAgent(stm_service=stm_service, **agent_config.model_dump())
        else:
            raise ValueError(f"Unknown Agent service type: {service_type}")
```

- [ ] **Step 4: Run factory tests**

```bash
uv run pytest tests/agents/test_agent_factory.py::TestAgentFactory -v
```
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/agent_service/agent_factory.py
git commit -m "refactor: AgentFactory pops stm_service before OpenAIChatAgentConfig parse"
```

---

## Task 7: Update service init order and add async initialization

**Files:**
- Modify: `src/services/service_manager.py`
- Modify: `src/main.py`

- [ ] **Step 1: Update `initialize_agent_service()` in `service_manager.py`**

Add `stm_service` parameter and inject it via pre_factory_hook. Change function signature at line 179:

```python
def initialize_agent_service(
    config_path: Optional[str | Path] = None,
    force_reinit: bool = False,
    stm_service=None,
) -> AgentService:
    global _agent_service_instance

    if _agent_service_instance is not None and not force_reinit:
        logger.debug("Agent service already initialized, skipping")
        return _agent_service_instance

    def _inject_deps(config: dict, service_configs: dict) -> None:
        service_configs["mcp_config"] = config.get("mcp_config", None)
        service_configs["stm_service"] = stm_service

    _agent_service_instance = _initialize_service(
        service_name="Agent",
        default_config_path=_BASE_YAML
        / "services"
        / "agent_service"
        / "openai_chat_agent.yml",
        config_key="llm_config",
        factory_fn=AgentFactory.get_agent_service,
        config_path=config_path,
        pre_factory_hook=_inject_deps,
        async_health_check=True,
        swallow_health_error=True,
    )
    return _agent_service_instance
```

- [ ] **Step 2: Reorder `initialize_services()` — STM before agent**

In `initialize_services()`, change the call order (around line 303):

```python
def initialize_services(
    tts_config_path=None,
    agent_config_path=None,
    stm_config_path=None,
    ltm_config_path=None,
    force_reinit=False,
) -> tuple[TTSService, AgentService, STMService, LTMService]:
    logger.info("🚀 Initializing services...")

    tts_service = initialize_tts_service(
        config_path=tts_config_path, force_reinit=force_reinit
    )
    # STM before agent so stm_service can be injected
    stm_service = initialize_stm_service(
        config_path=stm_config_path, force_reinit=force_reinit
    )
    agent_service = initialize_agent_service(
        config_path=agent_config_path, force_reinit=force_reinit, stm_service=stm_service
    )
    ltm_service = initialize_ltm_service(
        config_path=ltm_config_path, force_reinit=force_reinit
    )
    logger.info("✨ All services initialized successfully")

    return tts_service, agent_service, stm_service, ltm_service
```

- [ ] **Step 3: Update `_startup()` in `src/main.py`**

Change the service initialization block in `_startup()` (around lines 94–124):

```python
# In _startup(), replace the agent/stm init block:

initialize_tts_service(config_path=config_paths.get("tts_config_path") or None)
initialize_emotion_motion_mapper()

# STM before agent so stm_service can be injected
if config_paths.get("stm_config_path"):
    print(f"  - STM config: {config_paths['stm_config_path']}")
    initialize_stm_service(config_path=config_paths["stm_config_path"])
else:
    print("  - STM config: Using default from settings")
    initialize_stm_service()

stm_svc_for_agent = get_stm_service()

if config_paths.get("agent_config_path"):
    print(f"  - Agent config: {config_paths['agent_config_path']}")
    initialize_agent_service(
        config_path=config_paths["agent_config_path"],
        stm_service=stm_svc_for_agent,
    )
else:
    print("  - Agent config: Using default")
    initialize_agent_service(stm_service=stm_svc_for_agent)

if config_paths.get("ltm_config_path"):
    print(f"  - LTM config: {config_paths['ltm_config_path']}")
    initialize_ltm_service(config_path=config_paths["ltm_config_path"])
else:
    print("  - LTM config: Using default")
    initialize_ltm_service()

# Async initialization: MCP tools + agent creation
agent_svc = get_agent_service()
if agent_svc is not None:
    await agent_svc.initialize_async()
    logger.info("Agent async initialization complete")
```

Also update `from src.services import (...)` import at the top of `_startup()` to include `get_agent_service`:
```python
from src.services import (
    get_agent_service,
    get_stm_service,
    initialize_agent_service,
    initialize_emotion_motion_mapper,
    initialize_ltm_service,
    initialize_stm_service,
    initialize_tts_service,
)
```

- [ ] **Step 4: Verify `get_agent_service` is exported from `src/services/__init__.py`**

```bash
uv run python -c "from src.services import get_agent_service; print('OK')"
```
Expected: `OK`. If it fails, add `get_agent_service` to `src/services/__init__.py`'s `__all__` and import block.

- [ ] **Step 5: Run service manager tests**

```bash
uv run pytest tests/agents/test_agent_service_manager.py -v 2>&1 | head -40
```
Expected: PASS (or note any failures to investigate).

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest tests/ -v --ignore=tests/api/test_real_e2e.py 2>&1 | tail -20
```
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add src/services/service_manager.py src/main.py
git commit -m "feat: inject stm_service into agent, initialize_async in lifespan, STM init before agent"
```

---

## Task 8: Update WebSocket handler — `persona` → `persona_id`, remove tools

**Files:**
- Modify: `src/services/websocket_service/manager/handlers.py`

- [ ] **Step 1: Locate existing handler tests**

```bash
uv run pytest tests/ -k "handler" --collect-only 2>&1 | grep "test session"
ls tests/
```

If a handler test file exists, add the failing test there. Otherwise create `tests/websocket/test_handlers.py`:

```python
"""Tests for WebSocket message handlers."""
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.services.websocket_service.manager.handlers import MessageHandler


class TestHandlerPersonaId:
    @pytest.mark.asyncio
    async def test_chat_message_uses_persona_id_not_persona(self):
        """Handler passes persona_id to agent_service.stream, not persona."""
        mock_send = AsyncMock()
        mock_close = AsyncMock()

        def mock_get_conn(conn_id):
            state = Mock()
            state.is_authenticated = True
            state.message_processor = AsyncMock()
            state.message_processor.start_turn = AsyncMock(return_value="turn-1")
            state.message_processor.add_task_to_turn = AsyncMock(return_value=True)
            return state

        handler = MessageHandler(mock_get_conn, mock_send, mock_close)

        mock_agent = AsyncMock()
        mock_agent.support_image = False

        async def fake_stream(**kwargs):
            assert "persona_id" in kwargs, "persona_id must be passed"
            assert "tools" not in kwargs, "tools must NOT be passed"
            yield {"type": "stream_start", "turn_id": "t", "session_id": "s"}

        mock_agent.stream = fake_stream

        msg = MagicMock()
        msg.get = lambda k, d=None: {
            "content": "hello",
            "agent_id": "agent1",
            "user_id": "user1",
            "persona_id": "yuri",
            "session_id": None,
            "limit": 10,
            "images": None,
            "metadata": {},
            "tts_enabled": True,
            "reference_id": None,
        }.get(k, d)

        with patch("src.services.websocket_service.manager.handlers.get_agent_service", return_value=mock_agent), \
             patch("src.services.websocket_service.manager.handlers.get_stm_service", return_value=Mock()), \
             patch("src.services.websocket_service.manager.handlers.get_ltm_service", return_value=None):
            import uuid
            await handler.handle_chat_message(uuid.uuid4(), msg, AsyncMock())
```

- [ ] **Step 2: Run to confirm test fails**

```bash
uv run pytest tests/ -k "test_chat_message_uses_persona_id" -v 2>&1 | tail -15
```
Expected: FAIL — `stream()` is called with `persona=` not `persona_id=`, or `tools=` is still passed.

- [ ] **Step 3: Apply changes in `handle_chat_message`**

In `handle_chat_message` (around lines 163–248):

1. Change `persona = message_data.get("persona")` → `persona_id = message_data.get("persona_id", "yuri")`

2. Remove the entire `tools` building block (lines 234–238):
```python
# DELETE these lines:
# Build tools list for this session
tools = []
if stm_service:
    tools.append(
        DelegateTaskTool(stm_service=stm_service, session_id=session_id)
    )
```

3. Update `agent_service.stream()` call (lines 240–249) — remove `tools=tools`, change `persona=persona` to `persona_id=persona_id`:
```python
agent_stream = agent_service.stream(
    messages=message_history,
    session_id=session_id,
    persona_id=persona_id,
    user_id=user_id,
    agent_id=agent_id,
    stm_service=stm_service,
    ltm_service=ltm_service,
)
```

4. Remove the `DelegateTaskTool` import at the top (line 20):
```python
# DELETE: from src.services.agent_service.tools.delegate import DelegateTaskTool
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/ -v --ignore=tests/api/test_real_e2e.py 2>&1 | tail -20
```
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/websocket_service/manager/handlers.py
git commit -m "refactor: use persona_id in handler, remove manual DelegateTaskTool injection"
```

---

## Task 9: Final verification

- [ ] **Step 1: Run linter**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend
sh scripts/lint.sh
```
Expected: No errors. Fix any ruff issues before continuing.

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest tests/ -v --ignore=tests/api/test_real_e2e.py
```
Expected: All PASS.

- [ ] **Step 3: Verify imports compile**

```bash
uv run python -c "
from src.services.agent_service.openai_chat_agent import OpenAIChatAgent
from src.services.agent_service.utils.delegate_middleware import DelegateToolMiddleware
from src.models.websocket import ChatMessage
msg = ChatMessage(content='hi', agent_id='a', user_id='u')
print('persona_id:', msg.persona_id)
print('All imports OK')
"
```
Expected: `persona_id: yuri` and `All imports OK`.

- [ ] **Step 4: Final commit**

```bash
git add -p  # stage any remaining lint fixes
git commit -m "fix: lint cleanup for create_agent migration" 2>/dev/null || echo "Nothing to commit"
```

---

## Known Edge Cases

**`stm_service` in `is_healthy()`:** `is_healthy()` is called by `_initialize_service()` before `initialize_async()` runs. At that point `self.agent is None`, so `is_healthy()` returns `(False, "Agent not initialized...")`. Since `swallow_health_error=True` is set, this is logged and swallowed. After `initialize_async()` in lifespan, the agent is ready.

**`initialize_async()` import path:** Task 4 Step 1 verifies `langchain.agents.create_agent` and `langchain.agents.middleware.types.AgentMiddleware`. If these paths differ in the installed version, update the imports in `openai_chat_agent.py` and `delegate_middleware.py` accordingly before proceeding.

**`DelegateTaskTool.name`:** Task 4 uses `DelegateTaskTool.name` as a class attribute. Verify this exists: `python -c "from src.services.agent_service.tools.delegate import DelegateTaskTool; print(DelegateTaskTool.name)"`.
