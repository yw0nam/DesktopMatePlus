"""MongoDB-backed user profile CRUD service."""

import pymongo.collection
from loguru import logger

from src.models.user_profile import UserProfile


class UserProfileService:
    """CRUD service for user context profiles stored in MongoDB."""

    def __init__(self, collection: pymongo.collection.Collection) -> None:
        self._col = collection

    def get_profile(self, user_id: str) -> UserProfile | None:
        """Retrieve profile by user_id, or None if not found."""
        doc = self._col.find_one({"user_id": user_id}, {"_id": 0})
        if doc is None:
            return None
        return UserProfile(**doc)

    def upsert_profile(self, user_id: str, data: dict) -> UserProfile:
        """Insert or replace the full profile for user_id."""
        doc = {"user_id": user_id, **data}
        profile = UserProfile(**doc)
        self._col.replace_one(
            {"user_id": user_id},
            profile.model_dump(),
            upsert=True,
        )
        logger.info(f"Profile upserted for user={user_id}")
        return profile

    def update_profile(self, user_id: str, partial: dict) -> UserProfile | None:
        """Apply a partial update to an existing profile. Returns None if not found."""
        result = self._col.find_one_and_update(
            {"user_id": user_id},
            {"$set": partial},
            return_document=pymongo.collection.ReturnDocument.AFTER,
            projection={"_id": 0},
        )
        if result is None:
            logger.info(f"update_profile: no profile found for user={user_id}")
            return None
        logger.info(f"Profile updated for user={user_id}")
        return UserProfile(**result)
