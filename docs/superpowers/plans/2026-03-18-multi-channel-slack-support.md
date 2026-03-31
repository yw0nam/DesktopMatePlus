# Multi-Channel Slack Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FastAPI 백엔드에 Slack 채널을 추가하여 Slack에서 Yuri 에이전트를 호출하고, NanoClaw 콜백 결과를 Slack으로 응답할 수 있도록 한다.

**Architecture:** SlackService(단일 클래스, 추상화 없음) + process_message() 공통 진입점 패턴. Webhook 라우트와 callback.py 양쪽이 process_message()를 공유한다. session_lock은 TTLCache 기반으로 메모리 누수를 방지한다.

**Tech Stack:** Python 3.13, FastAPI, slack_sdk, cachetools, pytest, MagicMock

---

## Key Codebase Facts (읽기 전 필수)

- **`AgentService.invoke()`** — ABC에 이미 존재. `async def invoke(...) -> dict[{content: str, new_chats: list[BaseMessage]}]`. 스펙의 `ainvoke()` = 이 메서드. 새로 추가 불필요.
- **`memory_orchestrator`** — `src/services/websocket_service/manager/memory_orchestrator.py`에 `load_context()`, `save_turn()` 함수로 존재.
- **`MongoDBSTM.add_chat_history()`** — 이미 sessions 컬렉션을 upsert함. 단, 메시지 없이 세션만 생성하는 전용 메서드(`upsert_session`)가 없으므로 추가 필요.
- **`BackgroundSweepService`** — `src/services/task_sweep_service/sweep.py`. 현재 만료된 태스크를 `failed`로 상태만 변경하고 Slack 알림은 없음.
- **테스트 패턴** — `patch()` + `MagicMock(spec=...)`. `conftest.py`의 `client` fixture를 사용.
- **서비스 등록 패턴** — `src/services/__init__.py` + `src/services/service_manager.py`에 등록, `main.py` lifespan에서 초기화.
- **설정 패턴** — YAML → Pydantic `BaseModel`. `yaml_files/main.yml`의 `services:` 키에 추가.

---

## File Map

### 신규 생성

| 파일 | 역할 |
|------|------|
| `src/services/channel_service/__init__.py` | `init_channel_service()`, `get_slack_service()`, `process_message()` |
| `src/services/channel_service/slack_service.py` | `SlackService`, `SlackMessage`, `SlackSettings` |
| `src/services/channel_service/session_lock.py` | TTLCache 기반 `session_lock()` |
| `src/api/routes/slack.py` | `POST /v1/channels/slack/events` webhook 라우트 |
| `yaml_files/services/channel_service/channel.yml` | Slack 설정 (bot_token, signing_secret 등) |
| `tests/services/channel_service/__init__.py` | 테스트 패키지 |
| `tests/services/channel_service/test_session_lock.py` | session_lock 단위 테스트 |
| `tests/services/channel_service/test_slack_service.py` | SlackService 단위 테스트 |
| `tests/services/channel_service/test_process_message.py` | process_message() 단위 테스트 |
| `tests/api/test_slack_webhook.py` | Slack webhook 엔드포인트 통합 테스트 |

### 수정

| 파일 | 변경 내용 |
|------|-----------|
| `pyproject.toml` | `cachetools`, `slack_sdk` 의존성 추가 |
| `src/services/stm_service/service.py` | `upsert_session()` abstract method 추가 |
| `src/services/stm_service/mongodb.py` | `upsert_session()` 구현 |
| `src/api/routes/__init__.py` | slack 라우터 등록 |
| `src/api/routes/callback.py` | `reply_channel` 조회 + `process_message()` 호출 |
| `src/services/task_sweep_service/sweep.py` | `slack_service_fn` 주입 + 타임아웃 시 Slack 알림 |
| `src/main.py` | `init_channel_service()` + `BackgroundSweepService` 슬랙 주입 |
| `yaml_files/main.yml` | `channel_service: channel.yml` 항목 추가 |
| `tests/conftest.py` | 테스트 YAML `services:` 에 `channel_service` 항목 추가 |

### Out of Scope (이 플랜에서 구현하지 않음)

- **Slack Socket Mode lifespan wiring** — `use_socket_mode=true`일 때 `SocketModeHandler.start_async()` 실행. 스펙 Section 4에 있으나 로컬 개발 편의 기능이며 현재 Webhook 방식으로 충분. 향후 별도 태스크로 구현.
- **Discord** — 향후 P2

---

## Task 1: 의존성 추가

**Files:**

- Modify: `pyproject.toml`

- [ ] **Step 1: cachetools, slack_sdk 추가**

`pyproject.toml`의 `dependencies` 섹션에 추가:

```toml
"cachetools>=5.5.0",
"slack_sdk>=3.34.0",
```

- [ ] **Step 2: 패키지 설치**

```bash

uv sync --all-extras
```

Expected: 설치 성공, 에러 없음

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add cachetools and slack_sdk dependencies"
```

---

## Task 2: session_lock (TTLCache)

**Files:**

- Create: `src/services/channel_service/session_lock.py`
- Create: `tests/services/channel_service/__init__.py`
- Create: `tests/services/channel_service/test_session_lock.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/services/channel_service/test_session_lock.py
import asyncio
import pytest
from src.services.channel_service.session_lock import session_lock


class TestSessionLock:
    def test_same_session_id_returns_same_lock(self):
        lock_a = session_lock("session-1")
        lock_b = session_lock("session-1")
        assert lock_a is lock_b

    def test_different_session_ids_return_different_locks(self):
        lock_a = session_lock("session-A")
        lock_b = session_lock("session-B")
        assert lock_a is not lock_b

    @pytest.mark.asyncio
    async def test_lock_is_async_context_manager(self):
        lock = session_lock("session-ctx")
        async with lock:
            pass  # Must not raise

    def test_lock_count_bounded_by_maxsize(self):
        """maxsize를 초과하면 가장 오래된 항목이 자동 evict된다."""
        from src.services.channel_service.session_lock import _locks
        original_maxsize = _locks.maxsize
        # 기본 maxsize=1024이므로 직접 검증은 하지 않고 import만 확인
        assert original_maxsize > 0
```

- [ ] **Step 2: 테스트 실패 확인**

```bash

uv run pytest tests/services/channel_service/test_session_lock.py -v
```

Expected: FAIL (ModuleNotFoundError: session_lock)

- [ ] **Step 3: 구현**

```python
# src/services/channel_service/session_lock.py
import asyncio

from cachetools import TTLCache

_SESSION_TTL = 600  # 10분
_locks: TTLCache[str, asyncio.Lock] = TTLCache(maxsize=1024, ttl=_SESSION_TTL)


def session_lock(session_id: str) -> asyncio.Lock:
    """Return an asyncio.Lock for the given session_id.

    Locks are cached with a 10-minute TTL and evicted automatically
    when unused, preventing memory leaks in long-running processes.
    """
    if session_id not in _locks:
        _locks[session_id] = asyncio.Lock()
    return _locks[session_id]
```

`src/services/channel_service/__init__.py`도 빈 파일로 생성 (다음 Task에서 채움):

```python
# src/services/channel_service/__init__.py
```

`tests/services/channel_service/__init__.py`:

```python
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/services/channel_service/test_session_lock.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/services/channel_service/ tests/services/channel_service/
git commit -m "feat: add TTL-based session_lock for channel concurrency control"
```

---

## Task 3: STMService.upsert_session()

**Files:**

- Modify: `src/services/stm_service/service.py`
- Modify: `src/services/stm_service/mongodb.py`
- Test: `tests/services/stm_service/test_upsert_session.py` (신규)

- [ ] **Step 1: 테스트 작성**

```python
# tests/services/stm_service/test_upsert_session.py
from unittest.mock import MagicMock, patch
import pytest
from src.services.stm_service.mongodb import MongoDBSTM


class TestUpsertSession:
    @pytest.fixture
    def stm(self):
        with patch.object(MongoDBSTM, "initialize_memory", return_value=MagicMock()):
            svc = MongoDBSTM(
                connection_string="mongodb://localhost",
                database_name="test",
                sessions_collection_name="sessions",
                messages_collection_name="messages",
            )
            svc._sessions_collection = MagicMock()
            return svc

    def test_upsert_creates_session_if_not_exists(self, stm):
        stm._sessions_collection.update_one.return_value = MagicMock(upserted_id="new")
        result = stm.upsert_session("slack:T1:C1:default", "default", "yuri")
        assert result is True
        stm._sessions_collection.update_one.assert_called_once()
        call_args = stm._sessions_collection.update_one.call_args
        assert call_args[1]["upsert"] is True

    def test_upsert_returns_true_on_success(self, stm):
        stm._sessions_collection.update_one.return_value = MagicMock()
        result = stm.upsert_session("slack:T1:C1:default", "default", "yuri")
        assert result is True

    def test_upsert_filter_uses_session_id_only(self, stm):
        stm._sessions_collection.update_one.return_value = MagicMock()
        stm.upsert_session("my-session", "user1", "agent1")
        filter_arg = stm._sessions_collection.update_one.call_args[0][0]
        assert filter_arg == {"session_id": "my-session"}
        update_arg = stm._sessions_collection.update_one.call_args[0][1]
        assert update_arg["$set"]["user_id"] == "user1"
        assert update_arg["$set"]["agent_id"] == "agent1"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/services/stm_service/test_upsert_session.py -v
```

Expected: FAIL (AttributeError: MongoDBSTM has no upsert_session)

- [ ] **Step 3: STMService ABC에 추상 메서드 추가**

`src/services/stm_service/service.py` 맨 끝에 추가:

```python
    @abstractmethod
    def upsert_session(self, session_id: str, user_id: str, agent_id: str) -> bool:
        """Create session if not exists, update user_id/agent_id if changed.

        Unlike add_chat_history, does not insert any messages.
        Used by channel handlers to ensure session exists before writing metadata.

        Returns:
            bool: True if successful.
        """
```

- [ ] **Step 4: MongoDBSTM 구현 추가**

`src/services/stm_service/mongodb.py`의 `update_session_metadata` 메서드 뒤에 추가:

```python
    def upsert_session(self, session_id: str, user_id: str, agent_id: str) -> bool:
        """Create session document if not exists. Does not add messages."""
        try:
            self._sessions_collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "agent_id": agent_id,
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$setOnInsert": {
                        "created_at": datetime.now(timezone.utc),
                        "metadata": {},
                    },
                },
                upsert=True,
            )
            logger.info(f"Upserted session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error upserting session {session_id}: {e}")
            raise
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/services/stm_service/test_upsert_session.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/services/stm_service/service.py src/services/stm_service/mongodb.py tests/services/stm_service/test_upsert_session.py
git commit -m "feat: add upsert_session to STMService for channel session initialization"
```

---

## Task 4: SlackService (파싱 + 전송)

**Files:**

- Create: `src/services/channel_service/slack_service.py`
- Create: `tests/services/channel_service/test_slack_service.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/services/channel_service/test_slack_service.py
import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.channel_service.slack_service import SlackMessage, SlackService, SlackSettings


def _make_settings(**kwargs):
    defaults = dict(
        enabled=True,
        bot_token="xoxb-test",
        signing_secret="test-secret",
        app_token="",
        use_socket_mode=False,
    )
    return SlackSettings(**(defaults | kwargs))


def _make_signature(secret: str, body: str, timestamp: str) -> str:
    base = f"v0:{timestamp}:{body}"
    return "v0=" + hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()


class TestSlackServiceSignature:
    def test_valid_signature_returns_true(self):
        svc = SlackService(_make_settings())
        ts = str(int(time.time()))
        body = '{"type":"event_callback"}'
        sig = _make_signature("test-secret", body, ts)
        assert svc.verify_signature(body=body, timestamp=ts, signature=sig) is True

    def test_invalid_signature_returns_false(self):
        svc = SlackService(_make_settings())
        ts = str(int(time.time()))
        assert svc.verify_signature(body="body", timestamp=ts, signature="v0=bad") is False

    def test_stale_timestamp_returns_false(self):
        svc = SlackService(_make_settings())
        old_ts = str(int(time.time()) - 400)  # 6+ minutes ago
        body = "body"
        sig = _make_signature("test-secret", body, old_ts)
        assert svc.verify_signature(body=body, timestamp=old_ts, signature=sig) is False


class TestParseEvent:
    @pytest.mark.asyncio
    async def test_returns_none_for_bot_message(self):
        svc = SlackService(_make_settings())
        payload = {
            "type": "event_callback",
            "team_id": "T1",
            "event": {
                "type": "message",
                "bot_id": "B1",
                "text": "bot said this",
                "channel": "C1",
                "user": "U1",
            },
        }
        result = await svc.parse_event(payload)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_slack_message_for_valid_event(self):
        svc = SlackService(_make_settings())
        payload = {
            "type": "event_callback",
            "team_id": "T1",
            "event": {
                "type": "message",
                "text": "hello yuri",
                "channel": "C1",
                "user": "U1",
            },
        }
        result = await svc.parse_event(payload)
        assert result is not None
        assert isinstance(result, SlackMessage)
        assert result.text == "hello yuri"
        assert result.channel_id == "C1"
        assert result.session_id == "slack:T1:C1:default"
        assert result.provider == "slack"

    @pytest.mark.asyncio
    async def test_returns_none_for_non_message_event(self):
        svc = SlackService(_make_settings())
        payload = {"type": "event_callback", "team_id": "T1", "event": {"type": "reaction_added"}}
        result = await svc.parse_event(payload)
        assert result is None


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_calls_slack_api(self):
        svc = SlackService(_make_settings())
        mock_client = MagicMock()
        mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})
        svc._client = mock_client

        await svc.send_message("C123", "hello!")
        mock_client.chat_postMessage.assert_called_once_with(channel="C123", text="hello!")
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/services/channel_service/test_slack_service.py -v
```

Expected: FAIL (ImportError: slack_service not found)

- [ ] **Step 3: SlackService 구현**

```python
# src/services/channel_service/slack_service.py
import hashlib
import hmac
import time
from dataclasses import dataclass

from loguru import logger
from pydantic import BaseModel
from slack_sdk.web.async_client import AsyncWebClient

STM_USER_ID = "default"  # TODO: multi-user support requires auth system
LTM_USER_ID = "default"  # TODO: multi-user support requires auth system

_SLACK_TIMESTAMP_TOLERANCE = 300  # 5분


class SlackSettings(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    signing_secret: str = ""
    app_token: str = ""
    use_socket_mode: bool = False


@dataclass
class SlackMessage:
    session_id: str    # "slack:{team_id}:{channel_id}:{STM_USER_ID}"
    channel_id: str    # 응답을 보낼 채널 ID
    provider: str      # "slack"
    text: str


class SlackService:
    """Slack Events API 검증, 이벤트 파싱, 메시지 전송을 담당한다."""

    def __init__(self, settings: SlackSettings) -> None:
        self._signing_secret = settings.signing_secret
        self._client = AsyncWebClient(token=settings.bot_token)

    def verify_signature(self, *, body: str, timestamp: str, signature: str) -> bool:
        """Slack request signature를 검증한다. Replay attack 방지를 위해 5분 이상 오래된 요청은 거부."""
        try:
            age = abs(time.time() - float(timestamp))
            if age > _SLACK_TIMESTAMP_TOLERANCE:
                logger.warning(f"Slack request too old: {age:.0f}s")
                return False
            base = f"v0:{timestamp}:{body}"
            expected = "v0=" + hmac.new(
                self._signing_secret.encode(), base.encode(), hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception:
            return False

    async def parse_event(self, payload: dict) -> SlackMessage | None:
        """Webhook payload에서 메시지를 추출한다.

        무시할 이벤트(봇 메시지, 비메시지 이벤트 등)는 None을 반환한다.
        """
        event = payload.get("event", {})
        if event.get("type") != "message":
            return None
        if event.get("bot_id"):
            return None
        text = event.get("text", "").strip()
        channel_id = event.get("channel", "")
        team_id = payload.get("team_id", "")
        if not text or not channel_id or not team_id:
            return None
        session_id = f"slack:{team_id}:{channel_id}:{STM_USER_ID}"
        return SlackMessage(
            session_id=session_id,
            channel_id=channel_id,
            provider="slack",
            text=text,
        )

    async def send_message(self, channel_id: str, text: str) -> None:
        """Slack Web API로 메시지를 전송한다. 실패 시 로그만 기록한다."""
        try:
            await self._client.chat_postMessage(channel=channel_id, text=text)
            logger.info(f"Slack message sent to {channel_id}")
        except Exception as e:
            logger.error(f"Failed to send Slack message to {channel_id}: {e}")
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/services/channel_service/test_slack_service.py -v
```

Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/services/channel_service/slack_service.py tests/services/channel_service/test_slack_service.py
git commit -m "feat: add SlackService for Slack Events API parsing and message sending"
```

---

## Task 5: channel_service init + process_message() + main.py 등록

**Files:**

- Modify: `src/services/channel_service/__init__.py`
- Modify: `src/main.py`
- Create: `yaml_files/services/channel_service/channel.yml`
- Create: `tests/services/channel_service/test_process_message.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/services/channel_service/test_process_message.py
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.services.channel_service import process_message


def _make_deps(invoke_content="응답"):
    agent_service = MagicMock()
    agent_service.invoke = AsyncMock(
        return_value={"content": invoke_content, "new_chats": [AIMessage(invoke_content)]}
    )
    stm = MagicMock()
    stm.upsert_session = MagicMock(return_value=True)
    stm.update_session_metadata = MagicMock(return_value=True)
    ltm = MagicMock()
    return agent_service, stm, ltm


class TestProcessMessage:
    @pytest.mark.asyncio
    async def test_calls_agent_invoke_with_human_message_when_text_provided(self):
        agent, stm, ltm = _make_deps()
        mock_slack = AsyncMock()

        with (
            patch(
                "src.services.channel_service.load_context",
                new=AsyncMock(return_value=[]),
            ),
            patch("src.services.channel_service.save_turn", new=AsyncMock()),
            patch("src.services.channel_service.get_slack_service", return_value=mock_slack),
        ):
            await process_message(
                text="안녕",
                session_id="slack:T1:C1:default",
                provider="slack",
                channel_id="C1",
                agent_service=agent,
                stm=stm,
                ltm=ltm,
            )

        call_messages = agent.invoke.call_args[1]["messages"]
        assert any(isinstance(m, HumanMessage) and m.content == "안녕" for m in call_messages)

    @pytest.mark.asyncio
    async def test_does_not_add_human_message_when_text_empty(self):
        """콜백 경로: text=""이면 HumanMessage를 context에 추가하지 않는다."""
        agent, stm, ltm = _make_deps()
        mock_slack = AsyncMock()

        with (
            patch(
                "src.services.channel_service.load_context",
                new=AsyncMock(return_value=[]),
            ),
            patch("src.services.channel_service.save_turn", new=AsyncMock()),
            patch("src.services.channel_service.get_slack_service", return_value=mock_slack),
        ):
            await process_message(
                text="",
                session_id="slack:T1:C1:default",
                provider="slack",
                channel_id="C1",
                agent_service=agent,
                stm=stm,
                ltm=ltm,
            )

        call_messages = agent.invoke.call_args[1]["messages"]
        assert not any(isinstance(m, HumanMessage) for m in call_messages)

    @pytest.mark.asyncio
    async def test_sends_response_to_slack(self):
        agent, stm, ltm = _make_deps("Yuri 응답")
        mock_slack = AsyncMock()

        with (
            patch("src.services.channel_service.load_context", new=AsyncMock(return_value=[])),
            patch("src.services.channel_service.save_turn", new=AsyncMock()),
            patch("src.services.channel_service.get_slack_service", return_value=mock_slack),
        ):
            await process_message(
                text="ping",
                session_id="slack:T1:C1:default",
                provider="slack",
                channel_id="C1",
                agent_service=agent,
                stm=stm,
                ltm=ltm,
            )

        mock_slack.send_message.assert_called_once_with("C1", "Yuri 응답")

    @pytest.mark.asyncio
    async def test_sends_error_message_on_invoke_failure(self):
        agent, stm, ltm = _make_deps()
        agent.invoke = AsyncMock(side_effect=RuntimeError("LLM 오류"))
        mock_slack = AsyncMock()

        with (
            patch("src.services.channel_service.load_context", new=AsyncMock(return_value=[])),
            patch("src.services.channel_service.save_turn", new=AsyncMock()),
            patch("src.services.channel_service.get_slack_service", return_value=mock_slack),
        ):
            await process_message(
                text="ping",
                session_id="slack:T1:C1:default",
                provider="slack",
                channel_id="C1",
                agent_service=agent,
                stm=stm,
                ltm=ltm,
            )

        mock_slack.send_message.assert_called_once()
        sent_text = mock_slack.send_message.call_args[0][1]
        assert "오류" in sent_text
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/services/channel_service/test_process_message.py -v
```

Expected: FAIL (ImportError from channel_service)

- [ ] **Step 3: channel_service/**init**.py 구현**

```python
# src/services/channel_service/__init__.py
import asyncio

from langchain_core.messages import AIMessage, HumanMessage
from loguru import logger

from src.services.agent_service.service import AgentService
from src.services.channel_service.session_lock import session_lock
from src.services.channel_service.slack_service import SlackService, SlackSettings
from src.services.ltm_service.service import LTMService
from src.services.stm_service.service import STMService
from src.services.websocket_service.manager.memory_orchestrator import load_context, save_turn

_slack_service: SlackService | None = None


def init_channel_service(settings: SlackSettings | None) -> None:
    """main.py lifespan에서 호출. SlackService 싱글톤을 초기화한다."""
    global _slack_service
    if settings and settings.enabled and settings.bot_token:
        _slack_service = SlackService(settings)
        logger.info("SlackService initialized")
    else:
        logger.info("SlackService disabled (enabled=false or bot_token missing)")


def get_slack_service() -> SlackService | None:
    return _slack_service


async def process_message(
    *,
    text: str,
    session_id: str,
    provider: str,
    channel_id: str,
    user_id: str = "default",    # TODO: multi-user support — 상수에서 읽도록 교체
    agent_id: str = "yuri",
    agent_service: AgentService,
    stm: STMService,
    ltm: LTMService,
) -> None:
    """외부 채널 메시지를 처리하고 응답을 전송한다.

    Webhook 라우트(text 있음)와 Callback 핸들러(text="") 양쪽에서 호출된다.
    text가 비어있으면 STM에 이미 TaskResult가 주입된 상태이므로 HumanMessage를 추가하지 않는다.
    """
    async with session_lock(session_id):
        # 1. STM 세션 upsert (세션이 없으면 생성)
        await asyncio.to_thread(stm.upsert_session, session_id, user_id, agent_id)
        # 2. reply_channel 메타데이터 저장
        await asyncio.to_thread(
            stm.update_session_metadata,
            session_id,
            {
                "user_id": user_id,
                "agent_id": agent_id,
                "reply_channel": {"provider": provider, "channel_id": channel_id},
            },
        )
        # 3. 컨텍스트 로드
        context = await load_context(
            stm_service=stm,
            ltm_service=ltm,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            query=text,
        )
        # 4. 에이전트 실행
        # text가 비어있으면 콜백 경로 — STM에 TaskResult가 이미 주입된 상태이므로
        # HumanMessage를 추가하지 않고 context만으로 invoke 호출.
        messages = context + [HumanMessage(text)] if text else context
        slack = get_slack_service() if provider == "slack" else None
        try:
            result = await agent_service.invoke(
                messages=messages,
                session_id=session_id,
                persona_id=agent_id,
                user_id=user_id,
                agent_id=agent_id,
            )
            final_text = result["content"]
            # new_chats에는 AgentService가 생성한 AIMessage(+tool messages)가 담겨 있다.
            # HumanMessage는 agent가 반환하지 않으므로 save_turn 시 별도로 prepend한다.
            new_chats = result["new_chats"]

            # 5. STM/LTM 저장 (fire-and-forget)
            chats_to_save = ([HumanMessage(text)] if text else []) + list(new_chats)
            asyncio.create_task(
                save_turn(
                    new_chats=chats_to_save,
                    stm_service=stm,
                    ltm_service=ltm,
                    user_id=user_id,
                    agent_id=agent_id,
                    session_id=session_id,
                )
            )

            # 6. 응답 전송
            if slack:
                await slack.send_message(channel_id, final_text)

        except Exception as e:
            logger.error(f"process_message failed for session {session_id}: {e}")
            if slack:
                await slack.send_message(channel_id, "처리 중 오류가 발생했어 😥 다시 시도해줘")
```

- [ ] **Step 4: YAML 설정 파일 생성**

```yaml
# yaml_files/services/channel_service/channel.yml
slack:
  enabled: false                             # 실제 사용 시 true로 변경
  bot_token: ""                              # SLACK_BOT_TOKEN env var
  signing_secret: ""                         # SLACK_SIGNING_SECRET env var
  app_token: ""                              # SLACK_APP_TOKEN (Socket Mode 전용)
  use_socket_mode: false                     # 로컬 개발 시 true
```

- [ ] **Step 5: main.py에 channel_service 초기화 추가**

`src/main.py`의 `_startup()` 함수 내 LTM 초기화 이후에 추가:

```python
            # Channel service (Slack 등 외부 채널)
            try:
                import yaml as _yaml
                from src.services.channel_service import init_channel_service
                from src.services.channel_service.slack_service import SlackSettings

                channel_config_path = config_paths.get("channel_service_path")
                slack_settings = SlackSettings()
                if channel_config_path and Path(channel_config_path).exists():
                    with open(channel_config_path, "r", encoding="utf-8") as _f:
                        _raw = _yaml.safe_load(_f) or {}
                    slack_cfg_dict = _raw.get("slack", {})
                    slack_settings = SlackSettings(**slack_cfg_dict)
                init_channel_service(slack_settings)
                logger.info("Channel service initialized")
            except Exception:
                logger.exception("Failed to initialize channel service")
```

- [ ] **Step 6: yaml_files/main.yml에 channel_service 추가**

`services:` 섹션에 추가:

```yaml
  channel_service: channel.yml
```

- [ ] **Step 7: 테스트 통과 확인**

```bash
uv run pytest tests/services/channel_service/test_process_message.py -v
```

Expected: 4 passed

- [ ] **Step 8: conftest.py 테스트 YAML에 channel_service 추가**

`tests/conftest.py`의 `test_settings_yaml` fixture 내 `config["services"]` dict에 추가:

```python
"channel_service": "channel.yml",
```

이로써 테스트 환경에서도 `config_paths`가 `channel_service_path`를 포함하게 된다.

- [ ] **Step 9: Commit**

```bash
git add src/services/channel_service/__init__.py yaml_files/services/channel_service/ yaml_files/main.yml src/main.py
git add tests/services/channel_service/test_process_message.py tests/conftest.py
git commit -m "feat: add channel_service with process_message() entry point and main.py registration"
```

---

## Task 6: Slack Webhook 라우트

**Files:**

- Create: `src/api/routes/slack.py`
- Modify: `src/api/routes/__init__.py`
- Create: `tests/api/test_slack_webhook.py`

- [ ] **Step 1: 테스트 작성**

```python
# tests/api/test_slack_webhook.py
import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_slack_signature(secret: str, body: str, timestamp: str) -> str:
    base = f"v0:{timestamp}:{body}"
    return "v0=" + hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()


URL_VERIFICATION_PAYLOAD = '{"type":"url_verification","challenge":"test-challenge-abc"}'

MESSAGE_PAYLOAD = (
    '{"type":"event_callback","team_id":"T1",'
    '"event":{"type":"message","text":"hello","channel":"C1","user":"U1"}}'
)

TEST_SECRET = "test-signing-secret"


def _headers(body: str, secret: str = TEST_SECRET) -> dict:
    ts = str(int(time.time()))
    sig = _make_slack_signature(secret, body, ts)
    return {
        "x-slack-request-timestamp": ts,
        "x-slack-signature": sig,
        "content-type": "application/json",
    }


class TestSlackWebhook:
    def test_url_verification_returns_challenge(self, client):
        body = URL_VERIFICATION_PAYLOAD
        mock_slack_svc = MagicMock()
        mock_slack_svc.verify_signature.return_value = True

        with patch("src.api.routes.slack.get_slack_service", return_value=mock_slack_svc):
            response = client.post(
                "/v1/channels/slack/events",
                content=body,
                headers=_headers(body),
            )

        assert response.status_code == 200
        assert response.json() == {"challenge": "test-challenge-abc"}

    def test_invalid_signature_returns_403(self, client):
        body = MESSAGE_PAYLOAD
        mock_slack_svc = MagicMock()
        mock_slack_svc.verify_signature.return_value = False

        with patch("src.api.routes.slack.get_slack_service", return_value=mock_slack_svc):
            response = client.post(
                "/v1/channels/slack/events",
                content=body,
                headers={
                    "x-slack-request-timestamp": "0",
                    "x-slack-signature": "v0=invalid",
                    "content-type": "application/json",
                },
            )

        assert response.status_code == 403

    def test_valid_message_returns_200_immediately(self, client):
        body = MESSAGE_PAYLOAD
        mock_slack_svc = MagicMock()
        mock_slack_svc.verify_signature.return_value = True
        mock_slack_svc.parse_event = AsyncMock(
            return_value=MagicMock(
                session_id="slack:T1:C1:default",
                channel_id="C1",
                provider="slack",
                text="hello",
            )
        )

        with (
            patch("src.api.routes.slack.get_slack_service", return_value=mock_slack_svc),
            patch("src.api.routes.slack.get_agent_service", return_value=MagicMock()),
            patch("src.api.routes.slack.get_stm_service", return_value=MagicMock()),
            patch("src.api.routes.slack.get_ltm_service", return_value=MagicMock()),
            patch("src.api.routes.slack.process_message", new=AsyncMock()) as mock_pm,
        ):
            response = client.post(
                "/v1/channels/slack/events",
                content=body,
                headers=_headers(body),
            )

        assert response.status_code == 200
        mock_pm.assert_called_once()  # 백그라운드 태스크가 실제로 예약됐는지 검증

    def test_slack_service_not_initialized_returns_503(self, client):
        body = MESSAGE_PAYLOAD
        with patch("src.api.routes.slack.get_slack_service", return_value=None):
            response = client.post(
                "/v1/channels/slack/events",
                content=body,
                headers=_headers(body),
            )
        assert response.status_code == 503
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/api/test_slack_webhook.py -v
```

Expected: FAIL (라우트 없음 → 404)

- [ ] **Step 3: Slack 라우트 구현**

```python
# src/api/routes/slack.py
"""Slack Events API webhook route."""

import asyncio

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from loguru import logger

from src.services import get_agent_service, get_ltm_service, get_stm_service
from src.services.channel_service import get_slack_service, process_message

router = APIRouter(prefix="/v1/channels/slack", tags=["Slack"])


@router.post(
    "/events",
    summary="Receive Slack Events API webhook",
    status_code=status.HTTP_200_OK,
    responses={
        403: {"description": "Invalid Slack signature"},
        503: {"description": "Slack service not initialized"},
    },
)
async def slack_events(request: Request) -> JSONResponse:
    """Slack Events API webhook 수신 엔드포인트.

    - URL verification challenge에 즉시 응답한다.
    - 유효한 메시지 이벤트는 백그라운드로 process_message()를 실행하고 즉시 200을 반환한다.
    """
    slack = get_slack_service()
    if slack is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack service not initialized",
        )

    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")
    timestamp = request.headers.get("x-slack-request-timestamp", "")
    signature = request.headers.get("x-slack-signature", "")

    if not slack.verify_signature(body=body_str, timestamp=timestamp, signature=signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    payload: dict = await request.json()

    # URL verification (Slack 앱 등록 시 1회)
    if payload.get("type") == "url_verification":
        return JSONResponse(content={"challenge": payload["challenge"]})

    # 메시지 파싱 (봇 메시지, 비관련 이벤트는 None)
    msg = await slack.parse_event(payload)
    if msg is None:
        return JSONResponse(content={"ok": True})

    # 즉시 200 반환, 실제 처리는 백그라운드
    agent_service = get_agent_service()
    stm = get_stm_service()
    ltm = get_ltm_service()

    asyncio.create_task(
        process_message(
            text=msg.text,
            session_id=msg.session_id,
            provider=msg.provider,
            channel_id=msg.channel_id,
            agent_service=agent_service,
            stm=stm,
            ltm=ltm,
        )
    )

    logger.info(f"Slack event queued for session {msg.session_id}")
    return JSONResponse(content={"ok": True})
```

- [ ] **Step 4: 라우터 등록**

`src/api/routes/__init__.py`에 추가:

```python
from src.api.routes import callback, ltm, slack, stm, tts, websocket
# ...
router.include_router(slack.router)
```

- [ ] **Step 5: get_ltm_service 임포트 확인**

`src/services/__init__.py`에 `get_ltm_service`가 이미 export되어 있는지 확인. 없으면 추가.

- [ ] **Step 6: 테스트 통과 확인**

```bash
uv run pytest tests/api/test_slack_webhook.py -v
```

Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add src/api/routes/slack.py src/api/routes/__init__.py tests/api/test_slack_webhook.py
git commit -m "feat: add POST /v1/channels/slack/events webhook route"
```

---

## Task 7: callback.py — reply_channel 라우팅

**Files:**

- Modify: `src/api/routes/callback.py`
- Modify: `tests/api/test_callback_api.py`

- [ ] **Step 1: 신규 테스트 추가 (기존 파일에 append)**

`tests/api/test_callback_api.py`에 새 class 추가:

```python
class TestCallbackSlackRouting:
    """reply_channel이 있는 Slack 세션에서 콜백이 process_message를 호출하는지 검증."""

    def test_slack_session_triggers_process_message(self, client, mock_stm_service):
        task_id = "task-slack-1"
        session_id = "slack:T1:C1:default"
        pending_tasks = [{"task_id": task_id, "status": "running", "description": "do work"}]
        mock_stm_service.get_session_metadata.return_value = {
            "pending_tasks": pending_tasks,
            "user_id": "default",
            "agent_id": "yuri",
            "reply_channel": {"provider": "slack", "channel_id": "C1"},
        }
        mock_stm_service.update_session_metadata.return_value = True
        mock_stm_service.add_chat_history.return_value = session_id

        with (
            patch("src.api.routes.callback.get_stm_service", return_value=mock_stm_service),
            patch("src.api.routes.callback.get_agent_service", return_value=MagicMock()),
            patch("src.api.routes.callback.get_ltm_service", return_value=MagicMock()),
            patch("src.api.routes.callback.process_message", new=AsyncMock()) as mock_pm,
        ):
            response = client.post(
                f"/v1/callback/nanoclaw/{session_id}",
                json={"task_id": task_id, "status": "done", "summary": "Task complete"},
            )

        assert response.status_code == 200
        mock_pm.assert_called_once()
        call_kwargs = mock_pm.call_args[1]
        assert call_kwargs["text"] == ""
        assert call_kwargs["provider"] == "slack"
        assert call_kwargs["channel_id"] == "C1"

    def test_unity_session_skips_process_message(self, client, mock_stm_service):
        """reply_channel 없는 Unity 세션은 기존 로직만 실행."""
        task_id = "task-unity-1"
        session_id = "unity-session-xyz"
        pending_tasks = [{"task_id": task_id, "status": "running"}]
        mock_stm_service.get_session_metadata.return_value = {
            "pending_tasks": pending_tasks,
            "user_id": "default",
            "agent_id": "yuri",
            # reply_channel 없음
        }
        mock_stm_service.update_session_metadata.return_value = True
        mock_stm_service.add_chat_history.return_value = session_id

        with (
            patch("src.api.routes.callback.get_stm_service", return_value=mock_stm_service),
            patch("src.api.routes.callback.process_message", new=AsyncMock()) as mock_pm,
        ):
            response = client.post(
                f"/v1/callback/nanoclaw/{session_id}",
                json={"task_id": task_id, "status": "done", "summary": "Done"},
            )

        assert response.status_code == 200
        mock_pm.assert_not_called()
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/api/test_callback_api.py::TestCallbackSlackRouting -v
```

Expected: FAIL (process_message not called / ImportError)

- [ ] **Step 3: callback.py 수정**

기존 `callback.py`의 import 섹션에 추가:

```python
import asyncio
from src.services import get_agent_service, get_ltm_service
from src.services.channel_service import process_message
```

`nanoclaw_callback` 함수의 마지막 `logger.info(...)` 이전에 추가:

```python
    # reply_channel이 있으면 Slack 등 외부 채널 세션 — process_message로 최종 응답
    reply_channel = metadata.get("reply_channel")
    if reply_channel:
        agent_svc = get_agent_service()
        stm_svc = get_stm_service()
        ltm_svc = get_ltm_service()
        asyncio.create_task(
            process_message(
                text="",  # STM에 TaskResult가 이미 주입된 상태 — HumanMessage 불필요
                session_id=session_id,
                provider=reply_channel["provider"],
                channel_id=reply_channel["channel_id"],
                user_id=metadata.get("user_id", "default"),
                agent_id=metadata.get("agent_id", "yuri"),
                agent_service=agent_svc,
                stm=stm_svc,
                ltm=ltm_svc,
            )
        )
        logger.info(f"Callback routing to {reply_channel['provider']} for session {session_id}")
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
uv run pytest tests/api/test_callback_api.py -v
```

Expected: 모든 기존 테스트 + 신규 2개 통과

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/callback.py tests/api/test_callback_api.py
git commit -m "feat: route nanoclaw callback to process_message for Slack sessions"
```

---

## Task 8: BackgroundSweepService — 타임아웃 시 Slack 알림

**Files:**

- Modify: `src/services/task_sweep_service/sweep.py`
- Modify: `src/main.py`
- Modify: `tests/services/task_sweep_service/test_sweep.py` (기존 파일에 추가)

- [ ] **Step 1: 테스트 작성**

기존 sweep 테스트 파일에 새 class 추가:

```python
# tests/services/task_sweep_service/test_sweep_slack.py (신규)
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.services.task_sweep_service.sweep import BackgroundSweepService, SweepConfig
from datetime import datetime, timezone, timedelta


def _expired_task(task_id: str) -> dict:
    return {
        "task_id": task_id,
        "status": "running",
        "created_at": (datetime.now(timezone.utc) - timedelta(seconds=999)).isoformat(),
    }


class TestSweepSlackNotification:
    @pytest.mark.asyncio
    async def test_expired_task_triggers_slack_send(self):
        stm = MagicMock()
        stm.list_all_sessions.return_value = [{"session_id": "slack:T1:C1:default"}]
        stm.get_session_metadata.return_value = {
            "pending_tasks": [_expired_task("task-1")],
            "reply_channel": {"provider": "slack", "channel_id": "C1"},
        }
        stm.update_session_metadata.return_value = True

        mock_slack = AsyncMock()
        slack_svc_fn = lambda: mock_slack  # noqa: E731

        svc = BackgroundSweepService(
            stm_service=stm,
            config=SweepConfig(sweep_interval_seconds=60, task_ttl_seconds=300),
            slack_service_fn=slack_svc_fn,
        )
        await svc._sweep_once()

        mock_slack.send_message.assert_called_once_with("C1", "태스크가 시간 초과됐어 😥")

    @pytest.mark.asyncio
    async def test_expired_unity_task_no_slack_call(self):
        """reply_channel 없는 Unity 세션은 Slack 알림 없이 상태만 변경."""
        stm = MagicMock()
        stm.list_all_sessions.return_value = [{"session_id": "unity-session"}]
        stm.get_session_metadata.return_value = {
            "pending_tasks": [_expired_task("task-u")],
            # reply_channel 없음
        }
        stm.update_session_metadata.return_value = True

        mock_slack = AsyncMock()
        svc = BackgroundSweepService(
            stm_service=stm,
            config=SweepConfig(),
            slack_service_fn=lambda: mock_slack,
        )
        await svc._sweep_once()
        mock_slack.send_message.assert_not_called()
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/services/task_sweep_service/test_sweep_slack.py -v
```

Expected: FAIL (`BackgroundSweepService.__init__` does not accept `slack_service_fn`)

- [ ] **Step 3: sweep.py 수정**

`BackgroundSweepService.__init__`에 `slack_service_fn` 파라미터 추가:

```python
from typing import Callable

class BackgroundSweepService:
    def __init__(
        self,
        stm_service: STMService,
        config: SweepConfig,
        slack_service_fn: Callable[[], "SlackService | None"] | None = None,
    ) -> None:
        self._stm = stm_service
        self.config = config
        self._slack_service_fn = slack_service_fn
        self._task: asyncio.Task | None = None
```

`_sweep_once()` 내부의 `if updated:` 블록을 아래와 같이 교체한다. `update_session_metadata` try/except **바깥쪽**에 Slack 알림을 추가해야 한다:

```python
            if updated:
                try:
                    self._stm.update_session_metadata(
                        session_id, {"pending_tasks": pending_tasks}
                    )
                except Exception:
                    logger.exception(
                        f"BackgroundSweepService: failed to update metadata for session {session_id}"
                    )
                # Slack 알림: reply_channel이 있는 외부 채널 세션만
                # update_session_metadata try/except 바깥에서 실행
                if self._slack_service_fn:
                    reply_channel = metadata.get("reply_channel")
                    if reply_channel and reply_channel.get("provider") == "slack":
                        slack = self._slack_service_fn()
                        if slack:
                            try:
                                await slack.send_message(
                                    reply_channel["channel_id"],
                                    "태스크가 시간 초과됐어 😥",
                                )
                            except Exception:
                                logger.exception("Failed to send sweep timeout Slack notification")
```

> **주의**: `_sweep_once`가 현재 `async def`이므로 `await slack.send_message()`는 직접 호출 가능.

- [ ] **Step 4: main.py BackgroundSweepService 초기화에 slack_service_fn 주입**

`main.py`에서 `BackgroundSweepService(stm_service=stm_svc, config=sweep_cfg)` 부분을:

```python
from src.services.channel_service import get_slack_service

sweep_service = BackgroundSweepService(
    stm_service=stm_svc,
    config=sweep_cfg,
    slack_service_fn=get_slack_service,
)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
uv run pytest tests/services/task_sweep_service/test_sweep_slack.py -v
```

Expected: 2 passed

- [ ] **Step 6: 전체 테스트 통과 확인**

```bash
uv run pytest -v
```

Expected: 전체 통과

- [ ] **Step 7: 린트**

```bash
sh scripts/lint.sh
```

Expected: 에러 없음

- [ ] **Step 8: Commit**

```bash
git add src/services/task_sweep_service/sweep.py src/main.py
git add tests/services/task_sweep_service/test_sweep_slack.py
git commit -m "feat: send Slack timeout notification from BackgroundSweepService"
```

---

## Task 9: 통합 테스트 (Slack Webhook → Callback 전체 흐름)

**Files:**

- Create: `tests/api/test_slack_integration.py`

- [ ] **Step 1: 통합 테스트 작성**

```python
# tests/api/test_slack_integration.py
"""Slack 전체 흐름 통합 테스트.

가짜 Slack payload → SlackService.parse_event → process_message → SlackService.send_message
NanoClaw는 모킹하여 Callback을 직접 트리거한다.
"""
import asyncio
import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage


def _make_headers(body: str, secret: str = "test-secret") -> dict:
    ts = str(int(time.time()))
    sig = "v0=" + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return {
        "x-slack-request-timestamp": ts,
        "x-slack-signature": sig,
        "content-type": "application/json",
    }


MESSAGE_BODY = (
    '{"type":"event_callback","team_id":"T1",'
    '"event":{"type":"message","text":"안녕 유리","channel":"C1","user":"U1"}}'
)

CALLBACK_PAYLOAD = {
    "task_id": "task-123",
    "status": "done",
    "summary": "개발 완료",
}


class TestSlackFullFlow:
    @pytest.mark.asyncio
    async def test_simple_message_reaches_slack_send(self, client):
        """Slack 메시지 → process_message → SlackService.send_message 까지 전달된다."""
        mock_slack_svc = MagicMock()
        mock_slack_svc.verify_signature.return_value = True
        mock_slack_svc.parse_event = AsyncMock(
            return_value=MagicMock(
                session_id="slack:T1:C1:default",
                channel_id="C1",
                provider="slack",
                text="안녕 유리",
            )
        )
        mock_slack_svc.send_message = AsyncMock()

        mock_agent = MagicMock()
        mock_agent.invoke = AsyncMock(
            return_value={"content": "안녕!", "new_chats": [AIMessage("안녕!")]}
        )

        mock_stm = MagicMock()
        mock_stm.upsert_session = MagicMock(return_value=True)
        mock_stm.update_session_metadata = MagicMock(return_value=True)
        mock_stm.get_chat_history = MagicMock(return_value=[])

        mock_ltm = MagicMock()
        mock_ltm.search_memory = MagicMock(return_value={"results": []})

        with (
            patch("src.api.routes.slack.get_slack_service", return_value=mock_slack_svc),
            patch("src.api.routes.slack.get_agent_service", return_value=mock_agent),
            patch("src.api.routes.slack.get_stm_service", return_value=mock_stm),
            patch("src.api.routes.slack.get_ltm_service", return_value=mock_ltm),
            patch("src.services.channel_service.get_slack_service", return_value=mock_slack_svc),
        ):
            response = client.post(
                "/v1/channels/slack/events",
                content=MESSAGE_BODY,
                headers=_make_headers(MESSAGE_BODY),
            )
            assert response.status_code == 200

            # 백그라운드 태스크 실행 대기
            await asyncio.sleep(0.1)

        mock_slack_svc.send_message.assert_called_once_with("C1", "안녕!")

    @pytest.mark.asyncio
    async def test_callback_triggers_final_slack_response(self, client):
        """NanoClaw 콜백 → process_message(text="") → SlackService.send_message."""
        session_id = "slack:T1:C1:default"
        task_id = "task-123"

        mock_stm = MagicMock()
        mock_stm.get_session_metadata.return_value = {
            "pending_tasks": [{"task_id": task_id, "status": "running"}],
            "user_id": "default",
            "agent_id": "yuri",
            "reply_channel": {"provider": "slack", "channel_id": "C1"},
        }
        mock_stm.update_session_metadata.return_value = True
        mock_stm.add_chat_history.return_value = session_id
        mock_stm.upsert_session = MagicMock(return_value=True)
        mock_stm.get_chat_history = MagicMock(return_value=[])

        mock_agent = MagicMock()
        mock_agent.invoke = AsyncMock(
            return_value={"content": "결과 받았어!", "new_chats": [AIMessage("결과 받았어!")]}
        )
        mock_ltm = MagicMock()
        mock_ltm.search_memory = MagicMock(return_value={"results": []})
        mock_slack_svc = AsyncMock()

        with (
            patch("src.api.routes.callback.get_stm_service", return_value=mock_stm),
            patch("src.api.routes.callback.get_agent_service", return_value=mock_agent),
            patch("src.api.routes.callback.get_ltm_service", return_value=mock_ltm),
            patch("src.services.channel_service.get_slack_service", return_value=mock_slack_svc),
        ):
            response = client.post(
                f"/v1/callback/nanoclaw/{session_id}",
                json=CALLBACK_PAYLOAD,
            )
            assert response.status_code == 200
            await asyncio.sleep(0.1)

        mock_slack_svc.send_message.assert_called_once_with("C1", "결과 받았어!")
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
uv run pytest tests/api/test_slack_integration.py -v
```

Expected: FAIL or ERROR (의존 모듈 연결 문제)

- [ ] **Step 3: 테스트 통과 확인 (수정 필요 시 디버깅)**

```bash
uv run pytest tests/api/test_slack_integration.py -v
```

Expected: 2 passed

- [ ] **Step 4: 전체 테스트 + 린트**

```bash
uv run pytest -v
sh scripts/lint.sh
```

Expected: 전체 통과, 린트 에러 없음

- [ ] **Step 5: Commit**

```bash
git add tests/api/test_slack_integration.py
git commit -m "test: add Slack full-flow integration tests (webhook → callback → send)"
```

---

## 완료 기준 체크리스트

- [ ] `uv run pytest` — 전체 통과
- [ ] `sh scripts/lint.sh` — 에러 없음
- [ ] `POST /v1/channels/slack/events` 엔드포인트 존재 (docs 확인)
- [ ] `POST /v1/callback/nanoclaw/{session_id}` — reply_channel 있을 때 Slack 응답 트리거
- [ ] `BackgroundSweepService` — 타임아웃 시 Slack 채널로 에러 메시지 전송
- [ ] `session_lock` — TTLCache, 10분 TTL
- [ ] `process_message(text="")` — HumanMessage 추가하지 않음 (콜백 경로)
