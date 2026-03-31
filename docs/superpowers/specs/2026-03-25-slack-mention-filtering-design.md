# Design Spec: Robust Slack Mention Filtering

**Status:** Draft
**Author:** Gemini CLI
**Date:** 2026-03-25

## 1. Overview
Currently, the Slack integration responds to every message in every channel where the bot is present. This design introduces a filtering mechanism to ensure the bot only responds when explicitly mentioned (e.g., `@yuri` or `<@U12345678>`) in public/group channels, while maintaining always-on responses in Direct Messages (DMs).

## 2. Requirements
- **Mention-Based Trigger:** In public channels and group chats, the bot must only respond if mentioned.
- **Case-Insensitivity:** Mentions like `@yuri`, `@Yuri`, and `@YURI` must all work.
- **Slack Native Mentions:** Support for Slack's internal `<@USER_ID>` format is mandatory.
- **DM Exception:** In Direct Messages (DMs), the bot should always respond to every message without requiring a mention.
- **Text Cleaning:** Mentions should be stripped from the message before it is sent to the AI agent to keep the context clean.
- **Dynamic Identification:** The bot should automatically discover its own User ID to accurately match native mentions.

## 3. Architecture & Components

### 3.1 `SlackSettings` Update
Add a `bot_name` field to allow configuration of the persona name used in text mentions.
- `bot_name: str = "yuri"`

### 3.2 `SlackService` Enhancements
- **State:** Add `self._bot_user_id: str | None = None` and `self._bot_name: str` to the class.
- **`initialize()` method:** An async method to call `auth.test` via the Slack WebClient and store the `user_id`.
- **`parse_event()` update:**
    - Detect channel type (DMs usually start with 'D').
    - Check for mentions using both the `_bot_user_id` and `_bot_name`.
    - Implement a `_clean_text()` helper using regex to remove mentions and normalize whitespace.

### 3.3 Lifespan Management
Update `src/main.py` to ensure `SlackService.initialize()` is called after the service is instantiated.

## 4. Data Flow
1. **Slack Webhook** receives an event.
2. **`SlackService.parse_event(payload)`** is called:
    - If channel type is DM -> Proceed.
    - If mention found (`<@BOT_ID>` or `@bot_name`) -> Proceed.
    - Else -> Return `None` (ignore).
3. If proceeding, **`_clean_text()`** strips the mention.
4. **`process_message()`** receives the cleaned text and proceeds with agent execution.

## 5. Regex Patterns
- **User Mention:** `<@U[A-Z0-9]+>`
- **Name Mention:** `(?i)@yuri` (where "yuri" is dynamic from config)

## 6. Error Handling
- If `auth.test` fails during initialization, log a warning and fall back to name-based matching only (or log a critical error if the bot cannot function).
- If the regex fails to match but the initial check passed, ensure the original text is still passed to avoid losing the user's message.

## 7. Testing Strategy
- **Unit Tests for `SlackService`:**
    - Test `parse_event` with/without mentions in different channel types.
    - Test `_clean_text` with various mention formats and whitespace.
- **Integration Test:**
    - Mock the Slack `auth.test` call and verify the initialization flow.
