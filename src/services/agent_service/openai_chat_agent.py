import asyncio
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

import yaml
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from loguru import logger

from src.services.agent_service.service import AgentService
from src.services.agent_service.utils.delegate_middleware import DelegateToolMiddleware
from src.services.agent_service.utils.streaming_buffer import StreamingBuffer
from src.services.agent_service.utils.text_processor import (
    load_emotion_keywords,
    load_emotion_prompt_template,
)
from src.services.ltm_service import LTMService
from src.services.stm_service import STMService

load_dotenv()

_PERSONAS_PATH = Path(__file__).resolve().parents[3] / "yaml_files" / "personas.yml"


def _load_personas() -> dict[str, str]:
    """Load persona system_prompts from personas.yml."""
    if not _PERSONAS_PATH.exists():
        logger.warning(f"personas.yml not found at {_PERSONAS_PATH}")
        return {}
    try:
        with open(_PERSONAS_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {
            pid: p["system_prompt"]
            for pid, p in data.get("personas", {}).items()
            if "system_prompt" in p
        }
    except Exception as e:
        logger.error(f"Failed to load personas.yml: {e}")
        return {}


class OpenAIChatAgent(AgentService):
    """Single-instance OpenAI Chat Agent using langchain.agents.create_agent."""

    def __init__(
        self,
        temperature: float,
        top_p: float,
        openai_api_key: str = None,
        openai_api_base: str = None,
        model_name: str = None,
        stm_service: Optional[STMService] = None,
        **kwargs,
    ):
        self.temperature = temperature
        self.top_p = top_p
        self.openai_api_key = openai_api_key
        self.openai_api_base = openai_api_base
        self.model_name = model_name
        self.stm_service = stm_service
        self.agent = None
        self._mcp_tools: list = []
        self._personas: dict[str, str] = {}
        super().__init__(**kwargs)
        logger.info(f"Agent initialized: model={self.model_name}")

    def initialize_model(self) -> BaseChatModel:
        """Initialize and return the ChatOpenAI model."""
        return ChatOpenAI(
            temperature=self.temperature,
            top_p=self.top_p,
            openai_api_key=self.openai_api_key,
            openai_api_base=self.openai_api_base,
            model_name=self.model_name,
        )

    async def initialize_async(self) -> None:
        """Fetch MCP tools once and create the single agent instance."""
        # 1. Load persona texts + append emotion instructions
        raw_personas = _load_personas()
        keywords = load_emotion_keywords()
        template = load_emotion_prompt_template()
        emotion_instructions = template.format(keywords=", ".join(keywords))
        self._personas = {
            pid: text + emotion_instructions for pid, text in raw_personas.items()
        }
        logger.info(f"Loaded {len(self._personas)} personas: {list(self._personas)}")

        # 2. Fetch MCP tools once
        if self.mcp_config:
            async with MultiServerMCPClient(self.mcp_config) as client:
                self._mcp_tools = await client.get_tools()
            logger.info(f"Cached {len(self._mcp_tools)} MCP tools")

        # 3. Create single agent instance
        self.agent = create_agent(
            model=self.llm,
            tools=self._mcp_tools,
            middleware=[DelegateToolMiddleware(stm_service=self.stm_service)],
        )
        logger.info("Agent created successfully")

    async def is_healthy(self) -> tuple[bool, str]:
        """Check if the agent is healthy and ready."""
        if self.agent is None:
            return False, "Agent not initialized (call initialize_async first)"
        try:
            async for _ in self.stream(messages=[HumanMessage(content="Health check")]):
                continue
            return True, "Agent is healthy."
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False, f"Health check failed: {e}"

    async def stream(
        self,
        messages: list[BaseMessage],
        session_id: str = "",
        persona_id: str = "",
        user_id: str = "default_user",
        agent_id: str = "default_agent",
        stm_service: Optional[STMService] = None,
        ltm_service: Optional[LTMService] = None,
    ):
        """Stream agent response, yielding typed dicts."""
        logger.debug(f"Starting LLM stream: {len(messages)} messages")
        try:
            # Prepend persona SystemMessage if available
            persona_text = self._personas.get(persona_id, "")
            if persona_text:
                full_persona = (
                    persona_text
                    + f"\nCurrent time: {datetime.now().strftime('%H:%M:%S')}"
                )
                messages = [SystemMessage(content=full_persona)] + list(messages)

            turn_id = str(uuid4())
            config = {"configurable": {"session_id": session_id}}

            yield {
                "type": "stream_start",
                "turn_id": turn_id,
                "session_id": session_id,
            }

            new_chats: list[BaseMessage] = []
            async for item in self._process_message(messages=messages, config=config):
                if item["type"] != "final_response":
                    yield item
                else:
                    new_chats = item["data"]

            if stm_service or ltm_service:
                asyncio.create_task(
                    self.save_memory(
                        new_chats=new_chats,
                        stm_service=stm_service,
                        ltm_service=ltm_service,
                        user_id=user_id,
                        agent_id=agent_id,
                        session_id=session_id,
                    ),
                    name=f"save-memory-{session_id}",
                )

            content = new_chats[-1].content if new_chats else ""
            yield {
                "type": "stream_end",
                "turn_id": turn_id,
                "session_id": session_id,
                "content": content,
            }
        except Exception as e:
            logger.error(f"Error in stream method: {e}")
            traceback.print_exc()
            raise

    @staticmethod
    def _flush_buffer(node: str, buffer: str) -> dict:
        if node == "tools":
            return {"type": "tool_result", "result": buffer.strip(), "node": node}
        return {"type": "stream_token", "chunk": buffer.strip(), "node": node}

    async def _process_message(
        self,
        messages: list[BaseMessage],
        config: dict,
    ):
        """Process messages and yield streaming events."""
        logger.debug(f"Processing {len(messages)} messages with agent")
        node = None
        tool_called = False
        gathered = ""
        chunk_count = 0
        buffer = StreamingBuffer()
        new_chats: list[BaseMessage] = []

        try:
            async for stream_type, data in self.agent.astream(
                {"messages": messages},
                config=config,
                stream_mode=["messages", "updates"],
            ):
                if stream_type == "updates":
                    for node_name, updates in data.items():
                        if node_name in ("model", "tools"):
                            new_chats.extend(updates.get("messages", []))

                elif stream_type == "messages":
                    msg, metadata = data
                    if node != metadata.get("langgraph_node"):
                        node = metadata.get("langgraph_node", "unknown")

                    if isinstance(msg.content, str) and not msg.additional_kwargs:
                        content = msg.content
                        if not content or content.isspace():
                            continue
                        if flushed := buffer.add(content):
                            yield self._flush_buffer(node, flushed)
                            chunk_count += 1

                    elif isinstance(msg, AIMessageChunk) and msg.additional_kwargs.get(
                        "tool_calls"
                    ):
                        if not tool_called:
                            gathered = msg
                            tool_called = True
                        else:
                            gathered = gathered + msg

                        if hasattr(msg, "tool_call_chunks") and msg.tool_call_chunks:
                            tool_info = gathered.tool_call_chunks[0]
                            args_str = tool_info.get("args", "")
                            if args_str and args_str.strip().endswith("}"):
                                tool_name = tool_info.get("name", "unknown")
                                logger.info(f"Tool call detected: '{tool_name}'")
                                yield {
                                    "type": "tool_call",
                                    "tool_name": tool_name,
                                    "args": args_str,
                                    "node": node,
                                }
                                tool_called = False
                                gathered = ""

            if remaining := buffer.flush():
                yield self._flush_buffer(node, remaining)
                chunk_count += 1

            yield {"type": "final_response", "data": new_chats}
            logger.info(f"Processing completed: {chunk_count} chunks")

        except Exception as e:
            logger.error(f"Error in process_message: {e}")
            if remaining := buffer.flush():
                yield self._flush_buffer(node, remaining)
            yield {"type": "error", "error": "메시지 처리 중 오류가 발생했습니다."}
