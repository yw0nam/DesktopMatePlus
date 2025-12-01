"""LTM (Long-Term Memory) API request and response models."""

from typing import Any, Union

from pydantic import BaseModel, Field


class MemoryMessageDict(BaseModel):
    """Model for a single memory message in role-content format."""

    role: str = Field(
        ...,
        description="Role of the message sender (user, assistant, system)",
    )
    content: str = Field(
        ...,
        description="Content of the message",
    )


class AddMemoryRequest(BaseModel):
    """Request model for adding memory to LTM."""

    user_id: str = Field(
        ...,
        description="User identifier",
        min_length=1,
    )
    agent_id: str = Field(
        ...,
        description="Agent identifier",
        min_length=1,
    )
    memory_dict: Union[list[MemoryMessageDict], str] = Field(
        ...,
        description="Memory content - either a list of role-content dicts or a plain string",
    )


class AddMemoryResponse(BaseModel):
    """Response model for adding memory to LTM.

    Returns the raw result from the LTM service implementation.
    The structure may vary depending on the LTM backend (e.g., Mem0).
    """

    success: bool = Field(
        ...,
        description="Whether the operation was successful",
    )
    message: str = Field(
        ...,
        description="Status message",
    )
    result: dict[str, Any] = Field(
        default={},
        description="Raw result from the LTM service. "
        "Typically contains 'results' (list of memory items) and 'relations' (list of relations) keys.",
    )


class SearchMemoryRequest(BaseModel):
    """Request model for searching memories in LTM."""

    user_id: str = Field(
        ...,
        description="User identifier",
        min_length=1,
    )
    agent_id: str = Field(
        ...,
        description="Agent identifier",
        min_length=1,
    )
    query: str = Field(
        ...,
        description="Search query string",
        min_length=1,
    )


class SearchMemoryResponse(BaseModel):
    """Response model for searching memories in LTM.

    Returns the raw result from the LTM service implementation.
    The structure may vary depending on the LTM backend (e.g., Mem0).
    """

    success: bool = Field(
        ...,
        description="Whether the operation was successful",
    )
    result: dict[str, Any] = Field(
        default={},
        description="Raw result from the LTM service. "
        "Typically contains 'results' (list of memory items) and 'relations' (list of relations) keys.",
    )


class DeleteMemoryRequest(BaseModel):
    """Request model for deleting a memory from LTM."""

    user_id: str = Field(
        ...,
        description="User identifier",
        min_length=1,
    )
    agent_id: str = Field(
        ...,
        description="Agent identifier",
        min_length=1,
    )
    memory_id: str = Field(
        ...,
        description="ID of the memory to delete",
        min_length=1,
    )


class DeleteMemoryResponse(BaseModel):
    """Response model for deleting a memory from LTM."""

    success: bool = Field(
        ...,
        description="Whether the operation was successful",
    )
    message: str = Field(
        ...,
        description="Status message",
    )
    result: dict[str, Any] = Field(
        default={},
        description="Raw result from the LTM service",
    )
