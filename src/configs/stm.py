from typing import Literal, Optional

from pydantic import BaseModel, Field


class MongoDBShortTermMemory(BaseModel):
    """Configure MongoDB as Short-Term Memory"""

    connection_string: str = Field(
        default="mongodb://admin:test@localhost:27017/",
        description="MongoDB connection string",
    )
    database_name: str = Field(
        default="desktopmate_db", description="MongoDB database name"
    )
    sessions_collection_name: str = Field(
        default="sessions", description="MongoDB collection name for sessions"
    )
    messages_collection_name: str = Field(
        default="messages", description="MongoDB collection name for messages"
    )


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
