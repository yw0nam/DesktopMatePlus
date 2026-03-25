"""Slack Events API webhook route."""

import asyncio

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from loguru import logger

from src.services import get_agent_service, get_ltm_service
from src.services.channel_service import get_slack_service, process_message

router = APIRouter(prefix="/v1/channels/slack", tags=["Slack"])


@router.post(
    "/events",
    summary="Receive Slack Events API webhook",
    status_code=status.HTTP_200_OK,
    responses={
        403: {"description": "Invalid Slack signature"},
        503: {"description": "Slack service not initialized"},
    },
)
async def slack_events(request: Request) -> JSONResponse:
    """Slack Events API webhook 수신 엔드포인트.

    - URL verification challenge에 즉시 응답한다.
    - 유효한 메시지 이벤트는 백그라운드로 process_message()를 실행하고 즉시 200을 반환한다.
    """
    slack = get_slack_service()
    if slack is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack service not initialized",
        )

    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")
    timestamp = request.headers.get("x-slack-request-timestamp", "")
    signature = request.headers.get("x-slack-signature", "")

    if not slack.verify_signature(
        body=body_str, timestamp=timestamp, signature=signature
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature"
        )

    payload: dict = await request.json()

    # URL verification (Slack 앱 등록 시 1회)
    if payload.get("type") == "url_verification":
        return JSONResponse(content={"challenge": payload["challenge"]})

    # 메시지 파싱 (봇 메시지, 비관련 이벤트는 None)
    msg = await slack.parse_event(payload)
    if msg is None:
        return JSONResponse(content={"ok": True})

    # 즉시 200 반환, 실제 처리는 백그라운드
    agent_service = get_agent_service()
    ltm = get_ltm_service()

    asyncio.create_task(
        process_message(
            text=msg.text,
            session_id=msg.session_id,
            provider=msg.provider,
            channel_id=msg.channel_id,
            agent_service=agent_service,
            ltm=ltm,
        )
    )

    logger.info(f"Slack event queued for session {msg.session_id}")
    return JSONResponse(content={"ok": True})
