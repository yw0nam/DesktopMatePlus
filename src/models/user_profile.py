"""User profile model for personalized conversations."""

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """Schema for user context profile."""

    user_id: str = Field(..., min_length=1, description="User identifier")
    display_name: str | None = Field(default=None, description="Display name")
    occupation: str | None = Field(default=None, description="Occupation or job title")
    interests: list[str] = Field(
        default_factory=list, description="List of user interests"
    )
    preferences: dict[str, str] = Field(
        default_factory=dict, description="User preferences as key-value pairs"
    )
    timezone: str | None = Field(
        default=None, description="User timezone (e.g. Asia/Seoul)"
    )
    notes: str | None = Field(
        default=None, description="Free-form notes about the user"
    )
