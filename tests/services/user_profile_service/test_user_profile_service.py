"""Tests for UserProfileService CRUD operations."""

from unittest.mock import MagicMock

import pytest

from src.models.user_profile import UserProfile
from src.services.user_profile_service.service import UserProfileService


@pytest.fixture
def mock_collection():
    return MagicMock()


@pytest.fixture
def service(mock_collection):
    return UserProfileService(collection=mock_collection)


class TestGetProfile:
    def test_returns_profile_when_found(self, service, mock_collection):
        mock_collection.find_one.return_value = {
            "user_id": "user_1",
            "display_name": "Alice",
            "occupation": "Engineer",
            "interests": ["music", "hiking"],
            "preferences": {"language": "ko"},
            "timezone": "Asia/Seoul",
            "notes": "Prefers concise replies",
        }
        result = service.get_profile("user_1")
        assert result is not None
        assert isinstance(result, UserProfile)
        assert result.user_id == "user_1"
        assert result.display_name == "Alice"
        assert result.interests == ["music", "hiking"]

    def test_returns_none_when_not_found(self, service, mock_collection):
        mock_collection.find_one.return_value = None
        result = service.get_profile("unknown_user")
        assert result is None

    def test_queries_by_user_id(self, service, mock_collection):
        mock_collection.find_one.return_value = None
        service.get_profile("user_42")
        mock_collection.find_one.assert_called_once_with(
            {"user_id": "user_42"}, {"_id": 0}
        )


class TestUpsertProfile:
    def test_returns_userprofile_with_given_data(self, service, mock_collection):
        result = service.upsert_profile(
            "user_1", {"display_name": "Bob", "interests": ["coding"]}
        )
        assert isinstance(result, UserProfile)
        assert result.user_id == "user_1"
        assert result.display_name == "Bob"

    def test_calls_replace_one_with_upsert(self, service, mock_collection):
        service.upsert_profile("user_1", {"occupation": "Designer"})
        mock_collection.replace_one.assert_called_once()
        call_args = mock_collection.replace_one.call_args
        assert call_args[0][0] == {"user_id": "user_1"}
        assert call_args[1]["upsert"] is True

    def test_stored_document_contains_user_id(self, service, mock_collection):
        service.upsert_profile("user_5", {"display_name": "Carol"})
        stored_doc = mock_collection.replace_one.call_args[0][1]
        assert stored_doc["user_id"] == "user_5"


class TestUpdateProfile:
    def test_returns_updated_profile_when_found(self, service, mock_collection):
        mock_collection.find_one_and_update.return_value = {
            "user_id": "user_1",
            "display_name": "Alice",
            "occupation": "Architect",
            "interests": [],
            "preferences": {},
            "timezone": None,
            "notes": None,
        }
        result = service.update_profile("user_1", {"occupation": "Architect"})
        assert result is not None
        assert result.occupation == "Architect"

    def test_returns_none_when_not_found(self, service, mock_collection):
        mock_collection.find_one_and_update.return_value = None
        result = service.update_profile("missing_user", {"occupation": "Dev"})
        assert result is None

    def test_calls_set_with_partial(self, service, mock_collection):
        mock_collection.find_one_and_update.return_value = None
        service.update_profile("user_1", {"notes": "test note"})
        call_args = mock_collection.find_one_and_update.call_args
        assert call_args[0][1] == {"$set": {"notes": "test note"}}
