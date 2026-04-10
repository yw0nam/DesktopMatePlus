"""Tests for UpdateUserProfileTool."""

from unittest.mock import MagicMock

import pytest

from src.models.user_profile import UserProfile
from src.services.agent_service.tools.profile.update_profile import (
    UpdateUserProfileTool,
)
from src.services.user_profile_service.service import UserProfileService


@pytest.fixture
def mock_svc():
    return MagicMock(spec=UserProfileService)


@pytest.fixture
def tool(mock_svc):
    return UpdateUserProfileTool(service=mock_svc)


def test_creates_profile_when_not_found(tool, mock_svc):
    mock_svc.get_profile.return_value = None
    mock_svc.upsert_profile.return_value = UserProfile(
        user_id="u1", occupation="Engineer"
    )
    result = tool._run(user_id="u1", occupation="Engineer")
    mock_svc.upsert_profile.assert_called_once_with("u1", {"occupation": "Engineer"})
    assert "occupation" in result


def test_updates_profile_when_exists(tool, mock_svc):
    existing = UserProfile(user_id="u1", display_name="Alice")
    updated = UserProfile(user_id="u1", display_name="Alice", occupation="Designer")
    mock_svc.get_profile.return_value = existing
    mock_svc.update_profile.return_value = updated
    result = tool._run(user_id="u1", occupation="Designer")
    mock_svc.update_profile.assert_called_once_with("u1", {"occupation": "Designer"})
    assert "occupation" in result


def test_returns_no_fields_message_when_empty(tool, mock_svc):
    result = tool._run(user_id="u1")
    assert result == "No fields to update."
    mock_svc.get_profile.assert_not_called()


def test_only_sends_non_none_fields(tool, mock_svc):
    existing = UserProfile(user_id="u1")
    mock_svc.get_profile.return_value = existing
    mock_svc.update_profile.return_value = UserProfile(
        user_id="u1", timezone="UTC", interests=["cycling"]
    )
    tool._run(user_id="u1", timezone="UTC", interests=["cycling"])
    call_args = mock_svc.update_profile.call_args[0]
    assert "display_name" not in call_args[1]
    assert call_args[1]["timezone"] == "UTC"
    assert call_args[1]["interests"] == ["cycling"]


def test_returns_failure_when_update_returns_none(tool, mock_svc):
    existing = UserProfile(user_id="u1")
    mock_svc.get_profile.return_value = existing
    mock_svc.update_profile.return_value = None
    result = tool._run(user_id="u1", notes="test")
    assert "failed" in result.lower()
