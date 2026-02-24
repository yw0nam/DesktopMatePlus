"""MongoDB Short-Term Memory configuration."""

from pydantic import BaseModel, Field


class MongoDBShortTermMemoryConfig(BaseModel):
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
