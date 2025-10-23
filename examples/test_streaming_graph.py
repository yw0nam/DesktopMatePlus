# %%
import logging
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from mem0 import Memory

from src.configs.mem0_configs import MEM0_CONFIG, VOCABULARY_DB_CONFIG
from src.services.agent_service.graph import AgentGraphBuilder
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
    builder = AgentGraphBuilder(
        llm=chat_model,
        mem0_client=mem0_client,
        vocabulary_manager=vocabulary_manager,
    )
    graph = builder.build()
    logger.info("Agent graph created successfully.")
    return graph


async def main():
    agent_graph = load_test_graph()
    example_messages = [
        HumanMessage(content="Hello, world!"),
        # Add more messages as needed for testing
    ]
    config = {
        "thread_id": "session-1",
    }

    print("\n" + "=" * 80)
    print("STREAMING AGENT RESPONSE WITH FORMATTED OUTPUT")
    print("=" * 80)

    async for response in process_message(example_messages, agent_graph, config):
        response_type = response.get("type")

        if response_type == "header":
            # Print node header
            print(response.get("text", ""), end="")

        elif response_type == "content":
            # Print content with emotion tag if present
            text = response.get("text", "")
            emotion = response.get("emotion")

            if emotion:
                print(f"[Emotion: {emotion}] {text}")
            else:
                print(text)

        elif response_type == "tool_call":
            # Print formatted tool call
            print(response.get("text", ""))

        elif response_type == "error":
            print(f"\n❌ ERROR: {response.get('message', 'Unknown error')}")

    print("\n" + "=" * 80)
    print("STREAMING COMPLETED")
    print("=" * 80 + "\n")


# %%
agent_graph = load_test_graph()
example_messages = [
    HumanMessage(
        content="i'm dating with natsume now who is the clever research i ever met. can you store this to your memory?"
    ),
    # Add more messages as needed for testing
]
config = {
    "thread_id": "session-1",
}
# %%
responses = []
async for response in process_message(example_messages, agent_graph, config):
    response_type = response.get("type")

    if response_type == "header":
        # Print node header
        print(response.get("text", ""), end="")

    elif response_type == "content":
        # Print content with emotion tag if present
        text = response.get("text", "")
        emotion = response.get("emotion")

        if emotion:
            print(f"[Emotion: {emotion}] {text}")
        else:
            print(text)

    elif response_type == "tool_call":
        # Print formatted tool call
        print(response.get("text", ""))

    elif response_type == "error":
        print(f"\n❌ ERROR: {response.get('message', 'Unknown error')}")
    responses.append(response)
# %%
responses[8]
# %%
len(responses)
# %%
# #%%
# if __name__ == "__main__":
#     import asyncio

#     asyncio.run(main())
