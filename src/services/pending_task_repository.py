"""MongoDB repository for delegated task tracking (KI-17 decoupling)."""

from datetime import UTC, datetime
from typing import Literal

import pymongo
from pydantic import BaseModel, Field
from pymongo.collection import Collection


class PendingTaskDocument(BaseModel):
    """Schema for documents in the ``pending_tasks`` MongoDB collection."""

    task_id: str
    session_id: str
    user_id: str
    agent_id: str
    description: str
    status: Literal["running", "done", "failed"] = "running"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    result_summary: str | None = None
    reply_channel: dict | None = None


class PendingTaskRepository:
    """Thin wrapper around MongoDB ``pending_tasks`` collection.

    Follows :class:`SessionRegistry` pattern: sync pymongo operations,
    callers use ``asyncio.to_thread()`` from async contexts.
    """

    def __init__(self, collection: Collection) -> None:
        self._col = collection
        self._col.create_index("task_id", unique=True)
        self._col.create_index("session_id")
        self._col.create_index(
            [("status", pymongo.ASCENDING), ("created_at", pymongo.ASCENDING)]
        )
        self._col.create_index(
            "created_at", expireAfterSeconds=7 * 24 * 3600  # 7-day TTL
        )

    def insert(self, doc: PendingTaskDocument) -> None:
        """Insert a new task document."""
        self._col.insert_one(doc.model_dump())

    def find_by_task_id(self, task_id: str) -> dict | None:
        """Find a single task by its ``task_id``."""
        return self._col.find_one({"task_id": task_id}, {"_id": 0})

    def find_by_session_id(
        self, session_id: str, statuses: set[str] | None = None
    ) -> list[dict]:
        """Return tasks for a session, optionally filtered by status set."""
        query: dict = {"session_id": session_id}
        if statuses:
            query["status"] = {"$in": list(statuses)}
        return list(self._col.find(query, {"_id": 0}))

    def find_expirable(self, statuses: set[str], ttl_seconds: int) -> list[dict]:
        """Find tasks older than *ttl_seconds* with a status in *statuses*."""
        cutoff = datetime.now(UTC).timestamp() - ttl_seconds
        cutoff_dt = datetime.fromtimestamp(cutoff, tz=UTC)
        return list(
            self._col.find(
                {
                    "status": {"$in": list(statuses)},
                    "created_at": {"$lt": cutoff_dt},
                },
                {"_id": 0},
            )
        )

    def update_status(
        self,
        task_id: str,
        status: Literal["done", "failed"],
        result_summary: str | None = None,
    ) -> bool:
        """Update a task's status and optional result summary.

        Sets ``completed_at`` to the current UTC time when transitioning to a
        terminal status. Returns ``True`` if a document was matched.
        """
        fields: dict = {"status": status, "completed_at": datetime.now(UTC)}
        if result_summary is not None:
            fields["result_summary"] = result_summary
        return (
            self._col.update_one({"task_id": task_id}, {"$set": fields}).matched_count
            > 0
        )

    def delete_by_session_id(self, session_id: str) -> int:
        """Delete all tasks for a session. Returns count of deleted documents."""
        return self._col.delete_many({"session_id": session_id}).deleted_count
