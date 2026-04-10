"""Profile middleware — pre-hook to inject user context before model call.

Wired in openai_chat_agent.py via:
  before_model(profile_retrieve_hook) — inject user profile before each model call
"""

import asyncio

from langchain_core.messages import SystemMessage
from loguru import logger

from src.services.service_manager import get_user_profile_service

_PROFILE_SECTION_HEADER = "\n\nUser Profile:"


async def profile_retrieve_hook(state, runtime):
    """Load user profile and inject as SystemMessage context before the model call."""
    svc = get_user_profile_service()
    if not svc:
        return None

    user_id = state.get("user_id", "")
    if not user_id:
        return None

    try:
        profile = await asyncio.to_thread(svc.get_profile, user_id)
    except Exception as e:
        logger.error(f"Profile retrieve failed (user={user_id}): {e}")
        return None

    if profile is None:
        return None

    # Build profile section only if there is meaningful data
    parts: list[str] = []
    if profile.display_name:
        parts.append(f"Name: {profile.display_name}")
    if profile.occupation:
        parts.append(f"Occupation: {profile.occupation}")
    if profile.interests:
        parts.append(f"Interests: {', '.join(profile.interests)}")
    if profile.preferences:
        prefs = ", ".join(f"{k}={v}" for k, v in profile.preferences.items())
        parts.append(f"Preferences: {prefs}")
    if profile.timezone:
        parts.append(f"Timezone: {profile.timezone}")
    if profile.notes:
        parts.append(f"Notes: {profile.notes}")

    if not parts:
        return None

    profile_section = _PROFILE_SECTION_HEADER + " " + "; ".join(parts)

    msgs = state.get("messages", [])
    if (
        msgs
        and isinstance(msgs[0], SystemMessage)
        and isinstance(msgs[0].content, str)
        and msgs[0].id
    ):
        # Strip any existing profile section and re-inject with latest data
        base_content = msgs[0].content.split(_PROFILE_SECTION_HEADER)[0]
        return {
            "messages": [
                SystemMessage(
                    id=msgs[0].id,
                    content=f"{base_content}{profile_section}",
                )
            ],
            "user_profile_loaded": True,
        }

    return None
