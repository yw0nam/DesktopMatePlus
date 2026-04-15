"""Proactive talking webhook endpoint."""

from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from loguru import logger

from src.models.proactive import ProactiveTriggerRequest, ProactiveTriggerResponse
from src.services.service_manager import get_proactive_service

router = APIRouter(prefix="/v1/proactive", tags=["Proactive"])


@router.post(
    "/trigger",
    response_model=ProactiveTriggerResponse,
    summary="Trigger proactive talk for a session",
    responses={
        200: {"description": "Trigger executed or skipped"},
        503: {"description": "Proactive service not available"},
    },
)
async def trigger_proactive(request: ProactiveTriggerRequest) -> JSONResponse:
    svc = get_proactive_service()
    if svc is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "skipped", "reason": "proactive service not available"},
        )

    # Find connection by session_id
    connection_id: UUID | None = None
    for cid, _conn in svc._ws_manager.connections.items():
        if str(cid) == request.session_id:
            connection_id = cid
            break

    if connection_id is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"status": "skipped", "reason": "session not found"},
        )

    logger.info(
        f"Proactive trigger: session={request.session_id} type={request.trigger_type}"
    )

    result = await svc.trigger_proactive(
        connection_id=connection_id,
        trigger_type=request.trigger_type,
        prompt_key=request.prompt_key,
        context=request.context,
    )

    return JSONResponse(status_code=status.HTTP_200_OK, content=result)
