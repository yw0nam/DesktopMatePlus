"""Tests for profile_retrieve_hook middleware."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from src.models.user_profile import UserProfile


@pytest.fixture
def profile():
    return UserProfile(
        user_id="user_1",
        display_name="Alice",
        occupation="Engineer",
        interests=["music", "hiking"],
        preferences={"language": "ko"},
        timezone="Asia/Seoul",
        notes=None,
    )


@pytest.fixture
def state_with_system(profile):
    return {
        "user_id": "user_1",
        "agent_id": "agent_1",
        "messages": [
            SystemMessage(id="sys-001", content="You are Yuri."),
            HumanMessage(content="Hello"),
        ],
    }


@pytest.mark.asyncio
async def test_injects_profile_into_system_message(profile, state_with_system):
    mock_svc = MagicMock()
    mock_svc.get_profile.return_value = profile

    with patch(
        "src.services.agent_service.middleware.profile_middleware.get_user_profile_service",
        return_value=mock_svc,
    ):
        from src.services.agent_service.middleware.profile_middleware import (
            profile_retrieve_hook,
        )

        result = await profile_retrieve_hook(state_with_system, runtime=None)

    assert result is not None
    updated_msg = result["messages"][0]
    assert isinstance(updated_msg, SystemMessage)
    assert "Alice" in updated_msg.content
    assert "Engineer" in updated_msg.content
    assert "music" in updated_msg.content
    assert updated_msg.id == "sys-001"
    assert result["user_profile_loaded"] is True


@pytest.mark.asyncio
async def test_returns_none_when_no_service():
    with patch(
        "src.services.agent_service.middleware.profile_middleware.get_user_profile_service",
        return_value=None,
    ):
        from src.services.agent_service.middleware.profile_middleware import (
            profile_retrieve_hook,
        )

        result = await profile_retrieve_hook(
            {"user_id": "u1", "messages": []}, runtime=None
        )
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_when_no_user_id():
    mock_svc = MagicMock()
    with patch(
        "src.services.agent_service.middleware.profile_middleware.get_user_profile_service",
        return_value=mock_svc,
    ):
        from src.services.agent_service.middleware.profile_middleware import (
            profile_retrieve_hook,
        )

        result = await profile_retrieve_hook(
            {"user_id": "", "messages": []}, runtime=None
        )
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_when_profile_not_found(state_with_system):
    mock_svc = MagicMock()
    mock_svc.get_profile.return_value = None
    with patch(
        "src.services.agent_service.middleware.profile_middleware.get_user_profile_service",
        return_value=mock_svc,
    ):
        from src.services.agent_service.middleware.profile_middleware import (
            profile_retrieve_hook,
        )

        result = await profile_retrieve_hook(state_with_system, runtime=None)
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_when_profile_empty():
    empty_profile = UserProfile(user_id="user_1")
    mock_svc = MagicMock()
    mock_svc.get_profile.return_value = empty_profile
    state = {
        "user_id": "user_1",
        "messages": [SystemMessage(id="sys-001", content="You are Yuri.")],
    }
    with patch(
        "src.services.agent_service.middleware.profile_middleware.get_user_profile_service",
        return_value=mock_svc,
    ):
        from src.services.agent_service.middleware.profile_middleware import (
            profile_retrieve_hook,
        )

        result = await profile_retrieve_hook(state, runtime=None)
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_when_no_system_message_with_id(profile):
    mock_svc = MagicMock()
    mock_svc.get_profile.return_value = profile
    state = {
        "user_id": "user_1",
        "messages": [HumanMessage(content="Hello")],
    }
    with patch(
        "src.services.agent_service.middleware.profile_middleware.get_user_profile_service",
        return_value=mock_svc,
    ):
        from src.services.agent_service.middleware.profile_middleware import (
            profile_retrieve_hook,
        )

        result = await profile_retrieve_hook(state, runtime=None)
    assert result is None


@pytest.mark.asyncio
async def test_preserves_existing_system_message_base(profile, state_with_system):
    mock_svc = MagicMock()
    mock_svc.get_profile.return_value = profile
    with patch(
        "src.services.agent_service.middleware.profile_middleware.get_user_profile_service",
        return_value=mock_svc,
    ):
        from src.services.agent_service.middleware.profile_middleware import (
            profile_retrieve_hook,
        )

        result = await profile_retrieve_hook(state_with_system, runtime=None)
    assert result is not None
    assert "You are Yuri." in result["messages"][0].content
