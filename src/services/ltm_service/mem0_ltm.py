import logging
from typing import Optional, TypedDict

from langchain_core.messages import BaseMessage
from langchain_core.messages.utils import convert_to_openai_messages
from langchain_openai import OpenAIEmbeddings
from mem0 import Memory
from pydantic import BaseModel, Field

from src.configs.ltm import Mem0LongTermMemoryConfig
from src.services.ltm_service.service import LTMService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Mem0Relation(BaseModel):
    """Model for a relation in the memory graph."""

    source: str = Field(
        ...,
        description="Source entity of the relation",
    )
    relationship: str = Field(
        ...,
        description="Type of relationship between source and destination",
    )
    destination: str = Field(
        ...,
        description="Destination entity of the relation",
    )


class Mem0MemoryItem(BaseModel):
    """Model for a single memory item retrieved from LTM."""

    id: str = Field(
        ...,
        description="Unique memory identifier",
    )
    memory: str = Field(
        ...,
        description="Memory content/text",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Associated user ID",
    )
    agent_id: Optional[str] = Field(
        default=None,
        description="Associated agent ID",
    )
    hash: Optional[str] = Field(
        default=None,
        description="Memory hash for deduplication",
    )
    metadata: Optional[dict] = Field(
        default=None,
        description="Additional metadata associated with the memory",
    )
    score: Optional[float] = Field(
        default=None,
        description="Similarity score for search results",
    )
    created_at: Optional[str] = Field(
        default=None,
        description="Timestamp when the memory was created",
    )
    updated_at: Optional[str] = Field(
        default=None,
        description="Timestamp when the memory was last updated",
    )


class Mem0Response(TypedDict):
    """TypedDict for Mem0 API responses.

    Contains results (list of memory items) and relations (list of graph relations).
    """

    results: list[Mem0MemoryItem]
    relations: list[Mem0Relation]


class Mem0LTM(LTMService[Memory]):
    """Mem0LTM for Long Term Memory Service.

    Args:
        memory_config (Mem0LongTermMemoryConfig): Configuration for Long-Term memory saving.
    """

    def __init__(self, memory_config: Mem0LongTermMemoryConfig):
        self.memory_config = memory_config
        super().__init__()
        logger.info(
            "Long Term Memory Service is initialized. Memory client initialized: %s",
            self.memory_client,
        )

    def initialize_memory(self) -> Memory:
        """
        Initialize the memory retrieval client and checkpoint saver.

        Returns:
            Memory: The initialized client.
        """
        mem0_config = self._parse_config(self.memory_config)

        memory = Memory.from_config(mem0_config)
        return memory

    def is_healthy(self) -> tuple[bool, str]:
        """
        Check if the memory service is healthy and ready.

        Returns:
            Tuple of (is_healthy: bool, message: str)
        """
        try:
            # Simple health check by adding a temporary entry,
            # And this should be returned as empty result. because this query dosen't have any information.
            health = self.memory_client.add("temp", user_id="health_check")
            if health["results"] == []:
                return True, "Mem0 Long Term Memory Service is healthy."
            else:
                return False, f"Mem0 Long Term Memory Service is unhealthy: {health}"
        except Exception as e:
            return False, f"Mem0 Long Term Memory Service health check failed: {e}"

    def search_memory(self, query: str, user_id: str, agent_id: str) -> Mem0Response:
        """
        Search the memory for relevant information.

        Returns:
            Mem0Response: Search results containing 'results' and 'relations' keys.
        """
        try:
            result = self.memory_client.search(
                query,
                user_id=user_id,
                agent_id=agent_id,
            )
        except Exception as e:
            logger.error(f"Error searching memory: {e}")
            result = {"error": str(e)}
        return result

    def add_memory(
        self, messages: list[BaseMessage], user_id: str, agent_id: str
    ) -> Mem0Response:
        """
        Add information to memory.

        Returns:
            Mem0Response: Add results containing 'results' and 'relations' keys.
        """
        try:
            messages = convert_to_openai_messages(messages)
            # Mem0 work better when each message is prefixed with user_id or agent_id
            for msg in messages:
                # Skip tool calls (assistant with tool_calls) and tool messages
                if msg.get("role") == "tool" or msg.get("tool_calls"):
                    continue

                # Process user and assistant messages
                if msg.get("role") in ("user", "assistant"):
                    prefix = (
                        f"{user_id}: " if msg["role"] == "user" else f"{agent_id}: "
                    )
                    content = msg.get("content")

                    if content is None:
                        continue

                    # Handle string content
                    if isinstance(content, str):
                        if not content.startswith(prefix):
                            msg["content"] = prefix + content
                    # Handle list content (multimodal)
                    elif isinstance(content, list):
                        for item in content:
                            # Only add prefix to text items, skip image_url
                            if isinstance(item, dict) and item.get("type") == "text":
                                if not item["text"].startswith(prefix):
                                    item["text"] = prefix + item["text"]
                                break  # Only prefix the first text item

            result = self.memory_client.add(
                messages,
                user_id=user_id,
                agent_id=agent_id,
            )
        except Exception as e:
            logger.error(f"Error adding memory: {e}")
            result = {"error": str(e)}
        return result

    def delete_memory(self, user_id: str, agent_id: str, memory_id: str) -> dict:
        """
        Delete information from memory.

        Args:
            user_id (str): The ID of the user. (Not used in Mem0 but kept for interface consistency)
            agent_id (str): The ID of the agent. (Not used in Mem0 but kept for interface consistency)
            memory_id (str): The ID of the memory to delete.

        Returns:
            dict: Delete results.
        """
        try:
            result = self.memory_client.delete(
                memory_id,
            )
        except Exception as e:
            logger.error(f"Error deleting memory: {e}")
            result = {"error": str(e)}
        return result

    def _parse_config(
        self,
        mem0_config: Mem0LongTermMemoryConfig,
    ) -> dict:
        """Parse Mem0 configuration.

        Args:
            mem0_config (Mem0Config): The Mem0 configuration object.

        Returns:
            dict: Parsed configuration dictionary.
        """
        logger.info(f"Parsing Mem0 configuration: {mem0_config}")
        embedding_model = OpenAIEmbeddings(
            model=mem0_config.embedder.config.model_name,
            openai_api_base=mem0_config.embedder.config.openai_base_url,
            openai_api_key=mem0_config.embedder.config.openai_api_key,
        )
        embedding_dict = {
            "provider": "langchain",
            "config": {
                "model": embedding_model,
                "embedding_dims": mem0_config.embedder.config.embedding_dims,
            },
        }
        # Fix: LLM config should include provider and config structure
        llm_dict = {
            "provider": mem0_config.llm.provider,
            "config": mem0_config.llm.config.model_dump(),
        }
        # Fix: Vector store and graph store should also include provider
        vector_store_dict = {
            "provider": mem0_config.vector_store.provider,
            "config": mem0_config.vector_store.config.model_dump(),
        }
        graph_store_dict = {
            "provider": mem0_config.graph_store.provider,
            "config": mem0_config.graph_store.config.model_dump(),
        }
        mem0_config_dict = {
            "llm": llm_dict,
            "embedder": embedding_dict,
            "vector_store": vector_store_dict,
            "graph_store": graph_store_dict,
        }
        return mem0_config_dict
