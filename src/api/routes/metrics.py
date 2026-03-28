"""Prometheus metrics endpoint."""

from fastapi import APIRouter
from fastapi.responses import Response

from src.core.metrics import get_metrics

router = APIRouter(tags=["Metrics"])


@router.get(
    "/metrics",
    summary="Prometheus metrics endpoint",
    status_code=200,
    responses={200: {"description": "Prometheus text format metrics"}},
)
async def metrics() -> Response:
    """Expose Prometheus metrics in text format."""
    data, content_type = get_metrics()
    return Response(content=data, media_type=content_type)
