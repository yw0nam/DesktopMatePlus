from pydantic import BaseModel, Field


class DelegateTaskInput(BaseModel):
    """Input schema for delegating a task to NanoClaw."""

    task: str = Field(
        ...,
        description="A clear, actionable description of the task to delegate. Include all necessary context.",
    )
