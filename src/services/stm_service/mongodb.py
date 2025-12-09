"""MongoDB implementation of Short-Term Memory service."""

import logging
from datetime import datetime, timezone
from typing import Optional, TypeVar

import pymongo
from langchain_core.messages import (
    BaseMessage,
    convert_to_messages,
    convert_to_openai_messages,
)

from src.services.agent_service.utils.message_util import strip_images_from_messages
from src.services.stm_service.service import STMService

# Configure logging
logger = logging.getLogger(__name__)

# Define the generic type for MongoDB client
MongoDBClientType = TypeVar("MongoDBClientType", bound=pymongo.MongoClient)


class MongoDBSTM(STMService[MongoDBClientType]):
    """MongoDB implementation of Short-Term Memory service."""

    def __init__(
        self,
        connection_string: str,
        database_name: str,
        sessions_collection_name: str,
        messages_collection_name: str,
    ):
        """Initialize MongoDB STM service.

        Args:
            connection_string: MongoDB connection string
            database_name: MongoDB database name
            sessions_collection_name: Sessions collection name
            messages_collection_name: Messages collection name
        """
        self.connection_string = connection_string
        self.database_name = database_name
        self.sessions_collection_name = sessions_collection_name
        self.messages_collection_name = messages_collection_name
        super().__init__()

    def initialize_memory(self) -> MongoDBClientType:
        """Initialize the MongoDB connection.

        Args:
            memory_config (dict): Configuration for MongoDB connection

        Returns:
            MongoDBClientType: The initialized MongoDB client

        Raises:
            pymongo.errors.ConnectionFailure: If connection fails
        """
        try:
            # Initialize MongoDB client
            self._client = pymongo.MongoClient(
                self.connection_string, uuidRepresentation="standard"
            )

            # Get database and collections
            self._db = self._client[self.database_name]
            self._sessions_collection = self._db[self.sessions_collection_name]
            self._messages_collection = self._db[self.messages_collection_name]

            # Test the connection
            self._client.admin.command("ping")
            logger.info(f"Successfully connected to MongoDB: {self.connection_string}")
            logger.info(f"Using database: {self.database_name}")
            logger.info(
                f"Using collections: {self.sessions_collection_name}, {self.messages_collection_name}"
            )

            # Create indexes for efficient querying
            self._create_indexes()

            return self._client  # type: ignore

        except pymongo.errors.ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Error initializing MongoDB memory: {e}")
            raise

    def is_healthy(self) -> tuple[bool, str]:
        """Check if MongoDB STM service is healthy.

        Returns:
            Tuple of (is_healthy: bool, message: str)
        """
        try:
            if self._client is None:
                return False, "MongoDB client not initialized"

            # Test the connection
            self._client.admin.command("ping")
            return True, "MongoDB STM service is healthy"
        except Exception as e:
            logger.error(f"MongoDB STM health check failed: {e}")
            return False, f"MongoDB STM service unhealthy: {str(e)}"

    def _create_indexes(self) -> None:
        """Create indexes on MongoDB collections for efficient querying.

        Creates the following indexes:
        - sessions collection: compound index on (user_id, agent_id)
        - messages collection: compound index on (session_id, created_at)
        """
        try:
            # Create compound index on sessions collection for user_id and agent_id
            self._sessions_collection.create_index(
                [("user_id", pymongo.ASCENDING), ("agent_id", pymongo.ASCENDING)],
                background=True,
                name="user_agent_idx",
            )
            logger.info(
                f"Created index on {self.sessions_collection_name}: user_id, agent_id"
            )

            # Create compound index on messages collection for session_id and created_at
            self._messages_collection.create_index(
                [("session_id", pymongo.ASCENDING), ("created_at", pymongo.ASCENDING)],
                background=True,
                name="session_created_idx",
            )
            logger.info(
                f"Created index on {self.messages_collection_name}: session_id, created_at"
            )

        except Exception as e:
            logger.warning(f"Failed to create indexes: {e}")
            # Don't raise - indexes are optional optimization

    def add_chat_history(
        self,
        user_id: str,
        agent_id: str,
        session_id: Optional[str],
        messages: list[BaseMessage],
    ) -> str:
        """Add chat history to MongoDB.

        Args:
            user_id (str): User identifier
            agent_id (str): Agent identifier
            session_id (Optional[str]): Session identifier, creates new if None
            messages (list[BaseMessage]): List of messages to add

        Returns:
            str: The session_id (newly created or existing)
        """
        try:
            self._sessions_collection.update_one(
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "agent_id": agent_id,
                },
                {
                    "$set": {
                        # 업데이트/생성 시: 'updated_at'은 항상 현재 시각으로 설정
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$setOnInsert": {
                        # 생성 시에만: 'created_at'은 처음 생성되는 시각으로 설정
                        "created_at": datetime.now(timezone.utc),
                        "metadata": {},
                    },
                },
                upsert=True,  # 세션이 없으면 새로 생성하도록 설정
            )
            # Serialize messages to dictionaries and strip images
            serialized_messages = convert_to_openai_messages(messages)
            serialized_messages = strip_images_from_messages(serialized_messages)

            # Prepare message documents for MongoDB
            message_docs = []
            current_time = datetime.now(timezone.utc)
            for idx, msg_dict in enumerate(serialized_messages):
                message_doc = {
                    "session_id": session_id,
                    "message_data": msg_dict,
                    "created_at": current_time,
                    "sequence": idx,  # Track message order within the batch
                }
                message_docs.append(message_doc)

            # Bulk insert messages
            if message_docs:
                self._messages_collection.insert_many(message_docs)
                logger.info(
                    f"Added {len(message_docs)} messages to session {session_id}"
                )

            return session_id

        except Exception as e:
            logger.error(f"Error adding chat history: {e}")
            raise

    def get_chat_history(
        self,
        user_id: str,
        agent_id: str,
        session_id: str,
        limit: Optional[int] = None,
    ) -> list[BaseMessage]:
        """Get chat history from MongoDB.

        Args:
            user_id (str): User identifier
            agent_id (str): Agent identifier
            session_id (str): Session identifier
            limit (Optional[int]): Max number of recent messages to retrieve

        Returns:
            list[BaseMessage]: Chat history
        """
        try:
            # Query messages collection for the given session_id
            query = {"session_id": session_id}

            # Sort by created_at ascending (oldest first) and sequence
            cursor = self._messages_collection.find(query).sort(
                [("created_at", pymongo.ASCENDING), ("sequence", pymongo.ASCENDING)]
            )

            # Apply limit if specified (get the most recent messages)
            if limit is not None and limit > 0:
                # To get the most recent N messages, we need to:
                # 1. Count total messages
                # 2. Skip the older ones
                total_count = self._messages_collection.count_documents(query)
                skip_count = max(0, total_count - limit)
                cursor = cursor.skip(skip_count).limit(limit)

            # Extract message data from documents
            message_dicts = []
            for doc in cursor:
                message_dicts.append(doc["message_data"])

            # Deserialize messages
            messages = convert_to_messages(message_dicts)

            logger.info(f"Retrieved {len(messages)} messages from session {session_id}")
            return messages

        except Exception as e:
            logger.error(f"Error retrieving chat history: {e}")
            raise

    def list_sessions(self, user_id: str, agent_id: str) -> list[dict]:
        """List sessions for a user and agent from MongoDB.

        Args:
            user_id (str): User identifier
            agent_id (str): Agent identifier

        Returns:
            list[dict]: List of session metadata
        """
        try:
            # Query sessions collection for user_id and agent_id
            query = {"user_id": user_id, "agent_id": agent_id}

            # Sort by updated_at descending (most recent first)
            cursor = self._sessions_collection.find(query).sort(
                "updated_at", pymongo.DESCENDING
            )

            # Convert to list of dictionaries with relevant metadata
            sessions = []
            for doc in cursor:
                session_metadata = {
                    "session_id": doc["session_id"],
                    "user_id": doc["user_id"],
                    "agent_id": doc["agent_id"],
                    "created_at": doc["created_at"],
                    "updated_at": doc["updated_at"],
                    "metadata": doc.get("metadata", {}),
                }
                sessions.append(session_metadata)

            logger.info(
                f"Retrieved {len(sessions)} sessions for user {user_id} and agent {agent_id}"
            )
            return sessions

        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            raise

    def delete_session(self, session_id: str, user_id: str, agent_id: str) -> bool:
        """Delete a specific chat session from MongoDB.

        Args:
            session_id (str): Session identifier
            user_id (str): User identifier (for verification)
            agent_id (str): Agent identifier (for verification)

        Returns:
            bool: True if deletion was successful
        """
        try:
            # First, verify that the session belongs to the user and agent
            session_query = {
                "session_id": session_id,
                "user_id": user_id,
                "agent_id": agent_id,
            }

            session = self._sessions_collection.find_one(session_query)
            if not session:
                logger.warning(
                    f"Session {session_id} not found for user {user_id} and agent {agent_id}"
                )
                return False

            # Delete all messages associated with this session
            message_result = self._messages_collection.delete_many(
                {"session_id": session_id}
            )
            logger.info(
                f"Deleted {message_result.deleted_count} messages from session {session_id}"
            )

            # Delete the session document
            session_result = self._sessions_collection.delete_one(session_query)

            if session_result.deleted_count > 0:
                logger.info(f"Successfully deleted session {session_id}")
                return True
            else:
                logger.warning(f"Failed to delete session {session_id}")
                return False

        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            raise

    def update_session_metadata(self, session_id: str, metadata: dict) -> bool:
        """Update session metadata in MongoDB.

        Args:
            session_id (str): Session identifier
            metadata (dict): Metadata to update or add

        Returns:
            bool: True if update was successful
        """
        try:
            # Build update operation using dot notation for metadata fields
            update_fields = {}
            for key, value in metadata.items():
                update_fields[f"metadata.{key}"] = value

            # Update the session document
            result = self._sessions_collection.update_one(
                {"session_id": session_id}, {"$set": update_fields}
            )

            if result.matched_count > 0:
                logger.info(f"Updated metadata for session {session_id}")
                return True
            else:
                logger.warning(f"Session {session_id} not found for metadata update")
                return False

        except Exception as e:
            logger.error(f"Error updating session metadata: {e}")
            raise
