"""User profile model for personalized conversations."""

from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator


class UserProfile(BaseModel):
    """Schema for user context profile."""

    user_id: str = Field(..., min_length=1, description="User identifier")
    display_name: str | None = Field(
        default=None, max_length=100, description="Display name"
    )
    occupation: str | None = Field(
        default=None, max_length=200, description="Occupation or job title"
    )
    interests: list[str] = Field(
        default_factory=list, max_length=50, description="List of user interests"
    )
    preferences: dict[str, str] = Field(
        default_factory=dict, description="User preferences as key-value pairs"
    )
    timezone: str | None = Field(
        default=None, max_length=50, description="User timezone (e.g. Asia/Seoul)"
    )
    notes: str | None = Field(
        default=None, max_length=2000, description="Free-form notes about the user"
    )

    @field_validator("interests")
    @classmethod
    def validate_interest_lengths(cls, v: list[str]) -> list[str]:
        """Ensure each interest string does not exceed 100 characters."""
        for item in v:
            if len(item) > 100:
                raise ValueError(
                    f"Each interest must be at most 100 characters, got {len(item)}"
                )
        return v
