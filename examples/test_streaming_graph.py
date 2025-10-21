import logging
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from mem0 import Memory

from src.configs.mem0_configs import MEM0_CONFIG, VOCABULARY_DB_CONFIG
from src.services.agent_service.graph import create_agent_graph
from src.services.agent_service.llm_factory import LLMFactory
from src.services.agent_service.tools.memory.metadata_manager import (
    PostgreSQLVocabularyManager,
)
from src.services.agent_service.utils.message_util import process_message

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("This module defines the AgentGraphBuilder and related functions.")


def load_test_graph():
    mem0_client = Memory.from_config(MEM0_CONFIG)
    vocabulary_manager = PostgreSQLVocabularyManager(VOCABULARY_DB_CONFIG)
    chat_model = LLMFactory.get_llm_service(
        "openai",
        openai_api_key=os.getenv("LLM_API_KEY"),
        openai_api_base=os.getenv("LLM_BASE_URL"),
        model_name=os.getenv("LLM_MODEL_NAME"),
    )
    agent_graph = create_agent_graph(
        llm=chat_model,
        mem0_client=mem0_client,
        vocabulary_manager=vocabulary_manager,
    )

    logger.info("Agent graph created successfully.")
    return agent_graph


async def main():
    agent_graph = load_test_graph()
    example_messages = [
        HumanMessage(content="Hello, world!"),
        # Add more messages as needed for testing
    ]
    config = {
        "thread_id": "session-1",
    }
    async for response in process_message(example_messages, agent_graph, config):
        print("Response chunk:", response)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
