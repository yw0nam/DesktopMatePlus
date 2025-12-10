"""LTM (Long-Term Memory) API routes."""

from fastapi import APIRouter, HTTPException, status
from langchain_core.messages import convert_to_messages
from loguru import logger

from src.models.ltm import (
    AddMemoryRequest,
    AddMemoryResponse,
    DeleteMemoryRequest,
    DeleteMemoryResponse,
    SearchMemoryRequest,
    SearchMemoryResponse,
)
from src.services import get_ltm_service

router = APIRouter(prefix="/v1/ltm", tags=["LTM"])


@router.post(
    "/add_memory",
    response_model=AddMemoryResponse,
    summary="Add memory to LTM",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Memory added successfully",
            "model": AddMemoryResponse,
        },
        400: {
            "description": "Invalid input",
            "content": {
                "application/json": {"example": {"detail": "Invalid memory format"}}
            },
        },
        500: {
            "description": "LTM service error",
            "content": {
                "application/json": {"example": {"detail": "Error adding memory: ..."}}
            },
        },
        503: {
            "description": "LTM service not initialized",
            "content": {
                "application/json": {
                    "example": {"detail": "LTM service not initialized"}
                }
            },
        },
    },
)
async def add_memory(request: AddMemoryRequest) -> AddMemoryResponse:
    """Add memory to Long-Term Memory storage.

    This endpoint accepts memory content (either as a list of role-content dicts
    or a plain string) and stores it in LTM associated with the given user and agent.

    Args:
        request: Add memory request containing user_id, agent_id, and memory_dict

    Returns:
        AddMemoryResponse: Success status and confirmation message

    Raises:
        HTTPException: If LTM service is not initialized or processing fails
    """
    ltm_service = get_ltm_service()

    if ltm_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LTM service not initialized",
        )

    try:
        # Convert memory_dict to LangChain messages
        if isinstance(request.memory_dict, list):
            # Convert Pydantic models to dicts for langchain
            messages = convert_to_messages(
                [
                    {"role": msg.role, "content": msg.content}
                    for msg in request.memory_dict
                ]
            )
        elif isinstance(request.memory_dict, str):
            messages = convert_to_messages(
                [{"role": "user", "content": request.memory_dict}]
            )
        else:
            raise ValueError("memory_dict must be either a list of dicts or a string.")

        # Add memory using LTM service
        result = ltm_service.add_memory(
            messages=messages,
            user_id=request.user_id,
            agent_id=request.agent_id,
        )

        # Check for errors in result
        if isinstance(result, dict) and "error" in result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error adding memory: {result['error']}",
            )

        logger.info(f"Memory added: user={request.user_id}, agent={request.agent_id}")

        return AddMemoryResponse(
            success=True,
            message="Memory added successfully.",
            result=result if isinstance(result, dict) else {},
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid memory format: {e}",
        ) from e
    except Exception as e:
        logger.error(f"Error adding memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding memory: {e}",
        ) from e


@router.post(
    "/search_memory",
    response_model=SearchMemoryResponse,
    summary="Search memories in LTM",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Search completed successfully",
            "model": SearchMemoryResponse,
        },
        500: {
            "description": "LTM service error",
            "content": {
                "application/json": {
                    "example": {"detail": "Error searching memories: ..."}
                }
            },
        },
        503: {
            "description": "LTM service not initialized",
            "content": {
                "application/json": {
                    "example": {"detail": "LTM service not initialized"}
                }
            },
        },
    },
)
async def search_memory(request: SearchMemoryRequest) -> SearchMemoryResponse:
    """Search memories in Long-Term Memory storage.

    Performs semantic search on memories associated with the given user and agent.

    Args:
        request: Search request containing user_id, agent_id, query, and optional limit

    Returns:
        SearchMemoryResponse: Success status and list of matching memories

    Raises:
        HTTPException: If LTM service is not initialized or search fails
    """
    ltm_service = get_ltm_service()

    if ltm_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LTM service not initialized",
        )

    try:
        # Search memories using LTM service
        result = ltm_service.search_memory(
            query=request.query,
            user_id=request.user_id,
            agent_id=request.agent_id,
        )

        # Check for errors in result
        if isinstance(result, dict) and "error" in result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error searching memories: {result['error']}",
            )

        logger.info(
            f"Memory search: query='{request.query}', user={request.user_id}, limit={request.limit}"
        )

        return SearchMemoryResponse(
            success=True,
            result=result if isinstance(result, dict) else {},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching memories: {e}",
        ) from e


@router.delete(
    "/delete_memory",
    response_model=DeleteMemoryResponse,
    summary="Delete memory from LTM",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Memory deleted successfully",
            "model": DeleteMemoryResponse,
        },
        404: {
            "description": "Memory not found",
            "content": {
                "application/json": {"example": {"detail": "Memory not found"}}
            },
        },
        500: {
            "description": "LTM service error",
            "content": {
                "application/json": {
                    "example": {"detail": "Error deleting memory: ..."}
                }
            },
        },
        503: {
            "description": "LTM service not initialized",
            "content": {
                "application/json": {
                    "example": {"detail": "LTM service not initialized"}
                }
            },
        },
    },
)
async def delete_memory(request: DeleteMemoryRequest) -> DeleteMemoryResponse:
    """Delete a memory from Long-Term Memory storage.

    Deletes a specific memory by its ID.

    Args:
        request: Delete request containing user_id, agent_id, and memory_id

    Returns:
        DeleteMemoryResponse: Success status and confirmation message

    Raises:
        HTTPException: If LTM service is not initialized or deletion fails
    """
    ltm_service = get_ltm_service()

    if ltm_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LTM service not initialized",
        )

    try:
        # Delete memory using LTM service
        result = ltm_service.delete_memory(
            user_id=request.user_id,
            agent_id=request.agent_id,
            memory_id=request.memory_id,
        )

        # Check for errors in result
        if isinstance(result, dict) and "error" in result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error deleting memory: {result['error']}",
            )

        logger.info(f"Memory deleted: id={request.memory_id}, user={request.user_id}")

        return DeleteMemoryResponse(
            success=True,
            message="Memory deleted successfully.",
            result=result if isinstance(result, dict) else {},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting memory: {e}",
        ) from e
