"""Prometheus metrics definitions for the DesktopMate+ backend."""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["endpoint"],
)
ACTIVE_CONNECTIONS = Gauge(
    "websocket_active_connections",
    "Active WebSocket connections",
)


def get_metrics() -> tuple[bytes, str]:
    """Generate latest Prometheus metrics.

    Returns:
        Tuple of (metrics data bytes, content type string).
    """
    return generate_latest(), CONTENT_TYPE_LATEST
