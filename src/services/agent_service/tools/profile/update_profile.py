"""Tool for updating the user profile from conversation context."""

from typing import Annotated

from langchain_core.tools import BaseTool
from langgraph.prebuilt import InjectedState
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from src.services.user_profile_service.service import UserProfileService


class UpdateUserProfileInput(BaseModel):
    """Input schema for updating the user profile."""

    user_id: Annotated[str, InjectedState("user_id")]
    display_name: str | None = Field(
        default=None, description="User's display name or preferred name"
    )
    occupation: str | None = Field(
        default=None, description="User's occupation or job title"
    )
    interests: list[str] | None = Field(
        default=None, description="List of user's interests or hobbies"
    )
    preferences: dict[str, str] | None = Field(
        default=None, description="User preferences as key-value pairs"
    )
    timezone: str | None = Field(
        default=None, description="User's timezone (e.g. Asia/Seoul, UTC)"
    )
    notes: str | None = Field(
        default=None, description="Free-form notes about the user"
    )


class UpdateUserProfileTool(BaseTool):
    """Update the user's profile when new personal information is learned."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "update_user_profile"
    description: str = (
        "Update the user's profile when you learn new information about them "
        "(e.g. their job, interests, preferences, timezone). "
        "Only include fields you want to update."
    )
    args_schema: type[UpdateUserProfileInput] = UpdateUserProfileInput
    service: UserProfileService

    def _run(
        self,
        user_id: str,
        display_name: str | None = None,
        occupation: str | None = None,
        interests: list[str] | None = None,
        preferences: dict[str, str] | None = None,
        timezone: str | None = None,
        notes: str | None = None,
    ) -> str:
        partial: dict = {}
        if display_name is not None:
            partial["display_name"] = display_name
        if occupation is not None:
            partial["occupation"] = occupation
        if interests is not None:
            partial["interests"] = interests
        if preferences is not None:
            partial["preferences"] = preferences
        if timezone is not None:
            partial["timezone"] = timezone
        if notes is not None:
            partial["notes"] = notes

        if not partial:
            return "No fields to update."

        try:
            existing = self.service.get_profile(user_id)
            if existing is None:
                profile = self.service.upsert_profile(user_id, partial)
                logger.info(f"Created new profile for user={user_id}")
            else:
                profile = self.service.update_profile(user_id, partial)
                logger.info(f"Updated profile for user={user_id}: {list(partial)}")
        except Exception as e:
            logger.error(f"Profile update failed for user={user_id}: {e}")
            return f"Failed to update profile: {e}"

        if profile is None:
            return "Profile update failed."
        return f"Profile updated: {', '.join(partial)}"
