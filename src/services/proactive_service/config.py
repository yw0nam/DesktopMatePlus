"""Configuration models for the ProactiveService."""

from pydantic import BaseModel, Field


class ScheduleEntry(BaseModel):
    id: str = Field(..., description="Unique schedule identifier")
    cron: str = Field(..., description="Cron expression")
    prompt_key: str = Field(..., description="Key in proactive_prompts.yml")
    enabled: bool = Field(default=True)


class ProactiveConfig(BaseModel):
    idle_timeout_seconds: int = Field(default=300, ge=1)
    cooldown_seconds: int = Field(default=600, ge=0)
    watcher_interval_seconds: int = Field(default=30, ge=1)
    schedules: list[ScheduleEntry] = Field(default_factory=list)
