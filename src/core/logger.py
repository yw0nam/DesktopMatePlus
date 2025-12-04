"""Logging configuration for the application."""

import logging
import os
import sys
from pathlib import Path

from loguru import logger


def setup_json_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Configure loguru for JSON-structured logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, output JSON format; if False, use standard format
    """
    # Remove default handler
    logger.remove()

    # 로그 파일 경로 설정 (환경 변수 또는 기본값)
    log_file = os.getenv("LOG_FILE", "logs/app.log")
    log_dir = Path(log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    if json_output:
        # 콘솔 출력
        logger.add(
            sys.stderr,
            level=level,
            serialize=True,  # Built-in JSON serialization
        )
        # 파일 출력
        logger.add(
            log_file,
            level=level,
            serialize=True,
            rotation="10 MB",  # 파일 크기가 10MB 넘으면 회전
            retention="1 week",  # 1주일 후 삭제
        )
    else:
        # Add standard formatter for development
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=level,
        )
        # 파일 출력
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            level=level,
            rotation="10 MB",
            retention="1 week",
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
