from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AddMemoryInput(BaseModel):
    """Input schema for adding a memory."""

    content: str = Field(
        ...,
        description="The actual content or text of the memory to be stored. This should be a clear and concise piece of information.",
    )
    # metadata: Optional[Dict[str, Any]] = Field(
    #     default=None,
    #     description="Optional key-value pairs that provide additional context or allow for structured filtering during search (e.g., {'source': 'email', 'project_id': 'proj-123'}).",
    # )


class SearchMemoryInput(BaseModel):
    """Input schema for searching memories."""

    query: str = Field(
        ...,
        description="The natural language query to search for relevant memories. This should be a question or a statement describing the information needed.",
    )
    limit: Optional[int] = Field(
        default=5,
        description="The maximum number of memory results to return. Defaults to 5 to avoid overwhelming the context window.",
    )
    # metadata_filter: Optional[Dict[str, Any]] = Field(
    #     default=None,
    #     description="A dictionary to filter memories based on their metadata. Only memories matching all key-value pairs will be returned.",
    # )


class DeleteMemoryInput(BaseModel):
    """Input schema for deleting a memory."""

    memory_id: str = Field(
        ...,
        description="The unique ID of the memory to be permanently deleted. This action is irreversible.",
    )


class UpdateMemoryInput(BaseModel):
    """Input schema for updating an existing memory."""

    memory_id: str = Field(
        ...,
        description="The unique ID of the memory to be updated. This ID is typically obtained from a prior search result.",
    )
    payload: Dict[str, Any] = Field(
        ...,
        description="A dictionary containing the fields to be updated. For example, to update the content, use {'content': 'new updated text'}.",
    )
