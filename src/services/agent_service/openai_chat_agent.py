from datetime import datetime
from pathlib import Path
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

from src.services.agent_service.middleware.delegate_middleware import (
    DelegateToolMiddleware,
)
from src.services.agent_service.middleware.hitl_middleware import HitLMiddleware
from src.services.agent_service.middleware.tool_gate_middleware import (
    ToolGateMiddleware,
)
from src.services.agent_service.service import AgentService
from src.services.agent_service.state import CustomAgentState
from src.services.agent_service.utils.streaming_buffer import StreamingBuffer

load_dotenv()

_PERSONAS_PATH = Path(__file__).resolve().parents[3] / "yaml_files" / "personas.yml"


def _load_personas() -> dict[str, str]:
    """Load persona system_prompts from personas.yml."""
    if not _PERSONAS_PATH.exists():
        logger.warning(f"personas.yml not found at {_PERSONAS_PATH}")
        return {}
    try:
        with open(_PERSONAS_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {
            pid: p["system_prompt"]
            for pid, p in data.get("personas", {}).items()
            if "system_prompt" in p
        }
    except Exception:
        logger.exception("Failed to load personas.yml")
        return {}


class OpenAIChatAgent(AgentService):
    """Single-instance OpenAI Chat Agent using langchain.agents.create_agent."""

    def __init__(
        self,
        temperature: float,
        top_p: float,
        openai_api_key: str | None = None,
        openai_api_base: str | None = None,
        model_name: str | None = None,
        tool_config: dict | None = None,
        **kwargs,
    ):
        self.temperature = temperature
        self.top_p = top_p
        self.openai_api_key = openai_api_key
        self.openai_api_base = openai_api_base
        self.model_name = model_name
        self.tool_config = tool_config
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
        # 1. Load persona texts (emoji emotion guide is already embedded in personas.yml)
        self._personas = _load_personas()
        logger.info(f"Loaded {len(self._personas)} personas: {list(self._personas)}")

        # 2. Load MCP tools via stateless client (langchain-mcp-adapters 0.2.2+)
        if self.mcp_config:
            try:
                client = MultiServerMCPClient(self.mcp_config)
                self._mcp_tools = await client.get_tools()
                logger.info(f"Loaded {len(self._mcp_tools)} MCP tools")
            except Exception:
                logger.exception("Failed to load MCP tools, continuing without")
                self._mcp_tools = []

        # 3. Create single agent instance
        from langchain.agents.middleware import after_model, before_model

        from src.services.agent_service.middleware.ltm_middleware import (
            ltm_consolidation_hook,
            ltm_retrieve_hook,
        )
        from src.services.agent_service.middleware.profile_middleware import (
            profile_retrieve_hook,
        )
        from src.services.agent_service.middleware.summary_middleware import (
            summary_consolidation_hook,
            summary_inject_hook,
        )
        from src.services.agent_service.middleware.task_status_middleware import (
            task_status_inject_hook,
        )
        from src.services.agent_service.tools.profile import UpdateUserProfileTool
        from src.services.service_manager import (
            get_mongo_client,
            get_user_profile_service,
        )

        mongo_client = get_mongo_client()
        checkpointer = None
        if mongo_client:
            try:
                from langgraph.checkpoint.mongodb import MongoDBSaver

                checkpointer = MongoDBSaver(client=mongo_client)
            except ImportError:
                logger.warning(
                    "langgraph-checkpoint-mongodb not available, checkpointer disabled"
                )

        custom_tools = list(self._mcp_tools)
        profile_svc = get_user_profile_service()
        if profile_svc is not None:
            custom_tools.append(UpdateUserProfileTool(service=profile_svc))

        from src.services.agent_service.tools.registry import ToolRegistry

        builtin_tools = ToolRegistry(self.tool_config).get_enabled_tools()
        if builtin_tools:
            logger.info(
                f"Adding {len(builtin_tools)} builtin tools: {[t.name for t in builtin_tools]}"
            )
            custom_tools.extend(builtin_tools)

        builtin_cfg: dict = (self.tool_config or {}).get("builtin", {})
        tool_gate = ToolGateMiddleware(
            allowed_commands=builtin_cfg.get("shell", {}).get("allowed_commands"),
            allowed_dirs=(
                [builtin_cfg.get("filesystem", {}).get("root_dir")]
                if builtin_cfg.get("filesystem", {}).get("root_dir")
                else None
            ),
        )

        mcp_tool_names = {t.name for t in self._mcp_tools}
        hitl_gate = HitLMiddleware(mcp_tool_names=mcp_tool_names)

        self.agent = create_agent(
            model=self.llm,
            tools=custom_tools,
            state_schema=CustomAgentState,
            checkpointer=checkpointer,
            middleware=[
                tool_gate,
                hitl_gate,
                DelegateToolMiddleware(),
                before_model(profile_retrieve_hook),
                before_model(summary_inject_hook),
                before_model(ltm_retrieve_hook),
                before_model(task_status_inject_hook),
                after_model(ltm_consolidation_hook),
                after_model(summary_consolidation_hook),
            ],
        )
        logger.info("Agent created successfully")

    async def cleanup_async(self) -> None:
        """No-op: stateless MCP client requires no shutdown."""
        logger.info("MCP cleanup: nothing to clean up (stateless client)")

    async def is_healthy(self) -> tuple[bool, str]:
        """Check if the agent is healthy and ready."""
        if self.agent is None:
            return False, "Agent not initialized (call initialize_async first)"
        try:
            async for _ in self.stream(messages=[HumanMessage(content="Health check")]):
                continue
            return True, "Agent is healthy."
        except Exception as e:
            logger.exception("Health check failed")
            return False, f"Health check failed: {e}"

    async def stream(
        self,
        messages: list[BaseMessage],
        session_id: str = "",
        persona_id: str = "",
        user_id: str = "default_user",
        agent_id: str = "default_agent",
        context: dict | None = None,
        is_new_session: bool = False,
    ):
        """Stream agent response, yielding typed dicts."""
        logger.debug(f"Starting LLM stream: {len(messages)} messages")
        try:
            # Only inject persona SystemMessage for new sessions.
            # For continuing sessions, persona is already at the start of checkpointed history.
            # Assign an explicit id so ltm_retrieve_hook can update it in-place via
            # add_messages (None-id messages are always appended, never replaced).
            persona_text = self._personas.get(persona_id, "")
            if persona_text and is_new_session:
                full_persona = (
                    persona_text
                    + f"\nCurrent time: {datetime.now().strftime('%H:%M:%S')}"
                )
                messages = [
                    SystemMessage(content=full_persona, id=str(uuid4())),
                    *list(messages),
                ]

            turn_id = str(uuid4())
            config = {"configurable": {"thread_id": session_id}}

            yield {
                "type": "stream_start",
                "turn_id": turn_id,
                "session_id": session_id,
            }

            new_chats: list[BaseMessage] = []
            had_error = False
            had_hitl_request = False
            async for item in self._process_message(
                messages=messages,
                config=config,
                user_id=user_id,
                agent_id=agent_id,
                context=context,
            ):
                if item["type"] == "hitl_request":
                    had_hitl_request = True
                    yield item
                elif item["type"] != "final_response":
                    if item["type"] == "error":
                        had_error = True
                    yield item
                else:
                    new_chats = item["data"]

            if not had_error and not had_hitl_request:
                content = new_chats[-1].content if new_chats else ""
                yield {
                    "type": "stream_end",
                    "turn_id": turn_id,
                    "session_id": session_id,
                    "content": content,
                    "new_chats": new_chats,
                }
        except Exception:
            logger.exception("Error in stream method")
            raise

    async def resume_after_approval(
        self,
        session_id: str,
        approved: bool,
        request_id: str,
        *,
        user_id: str = "",
        agent_id: str = "",
        context: dict | None = None,
    ):
        """Resume graph after HitL approval/denial.

        CRITICAL: Command(resume=...) is passed as the FIRST POSITIONAL argument
        to astream, replacing the normal input dict. This is the documented
        LangGraph resume convention.
        """
        from langgraph.types import Command

        config = {"configurable": {"thread_id": session_id}}
        resume_value = Command(resume={"approved": approved, "request_id": request_id})
        astream_iter = self.agent.astream(
            resume_value,
            config=config,
            stream_mode=["messages", "updates"],
            context=context,
        )
        async for event in self._consume_astream(astream_iter, session_id):
            if event["type"] == "final_response":
                new_chats = event["data"]
                content = new_chats[-1].content if new_chats else ""
                yield {
                    "type": "stream_end",
                    "turn_id": "",
                    "session_id": session_id,
                    "content": content,
                    "new_chats": new_chats,
                }
            else:
                yield event

    async def invoke(
        self,
        messages: list[BaseMessage],
        session_id: str = "",
        persona_id: str = "",
        user_id: str = "default_user",
        agent_id: str = "default_agent",
        context: dict | None = None,
        is_new_session: bool = False,
    ) -> dict:
        """Invoke agent and return final result without streaming."""
        logger.debug(f"Starting LLM invoke: {len(messages)} messages")
        try:
            persona_text = self._personas.get(persona_id, "")
            if persona_text and is_new_session:
                full_persona = (
                    persona_text
                    + f"\nCurrent time: {datetime.now().strftime('%H:%M:%S')}"
                )
                messages = [
                    SystemMessage(content=full_persona, id=str(uuid4())),
                    *list(messages),
                ]

            config = {"configurable": {"thread_id": session_id}}
            input_count = len(messages)

            result = await self.agent.ainvoke(
                {"messages": messages, "user_id": user_id, "agent_id": agent_id},
                config=config,
                context=context,
            )

            all_messages: list[BaseMessage] = result.get("messages", [])
            new_chats = all_messages[input_count:]
            content = new_chats[-1].content if new_chats else ""

            logger.info(f"Invoke completed: {len(new_chats)} new messages")
            return {"content": content, "new_chats": new_chats}

        except Exception:
            logger.exception("Error in invoke method")
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
        user_id: str = "",
        agent_id: str = "",
        context: dict | None = None,
    ):
        """Process messages and yield streaming events."""
        logger.debug(f"Processing {len(messages)} messages with agent")
        astream_iter = self.agent.astream(
            {"messages": messages, "user_id": user_id, "agent_id": agent_id},
            config=config,
            context=context,
            stream_mode=["messages", "updates"],
        )
        session_id = config["configurable"]["thread_id"]
        async for event in self._consume_astream(astream_iter, session_id):
            yield event

    async def _consume_astream(self, astream_iter, session_id: str):
        """Consume agent astream iterator, yielding streaming events."""
        node = None
        tool_called = False
        gathered = ""
        chunk_count = 0
        buffer = StreamingBuffer()
        new_chats: list[BaseMessage] = []

        try:
            async for stream_type, data in astream_iter:
                if stream_type == "updates":
                    if data.get("__interrupt__"):
                        interrupt_value = data["__interrupt__"][0].value
                        yield {
                            "type": "hitl_request",
                            "request_id": interrupt_value["request_id"],
                            "tool_name": interrupt_value["tool_name"],
                            "tool_args": interrupt_value["tool_args"],
                            "session_id": session_id,
                        }
                        return

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
            logger.info(f"Stream processing completed: {chunk_count} chunks")

        except Exception:
            logger.warning("Error in stream processing", exc_info=True)
            if remaining := buffer.flush():
                yield self._flush_buffer(node, remaining)
            yield {"type": "error", "error": "메시지 처리 중 오류가 발생했습니다."}
