# Slack Mention Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Filter Slack messages so the bot only responds when explicitly mentioned in public/group channels, while always responding in DMs.

**Architecture:** Add `bot_name` to `SlackSettings` and `_bot_user_id`/`_bot_name` state to `SlackService`. A new async `initialize()` method calls Slack's `auth.test` to discover the bot's user ID. `parse_event()` is updated to check channel type (DM = always respond) and mention presence (public = require mention), then strips mentions from the text before forwarding to the agent.

**Tech Stack:** Python 3.13, `slack_sdk.web.async_client.AsyncWebClient`, `re`, `pytest`, `unittest.mock.AsyncMock`

---

## File Map

| Action | File | Responsibility |
| ------ | ---- | -------------- |
| Modify | `src/services/channel_service/slack_service.py` | All logic: settings, state, `initialize()`, helpers, `parse_event()` |
| Modify | `src/services/channel_service/__init__.py` | Make `init_channel_service` async; call `await svc.initialize()` |
| Modify | `src/main.py` | `await init_channel_service(...)` in lifespan |
| Modify | `tests/services/channel_service/test_slack_service.py` | Fix stale `_make_settings()`; update broken test; add new test cases |

---

## Task 1: Fix `_make_settings()`, add `bot_name` to `SlackSettings`, add state to `SlackService.__init__`

**Files:**

- Modify: `src/services/channel_service/slack_service.py`
- Test: `tests/services/channel_service/test_slack_service.py`

**Pre-check:** The existing `_make_settings()` helper in the test file passes `app_token` and `use_socket_mode` which are not in the current `SlackSettings` model (Pydantic rejects unknown fields). Remove them first.

In `tests/services/channel_service/test_slack_service.py`, replace the `_make_settings` function:

```python
def _make_settings(**kwargs):
    defaults = {
        "enabled": True,
        "bot_token": "xoxb-test",
        "signing_secret": "test-secret",
    }
    return SlackSettings(**(defaults | kwargs))
```

- [ ] **Step 1: Write the failing tests**

Add to `tests/services/channel_service/test_slack_service.py`:

```python
class TestSlackServiceInit:
    def test_bot_name_default_is_yuri(self):
        settings = _make_settings()
        assert settings.bot_name == "yuri"

    def test_bot_name_can_be_overridden(self):
        settings = _make_settings(bot_name="nari")
        assert settings.bot_name == "nari"

    def test_initial_bot_user_id_is_none(self):
        svc = SlackService(_make_settings())
        assert svc._bot_user_id is None

    def test_bot_name_stored_from_settings(self):
        svc = SlackService(_make_settings(bot_name="nari"))
        assert svc._bot_name == "nari"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/spow12/codes/2025_lower/DesktopMatePlus/backend
uv run pytest tests/services/channel_service/test_slack_service.py::TestSlackServiceInit -v
```

Expected: FAIL — `SlackSettings` has no `bot_name`, `SlackService` has no `_bot_user_id`/`_bot_name`

- [ ] **Step 3: Implement minimal changes**

In `src/services/channel_service/slack_service.py`:

```python
class SlackSettings(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    signing_secret: str = ""
    bot_name: str = "yuri"                    # ← add this
```

```python
class SlackService:
    def __init__(self, settings: SlackSettings) -> None:
        self._signing_secret = settings.signing_secret
        self._client = AsyncWebClient(token=settings.bot_token)
        self._bot_user_id: str | None = None   # ← add these two
        self._bot_name: str = settings.bot_name
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/services/channel_service/test_slack_service.py::TestSlackServiceInit -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/channel_service/slack_service.py tests/services/channel_service/test_slack_service.py
git commit -m "feat(slack): add bot_name to SlackSettings and state to SlackService"
```

---

## Task 2: Implement `SlackService.initialize()`

**Files:**

- Modify: `src/services/channel_service/slack_service.py`
- Test: `tests/services/channel_service/test_slack_service.py`

> **Note:** `asyncio_mode = "auto"` is set in `pyproject.toml` — no `@pytest.mark.asyncio` decorator needed on async test methods.

- [ ] **Step 1: Write the failing tests**

Add to `tests/services/channel_service/test_slack_service.py`:

```python
class TestSlackServiceInitialize:
    async def test_initialize_sets_bot_user_id_on_success(self):
        svc = SlackService(_make_settings())
        mock_client = MagicMock()
        mock_client.auth_test = AsyncMock(return_value={"user_id": "UBOTABC"})
        svc._client = mock_client

        await svc.initialize()

        assert svc._bot_user_id == "UBOTABC"

    async def test_initialize_leaves_bot_user_id_none_on_failure(self):
        svc = SlackService(_make_settings())
        mock_client = MagicMock()
        mock_client.auth_test = AsyncMock(side_effect=Exception("auth failed"))
        svc._client = mock_client

        await svc.initialize()  # must not raise

        assert svc._bot_user_id is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/services/channel_service/test_slack_service.py::TestSlackServiceInitialize -v
```

Expected: FAIL — `SlackService` has no `initialize()` method

- [ ] **Step 3: Implement `initialize()`**

Add to `SlackService` in `slack_service.py`:

```python
async def initialize(self) -> None:
    """Slack auth.test를 호출해 봇의 user_id를 가져온다.
    실패 시 경고만 기록하고 이름 기반 매칭으로 폴백한다.
    """
    try:
        result = await self._client.auth_test()
        self._bot_user_id = result["user_id"]
        logger.info(f"SlackService bot_user_id resolved: {self._bot_user_id}")
    except Exception as e:
        logger.warning(f"SlackService auth.test failed, falling back to name-only matching: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/services/channel_service/test_slack_service.py::TestSlackServiceInitialize -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/channel_service/slack_service.py tests/services/channel_service/test_slack_service.py
git commit -m "feat(slack): add initialize() to resolve bot user_id via auth.test"
```

---

## Task 3: Implement `_is_dm()`, `_is_mentioned()`, and `_clean_text()` helpers

**Files:**

- Modify: `src/services/channel_service/slack_service.py` (add `import re` at top — it is not currently imported)
- Test: `tests/services/channel_service/test_slack_service.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/services/channel_service/test_slack_service.py`:

```python
class TestSlackServiceHelpers:
    # _is_dm
    def test_is_dm_true_for_d_channel(self):
        svc = SlackService(_make_settings())
        assert svc._is_dm("D012AB3CD") is True

    def test_is_dm_false_for_c_channel(self):
        svc = SlackService(_make_settings())
        assert svc._is_dm("C012AB3CD") is False

    # _is_mentioned — user_id match
    def test_is_mentioned_true_for_native_user_id(self):
        svc = SlackService(_make_settings())
        svc._bot_user_id = "U12345"
        assert svc._is_mentioned("<@U12345> hello") is True

    def test_is_mentioned_false_for_other_user_id(self):
        svc = SlackService(_make_settings())
        svc._bot_user_id = "U12345"
        assert svc._is_mentioned("<@UOTHER> hello") is False

    # _is_mentioned — name match (case insensitive)
    def test_is_mentioned_true_for_at_name(self):
        svc = SlackService(_make_settings(bot_name="yuri"))
        assert svc._is_mentioned("hey @yuri what's up") is True

    def test_is_mentioned_true_for_at_name_uppercase(self):
        svc = SlackService(_make_settings(bot_name="yuri"))
        assert svc._is_mentioned("@YURI hello") is True

    def test_is_mentioned_false_for_bare_name(self):
        svc = SlackService(_make_settings(bot_name="yuri"))
        assert svc._is_mentioned("hello yuri") is False

    # _clean_text
    def test_clean_text_removes_native_mention(self):
        svc = SlackService(_make_settings())
        svc._bot_user_id = "U12345"
        assert svc._clean_text("<@U12345> please help") == "please help"

    def test_clean_text_removes_name_mention(self):
        svc = SlackService(_make_settings(bot_name="yuri"))
        assert svc._clean_text("@yuri what time is it") == "what time is it"

    def test_clean_text_removes_name_mention_case_insensitive(self):
        svc = SlackService(_make_settings(bot_name="yuri"))
        assert svc._clean_text("@YURI hello") == "hello"

    def test_clean_text_normalizes_extra_whitespace(self):
        svc = SlackService(_make_settings(bot_name="yuri"))
        svc._bot_user_id = "U12345"
        assert svc._clean_text("  <@U12345>   tell me  ") == "tell me"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/services/channel_service/test_slack_service.py::TestSlackServiceHelpers -v
```

Expected: FAIL — helpers don't exist yet

- [ ] **Step 3: Implement helpers**

Add `import re` after existing imports in `slack_service.py`. Add these methods to `SlackService`:

```python
def _is_dm(self, channel_id: str) -> bool:
    """Slack DM channel ID는 'D'로 시작한다."""
    return channel_id.startswith("D")

def _is_mentioned(self, text: str) -> bool:
    """텍스트에 봇에 대한 mention이 포함되어 있는지 확인한다."""
    if self._bot_user_id and re.search(rf"<@{re.escape(self._bot_user_id)}>", text):
        return True
    return bool(re.search(rf"(?i)@{re.escape(self._bot_name)}", text))

def _clean_text(self, text: str) -> str:
    """mention 태그를 제거하고 공백을 정규화한다."""
    if self._bot_user_id:
        text = re.sub(rf"<@{re.escape(self._bot_user_id)}>", "", text)
    text = re.sub(rf"(?i)@{re.escape(self._bot_name)}", "", text)
    return " ".join(text.split())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/services/channel_service/test_slack_service.py::TestSlackServiceHelpers -v
```

Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add src/services/channel_service/slack_service.py tests/services/channel_service/test_slack_service.py
git commit -m "feat(slack): add _is_dm, _is_mentioned, _clean_text helpers"
```

---

## Task 4: Update `parse_event()` with mention/DM filtering

**Files:**

- Modify: `src/services/channel_service/slack_service.py`
- Modify: `tests/services/channel_service/test_slack_service.py` (update existing test + add new ones)

> **Design note:** For DM channels, `_clean_text()` is intentionally not called — the spec only requires mention stripping when a mention is the gate condition (public channels). DMs pass through as-is.

- [ ] **Step 1: Update the broken existing test + write new failing tests**

The existing `test_returns_slack_message_for_valid_event` sends `"hello yuri"` to a public channel. After the new filtering this returns `None` (bare name is not a mention). **Replace** it and **add** new tests — all as methods inside the existing `TestParseEvent` class:

```python
# REPLACE test_returns_slack_message_for_valid_event with:
async def test_returns_slack_message_for_public_channel_with_name_mention(self):
    svc = SlackService(_make_settings(bot_name="yuri"))
    payload = {
        "type": "event_callback",
        "team_id": "T1",
        "event": {
            "type": "message",
            "text": "@yuri hello",
            "channel": "C1",
            "user": "U1",
        },
    }
    result = await svc.parse_event(payload)
    assert result is not None
    assert result.text == "hello"         # mention stripped
    assert result.channel_id == "C1"
    assert result.session_id == "slack:T1:C1:default"
    assert result.provider == "slack"

# ADD these new methods inside TestParseEvent:
async def test_returns_none_for_public_channel_without_mention(self):
    svc = SlackService(_make_settings(bot_name="yuri"))
    payload = {
        "type": "event_callback",
        "team_id": "T1",
        "event": {
            "type": "message",
            "text": "hello yuri",         # bare name — not a mention
            "channel": "C1",
            "user": "U1",
        },
    }
    result = await svc.parse_event(payload)
    assert result is None

async def test_returns_slack_message_for_dm_without_mention(self):
    svc = SlackService(_make_settings(bot_name="yuri"))
    payload = {
        "type": "event_callback",
        "team_id": "T1",
        "event": {
            "type": "message",
            "text": "hello there",
            "channel": "D012ABC",         # DM channel
            "user": "U1",
        },
    }
    result = await svc.parse_event(payload)
    assert result is not None
    assert result.text == "hello there"   # text unchanged in DMs

async def test_returns_slack_message_for_native_user_id_mention(self):
    svc = SlackService(_make_settings())
    svc._bot_user_id = "UBOTID"
    payload = {
        "type": "event_callback",
        "team_id": "T1",
        "event": {
            "type": "message",
            "text": "<@UBOTID> what's the weather?",
            "channel": "C1",
            "user": "U1",
        },
    }
    result = await svc.parse_event(payload)
    assert result is not None
    assert result.text == "what's the weather?"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/services/channel_service/test_slack_service.py::TestParseEvent -v
```

Expected: new tests FAIL — `parse_event` doesn't filter yet. Updated test also FAIL (text not cleaned).

- [ ] **Step 3: Update `parse_event()` implementation**

Replace the body of `parse_event()` in `slack_service.py`:

```python
async def parse_event(self, payload: dict) -> SlackMessage | None:
    """Webhook payload에서 메시지를 추출한다.

    - DM 채널: 항상 응답
    - 공개/그룹 채널: mention 있을 때만 응답
    - 무시할 이벤트(봇 메시지, 비메시지 이벤트 등): None 반환
    """
    event = payload.get("event", {})
    if event.get("type") != "message":
        return None
    if event.get("bot_id"):
        return None
    if event.get("subtype"):
        return None

    text = event.get("text", "").strip()
    channel_id = event.get("channel", "")
    team_id = payload.get("team_id", "")
    if not text or not channel_id or not team_id:
        return None

    # DM은 mention 없이도 항상 응답; 공개 채널은 mention 필요
    if not self._is_dm(channel_id):
        if not self._is_mentioned(text):
            return None
        text = self._clean_text(text)
        if not text:
            return None

    session_id = f"slack:{team_id}:{channel_id}:{STM_USER_ID}"
    return SlackMessage(
        session_id=session_id,
        channel_id=channel_id,
        provider="slack",
        text=text,
    )
```

- [ ] **Step 4: Run all `TestParseEvent` tests**

```bash
uv run pytest tests/services/channel_service/test_slack_service.py::TestParseEvent -v
```

Expected: PASS (all tests)

- [ ] **Step 5: Run all slack service tests to check for regressions**

```bash
uv run pytest tests/services/channel_service/test_slack_service.py -v
```

Expected: PASS (all tests)

- [ ] **Step 6: Commit**

```bash
git add src/services/channel_service/slack_service.py tests/services/channel_service/test_slack_service.py
git commit -m "feat(slack): filter parse_event to mention-only in public channels, always-on in DMs"
```

---

## Task 5: Wire `initialize()` into lifespan

**Files:**

- Modify: `src/services/channel_service/__init__.py`
- Modify: `src/main.py` (one line change only)

> **Note:** The existing `try/except` block wrapping channel service initialization in `main.py` (lines ~136–159) continues to handle any failures from `initialize()`. No changes are needed to error handling — only the `await` keyword is added.

- [ ] **Step 1: Make `init_channel_service` async and call `initialize()`**

In `src/services/channel_service/__init__.py`, change the function signature and add the `await` call:

```python
async def init_channel_service(settings: SlackSettings | None) -> None:
    """main.py lifespan에서 호출. SlackService 싱글톤을 초기화한다."""
    global _slack_service
    if settings and settings.enabled and settings.bot_token:
        _slack_service = SlackService(settings)
        await _slack_service.initialize()
        logger.info("SlackService initialized")
    else:
        logger.info("SlackService disabled (enabled=false or bot_token missing)")
```

- [ ] **Step 2: Update the call in `main.py`**

In `src/main.py`, find:

```python
init_channel_service(slack_settings)
```

Change it to:

```python
await init_channel_service(slack_settings)
```

- [ ] **Step 3: Run the full test suite**

```bash
uv run pytest tests/ -v --ignore=tests/api/test_real_e2e.py
```

Expected: PASS — no regressions

- [ ] **Step 4: Run lint**

```bash
sh scripts/lint.sh
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add src/services/channel_service/__init__.py src/main.py
git commit -m "feat(slack): wire SlackService.initialize() into lifespan startup"
```

---

## Done

All tasks complete. The bot now:

- Ignores messages in public/group channels unless mentioned via `@bot_name` or `<@BOT_USER_ID>`
- Always responds in DMs
- Strips mention from text before forwarding to the agent
- Resolves its own Slack user ID at startup via `auth.test`
