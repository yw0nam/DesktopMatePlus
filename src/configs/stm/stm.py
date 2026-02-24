"""Main Short-Term Memory configuration."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .mongodb import MongoDBShortTermMemoryConfig


class STMConfig(BaseModel):
    """Short Memory Configuration Class"""

    short_term_memory_type: Literal["mongodb"] = Field(
        "mongodb", description="사용할 메모리 유형"
    )
    # TODO: Add other short-term memory configs here At first, add MongoDB

    mongodb: Optional[MongoDBShortTermMemoryConfig] = Field(
        default_factory=MongoDBShortTermMemoryConfig,
        description="MongoDB STM 설정",
    )
