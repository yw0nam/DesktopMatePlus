import logging

from langchain_openai import OpenAIEmbeddings
from mem0 import Memory

from src.configs.ltm import Mem0LongTermMemory
from src.services.ltm_service.service import LTMService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Mem0LTM(LTMService[Memory]):
    """Mem0LTM for Long Term Memory Service.

    Args:
        memory_config (Mem0LongTermMemory): Configuration for Long-Term memory saving.
    """

    def __init__(
        self,
        memory_config: Mem0LongTermMemory,
    ):
        super().__init__(memory_config=memory_config)
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

    def search_memory(self) -> dict:
        """
        Search the memory for relevant information.

        Returns:
            dict: Search results.
        """

    def add_memory(self) -> dict:
        """
        Add information to memory.

        Returns:
            dict: Add results.
        """

    def _parse_config(
        self,
        mem0_config: Mem0LongTermMemory,
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
