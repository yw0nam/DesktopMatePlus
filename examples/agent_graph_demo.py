"""
Demo script for LangGraph Agent with Desktop Context.

This script demonstrates how to use the agent graph with all nodes:
- perceive_environment: Capture and analyze screen
- query_memory: Retrieve relevant memories
- reason_and_plan: Plan actions
- generate_response: Generate response
- update_memory: Store new memories
"""

import asyncio
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from loguru import logger
from mem0 import Memory

from src.configs.mem0_configs import MEM0_CONFIG, VOCABULARY_DB_CONFIG
from src.services.agent_service.graph import create_agent_graph
from src.services.agent_service.llm_factory import LLMFactory
from src.services.agent_service.tools.memory.metadata_manager import (
    PostgreSQLVocabularyManager,
)
from src.services.screen_capture_service.screen_capture import ScreenCaptureService
from src.services.vlm_service.vlm_factory import VLMFactory

# Load environment variables
load_dotenv()


async def run_agent_demo(
    user_message: str,
    user_id: str = "demo-user",
    capture_screen: bool = False,
    thread_id: str = "demo-thread",
):
    """
    Run a demonstration of the agent graph.

    Args:
        user_message: Message from the user
        user_id: User identifier
        capture_screen: Whether to capture and analyze screen
        thread_id: Thread identifier for conversation continuity
    """
    logger.info("=== LangGraph Agent Demo ===")
    logger.info(f"User message: {user_message}")
    logger.info(f"Screen capture: {capture_screen}")

    # 1. Initialize services
    logger.info("Initializing services...")

    # LLM for reasoning and generation
    llm = LLMFactory.get_llm_service(
        service_type="openai",
        openai_api_key=os.getenv("LLM_API_KEY"),
        openai_api_base=os.getenv("LLM_BASE_URL"),
        model_name=os.getenv("LLM_MODEL_NAME"),
    )

    # Memory client
    mem0_client = Memory.from_config(MEM0_CONFIG)

    # Vocabulary manager for metadata
    vocabulary_manager = PostgreSQLVocabularyManager(db_config=VOCABULARY_DB_CONFIG)

    # Optional: VLM service for screen analysis
    vlm_service = None
    if capture_screen:
        try:
            vlm_service = VLMFactory.get_vlm_service(
                service_type=os.getenv("VLM_MODEL", "openai"),
                openai_api_key=os.getenv("VLM_API_KEY"),
                openai_base_url=os.getenv("VLM_BASE_URL"),
                model_name=os.getenv("VLM_MODEL_NAME"),
            )
            logger.info("VLM service initialized")
        except Exception as e:
            logger.warning(f"VLM service initialization failed: {e}")

    # Optional: Screen capture service
    screen_capture_service = None
    if capture_screen:
        try:
            screen_capture_service = ScreenCaptureService()
            logger.info("Screen capture service initialized")
        except Exception as e:
            logger.warning(f"Screen capture service initialization failed: {e}")

    # 2. Create agent graph
    logger.info("Creating agent graph...")
    graph = create_agent_graph(
        llm=llm,
        mem0_client=mem0_client,
        vocabulary_manager=vocabulary_manager,
        vlm_service=vlm_service,
        screen_capture_service=screen_capture_service,
    )

    # 3. Prepare initial state and configuration
    initial_state = {
        "messages": [HumanMessage(content=user_message)],
    }

    config = {
        "configurable": {
            "user_id": user_id,
            "agent_id": "desktop-assistant",
            "thread_id": thread_id,
            "capture_screen": capture_screen,
        }
    }

    # 4. Execute agent graph
    logger.info("Executing agent graph...")
    logger.info("-" * 60)

    try:
        result = await graph.ainvoke(initial_state, config)

        # 5. Display results
        logger.info("=== Agent Execution Complete ===")
        logger.info(f"\nFinal state keys: {result.keys()}")

        if "visual_context" in result and result["visual_context"]:
            logger.info(f"\n📸 Visual Context:\n{result['visual_context']}")

        if "relevant_memories" in result and result["relevant_memories"]:
            logger.info(f"\n🧠 Retrieved Memories: {len(result['relevant_memories'])}")
            for mem in result["relevant_memories"]:
                logger.info(f"  - {mem.get('memory', 'N/A')}")

        if "action_plan" in result and result["action_plan"]:
            logger.info(f"\n📋 Action Plan:\n{result['action_plan']}")

        if "messages" in result:
            # Find the AI's response (last AIMessage)
            from langchain_core.messages import AIMessage

            ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
            if ai_messages:
                logger.info(f"\n🤖 Assistant Response:\n{ai_messages[-1].content}")

        logger.info("-" * 60)
        return result

    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        raise


async def main():
    """Run demo scenarios."""

    # Scenario 1: Simple conversation without screen capture
    logger.info("\n" + "=" * 60)
    logger.info("SCENARIO 1: Simple Conversation")
    logger.info("=" * 60)

    await run_agent_demo(
        user_message="Hello! My name is Alex and I'm learning Python.",
        user_id="demo-user",
        capture_screen=False,
        thread_id="demo-thread-1",
    )

    # Wait a bit between scenarios
    await asyncio.sleep(2)

    # Scenario 2: Continue conversation (same thread)
    logger.info("\n" + "=" * 60)
    logger.info("SCENARIO 2: Continuing Conversation")
    logger.info("=" * 60)

    await run_agent_demo(
        user_message="What's my name again? What am I learning?",
        user_id="demo-user",
        capture_screen=False,
        thread_id="demo-thread-1",  # Same thread as before
    )

    # Scenario 3: With screen capture (if services available)
    logger.info("\n" + "=" * 60)
    logger.info("SCENARIO 3: With Screen Analysis")
    logger.info("=" * 60)

    try:
        await run_agent_demo(
            user_message="What's on my screen right now?",
            user_id="demo-user",
            capture_screen=True,
            thread_id="demo-thread-2",
        )
    except Exception as e:
        logger.warning(f"Screen capture scenario failed: {e}")
        logger.info("This is expected if VLM services are not configured")


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
