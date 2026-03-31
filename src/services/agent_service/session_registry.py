"""Thin wrapper around MongoDB session_registry collection."""

from datetime import UTC, datetime

import pymongo
from pymongo.collection import Collection


class SessionRegistry:
    def __init__(self, collection: Collection) -> None:
        self._col = collection
        self._col.create_index(
            [("user_id", pymongo.ASCENDING), ("agent_id", pymongo.ASCENDING)]
        )
        self._col.create_index([("updated_at", pymongo.DESCENDING)])

    def upsert(self, thread_id: str, user_id: str, agent_id: str) -> None:
        now = datetime.now(UTC)
        self._col.update_one(
            {"thread_id": thread_id},
            {
                "$set": {"user_id": user_id, "agent_id": agent_id, "updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    def list_sessions(self, user_id: str, agent_id: str) -> list[dict]:
        return list(
            self._col.find(
                {"user_id": user_id, "agent_id": agent_id},
                sort=[("updated_at", pymongo.DESCENDING)],
            )
        )

    def find_all(self) -> list[dict]:
        return list(self._col.find({}, {"thread_id": 1}))

    def delete(self, thread_id: str) -> bool:
        return self._col.delete_one({"thread_id": thread_id}).deleted_count > 0
