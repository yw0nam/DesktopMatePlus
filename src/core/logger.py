"""Logging configuration for the application."""

import logging
import sys

from loguru import logger


def setup_json_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Configure loguru for JSON-structured logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, output JSON format; if False, use standard format
    """
    # Remove default handler
    logger.remove()

    if json_output:
        # Use loguru's built-in serialize for JSON output
        # This properly handles all record fields including extra
        logger.add(
            sys.stderr,
            level=level,
            serialize=True,  # Built-in JSON serialization
        )
    else:
        # Add standard formatter for development
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=level,
        )


def setup_logging(
    logger_name: str = "waifu_backend", level: int = logging.INFO
) -> logging.Logger:
    """Legacy logging setup for compatibility.

    This function is kept for backward compatibility but is deprecated.
    Use setup_json_logging() instead for new code.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # 핸들러가 이미 있으면 중복 방지
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
