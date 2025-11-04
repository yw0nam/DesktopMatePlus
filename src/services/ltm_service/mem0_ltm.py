import logging

from langchain_core.messages import BaseMessage
from langchain_openai import OpenAIEmbeddings
from mem0 import Memory

from src.configs.ltm import Mem0LongTermMemoryConfig
from src.services.ltm_service.service import LTMService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Mem0LTM(LTMService[Memory]):
    """Mem0LTM for Long Term Memory Service.

    Args:
        memory_config (Mem0LongTermMemoryConfig): Configuration for Long-Term memory saving.
    """

    def __init__(self, memory_config: Mem0LongTermMemoryConfig):
        super().__init__()
        self.memory_config = memory_config
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

        memory = Memory(**mem0_config)
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

    def search_memory(self, query: str, user_id: str, agent_id: str) -> dict:
        """
        Search the memory for relevant information.

        Returns:
            dict: Search results.
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
    ) -> dict:
        """
        Add information to memory.

        Returns:
            dict: Add results.
        """
        try:
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
            user_id (str): The ID of the user. (Not used in Mem0 but kept for interface consistency
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
        embedding_model = OpenAIEmbeddings(
            model=mem0_config.embedder.config["model_name"],
            openai_api_base=mem0_config.embedder.config["openai_api_base"],
            openai_api_key=mem0_config.embedder.config["openai_api_key"],
        )
        embedding_dict = {
            "provider": "langchain",
            "config": {
                "model": embedding_model,
                "embedding_dims": mem0_config.embedder.config["embedding_dims"],
            },
        }
        mem0_config_dict = {
            "llm": mem0_config.llm.config,
            "embedder": embedding_dict,
            "vector_store": mem0_config.vector_store.config,
            "graph_store": mem0_config.graph_store.config,
        }
        return mem0_config_dict
