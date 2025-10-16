"""Configuration for the PostgreSQL-backed vocabulary database."""

import os
from typing import Dict


def _env(key: str, default: str) -> str:
    value = os.getenv(key)
    return value if value is not None else default


VOCABULARY_DB_CONFIG: Dict[str, str] = {
    "host": _env("VOCABULARY_DB_HOST", "localhost"),
    "database": _env("VOCABULARY_DB_NAME", "memory_system_dev"),
    "user": _env("VOCABULARY_DB_USER", "memory_system"),
    "password": _env("VOCABULARY_DB_PASSWORD", "memory_system"),
    "port": _env("VOCABULARY_DB_PORT", "5432"),
}
