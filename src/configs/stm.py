from typing import Literal, Optional

from pydantic import BaseModel, Field


class MongoDBShortTermMemory(BaseModel):
    """Configure MongoDB as Short-Term Memory"""

    pass


class STMConfig(BaseModel):
    """Short Memory Configuration Class"""

    short_term_memory_type: Literal["mongodb"] = Field(
        "mongodb", description="사용할 메모리 유형"
    )
    # TODO: Add other short-term memory configs here At first, add MongoDB

    mongodb: Optional[MongoDBShortTermMemory] = Field(
        default_factory=MongoDBShortTermMemory,
        description="MongoDB 체크포인트 설정",
    )
