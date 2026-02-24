"""Main Long-Term Memory configuration."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .mem0 import Mem0LongTermMemoryConfig


class MemoryConfig(BaseModel):
    """최종 메모리 설정"""

    memory_type: Literal["mem0"] = Field("mem0", description="사용할 메모리 유형")
    mem0: Optional[Mem0LongTermMemoryConfig] = Field(
        default_factory=Mem0LongTermMemoryConfig,
        description="Mem0 Long-Term Memory 설정",
    )
