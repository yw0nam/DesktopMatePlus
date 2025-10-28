import json
import logging
import os
import traceback
from uuid import uuid4

import psycopg
from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain_postgres import PostgresChatMessageHistory
from langgraph.checkpoint.memory import BaseCheckpointSaver, MemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from mem0 import Memory

from src.services.agent_service.service import AgentService
from src.services.agent_service.tools.memory import AddMemoryTool, SearchMemoryTool
from src.services.agent_service.utils.mem0_configs import (
    MEM0_CONFIG,
    POSTGRES_DB_CONFIG,
)
from src.services.agent_service.utils.message_util import check_table_exists

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

__doc__ = """
This module contains the implementation of the AgentFactory class, which provides functionality for processing chat messages using a language model and tools from a Multi-Server MCP client.

Classes:
- AgentFactory: A class that encapsulates the logic for message processing and tool interaction.

Functions:
- process_message: Processes incoming messages asynchronously through an agent and yields responses or tool calls.
- stream: Initializes the agent with the provided language model and configuration, then streams message processing results.

Example usage:
    llm = LLMFactory.get_llm_service(...)
    agent_factory = AgentFactory(llm)
    async for result in agent_factory.stream(messages=[...], mcp_config={...}):
        print(result)
"""


class OpenAIChatAgent(AgentService):
    """OpenAI Chat Agent for processing messages.

    Args:
        temperature (float): Sampling temperature for the language model.
        top_p (float): Nucleus sampling parameter.
        openai_api_key (str, optional): OpenAI API key.
        openai_api_base (str, optional): Base URL for OpenAI API.
        model_name (str, optional): Name of the language model to use.
        **kwargs: Additional arguments for the base AgentService class.
    """

    def __init__(
        self,
        temperature: float,
        top_p: float,
        openai_api_key: str = None,
        openai_api_base: str = None,
        model_name: str = None,
        **kwargs,
    ):
        self.temperature = temperature
        self.top_p = top_p
        self.openai_api_key = openai_api_key
        self.openai_api_base = openai_api_base
        self.model_name = model_name
        super().__init__(**kwargs)
        logger.info(
            "AgentFactory initialized with model: %s, checkpoint: %s",
            self.llm,
            self.checkpoint,
        )

    def initialize_model(self) -> tuple[BaseChatModel, BaseCheckpointSaver]:
        llm = ChatOpenAI(
            temperature=self.temperature,
            top_p=self.top_p,
            openai_api_key=self.openai_api_key,
            openai_api_base=self.openai_api_base,
            model_name=self.model_name,
        )
        memory_saver = MemorySaver()
        return llm, memory_saver

    def init_memory(
        self,
        user_id: str,
        agent_id: str,
        conversation_id: str = "default_session",
        db_table_name: str = "chat_history",
    ) -> tuple[Memory, PostgresChatMessageHistory, list[BaseTool]]:
        """
        Initializes memory components for the agent.
        Args:
            user_id (str): Persistent user/client identifier.
            agent_id (str): Persistent agent identifier.
            conversation_id (str, optional): Conversation/session identifier.
            db_table_name (str): Database table name for chat history.
        Returns:
            tuple: A tuple containing the Memory instance, PostgresChatMessageHistory instance, and a list of memory tools.
        """

        sync_connection = psycopg.connect(**POSTGRES_DB_CONFIG)
        mem0_client = Memory.from_config(MEM0_CONFIG)

        add_memory_tool = AddMemoryTool(
            mem0_client=mem0_client,
            user_id=user_id,
            agent_id=agent_id,
        )
        search_memory_tool = SearchMemoryTool(
            mem0_client=mem0_client,
            user_id=user_id,
            agent_id=agent_id,
        )
        table_name = f"{user_id}_{db_table_name}"
        if not check_table_exists(sync_connection, table_name):
            PostgresChatMessageHistory.create_tables(sync_connection, table_name)

        chat_history = PostgresChatMessageHistory(
            table_name,
            conversation_id,
            sync_connection=sync_connection,
        )
        memory_tools = [add_memory_tool, search_memory_tool]
        return mem0_client, chat_history, memory_tools

    async def is_healthy(self) -> tuple[bool, str]:
        """
        Performs a health check on the agent by sending a test message
        and verifying a response is received.
        Returns:
            tuple: A tuple containing a boolean indicating health status and a message.
        """
        try:
            test_message = [AIMessageChunk(content="Health check")]
            response_received = False
            stream = self.stream(
                messages=test_message,
                client_id="health_check",
            )
            try:
                async for _response in stream:
                    response_received = True
                    break  # Just check if we get any response
            finally:
                await stream.aclose()

            if response_received:
                return True, "Agent is healthy."
            else:
                return False, "Agent did not respond."
        except Exception as e:
            logger.error("Health check failed: %s", e)
            return False, f"Health check failed: {e}"

    async def stream(
        self,
        messages: list[BaseMessage],
        client_id: str,
        tools: list[BaseTool] = None,
        user_id: str = "default_user",
        agent_id: str = "default_agent",
        with_memory: bool = False,
    ):
        """
        Streams the processing of messages through the agent.

        Args:
            messages (list[BaseMessage]): List of messages to process.
            client_id (str): Identifier for the client. Note: this should be generated by uuid4()
            tools (list[BaseTool], optional): Additional tools for the agent.
            user_id (str): Persistent user/client identifier.
            agent_id (str): Persistent agent identifier.
            with_memory (bool): Whether to initialize memory for the agent.
        Yields:
            dict: Streaming response chunks including start, tokens, tool calls, tool results, and end
        """
        if tools is None:
            tools = []
        logger.info(f"Starting LLM stream for messages: {messages}")
        logger.info(f"MCP Config: {self.mcp_config}")
        try:
            client = MultiServerMCPClient(self.mcp_config)

            mcp_tools = await client.get_tools()
            logger.info(
                "Fetched %d tools from MCP client: %s",
                len(mcp_tools),
                [tool.name for tool in mcp_tools],
            )
            # memory_initialization
            if with_memory:
                _memory, chat_history_manager, memory_tools = self.init_memory(
                    user_id, agent_id, conversation_id=client_id
                )
                tools += memory_tools

                # Message processing with memory retrieval
                retrieved_message = chat_history_manager.get_messages()
                length_of_message = len(
                    retrieved_message
                )  # Message Length for trimming
                retrieved_memory = _memory.search(
                    query=messages[0].content, user_id=user_id, agent_id=agent_id
                )
                if retrieved_memory:
                    logger.debug(
                        "Retrieved %d relevant memory items for user '%s' and agent '%s'.",
                        len(retrieved_memory),
                        user_id,
                        agent_id,
                    )

                messages = (
                    retrieved_message
                    + [SystemMessage(json.dumps(retrieved_memory, ensure_ascii=False))]
                    + messages
                )

            logger.debug("Creating react agent.")
            agent = create_react_agent(
                self.llm,
                tools=tools + mcp_tools if tools else mcp_tools,
                checkpointer=self.checkpoint,
            )
            run_id = str(uuid4())
            config = {"configurable": {"thread_id": client_id}}

            # stream 메서드는 process_message 라는 비동기 제너레이터를 반환합니다.
            yield {
                "type": "stream_start",
                "data": {"turn_id": run_id, "client_id": client_id},
            }
            async for item in self._process_message(
                messages=messages, agent=agent, config=config
            ):
                yield item

            yield {
                "type": "stream_end",
                "data": {
                    "turn_id": run_id,
                    "client_id": client_id,
                },
            }
            if with_memory:
                complete_message = agent.get_state(config=config).values["messages"]
                complete_message = complete_message[
                    length_of_message:
                ]  # Trim old messages
                # TODO: Trim retrieved memory System Message?
                chat_history_manager.add_messages(complete_message)
        except Exception as e:
            logger.error(f"Error in stream method: {e}")

            traceback.print_exc()
            raise

    async def _process_message(
        self,
        messages: list[BaseMessage],
        agent: CompiledStateGraph,
        config: RunnableConfig,
    ):
        """메시지를 처리하고 스트리밍 응답을 생성합니다."""
        logger.debug("Processing message with agent for %d messages", len(messages))

        node = None
        tool_called = False
        gathered = ""
        content_buffer = ""

        # 개선된 버퍼링 설정
        MIN_BUFFER_SIZE = 20  # 최소 버퍼 크기 (더 큰 청크로 전송)
        MAX_BUFFER_SIZE = 100  # 최대 버퍼 크기 (메모리 보호)

        # 문장 종료 문자 (더 자연스러운 분할점)
        SENTENCE_ENDINGS = (".", "!", "?", "\n")
        WORD_ENDINGS = (" ", ",", ";", ":")

        chunk_count = 0

        try:
            async for msg, metadata in agent.astream(
                {"messages": messages}, stream_mode="messages", config=config
            ):
                # 노드 변경 처리 (로깅만, 클라이언트 전송 없음)
                if node != metadata.get("langgraph_node"):
                    node = metadata.get("langgraph_node", "unknown")

                # 일반 메시지 콘텐츠 처리
                if isinstance(msg.content, str) and not msg.additional_kwargs:
                    content = msg.content

                    # 빈 콘텐츠 및 공백만 있는 콘텐츠 스킵
                    if not content or content.isspace():
                        continue

                    # 버퍼에 콘텐츠 추가
                    content_buffer += content

                    # 메모리 보호: 최대 크기 초과 시 강제 전송
                    if len(content_buffer) > MAX_BUFFER_SIZE:
                        if content_buffer.strip():
                            if node == "tools":
                                yield {
                                    "event": "tool_result",
                                    "data": {
                                        "execution_result": content_buffer.strip()
                                    },
                                    "node": node,
                                }
                            elif node == "agent":
                                yield {
                                    "event": "stream_token",
                                    "data": {"chunk": content_buffer.strip()},
                                    "node": node,
                                }
                            chunk_count += 1
                        content_buffer = ""
                        continue

                    # 자연스러운 분할점에서 전송
                    should_send = False

                    # 1. 문장 종료 시 전송
                    if (
                        content.endswith(SENTENCE_ENDINGS)
                        and len(content_buffer) >= MIN_BUFFER_SIZE
                    ):
                        should_send = True
                    # 2. 단어 종료 시 최소 크기 확인 후 전송
                    elif (
                        content.endswith(WORD_ENDINGS)
                        and len(content_buffer) >= MIN_BUFFER_SIZE * 2
                    ):
                        should_send = True

                    if should_send and content_buffer.strip():
                        if node == "tools":
                            yield {
                                "type": "tool_result",
                                "data": content_buffer.strip(),
                                "node": node,
                            }
                        elif node == "agent":
                            yield {
                                "type": "stream_token",
                                "data": content_buffer.strip(),
                                "node": node,
                            }
                        chunk_count += 1
                        content_buffer = ""

                # AI 메시지 청크 및 툴 콜 처리 (향후 MCP 재활성화 대비)
                elif isinstance(msg, AIMessageChunk) and msg.additional_kwargs.get(
                    "tool_calls"
                ):
                    if not tool_called:
                        gathered = msg
                        tool_called = True
                    else:
                        gathered = gathered + msg

                    # 툴 콜 완성 확인
                    if hasattr(msg, "tool_call_chunks") and msg.tool_call_chunks:
                        tool_info = gathered.tool_call_chunks[0]
                        args_str = tool_info.get("args", "")
                        if args_str and args_str.strip().endswith("}"):
                            tool_name = tool_info.get("name", "unknown")
                            logger.info(f"Tool call detected: '{tool_name}'")
                            yield {
                                "type": "tool_call",
                                "data": {
                                    "tool_name": tool_name,
                                    "args": args_str,
                                },
                                "node": node,
                            }
                            # 상태 리셋
                            tool_called = False
                            gathered = ""

            # 마지막 버퍼 처리
            if content_buffer.strip():
                if node == "tools":
                    yield {
                        "type": "tool_result",
                        "data": content_buffer.strip(),
                        "node": node,
                    }
                elif node == "agent":
                    yield {
                        "type": "stream_token",
                        "data": content_buffer.strip(),
                        "node": node,
                    }
                chunk_count += 1

            logger.info(f"Message processing completed. Total chunks: {chunk_count}")

        except Exception as e:
            logger.error(f"Error in process_message: {e}")
            # 버퍼에 남은 내용이 있으면 먼저 전송
            if content_buffer.strip():
                yield {
                    "type": "tool_result",
                    "data": content_buffer.strip(),
                    "node": node,
                }
            elif node == "agent":
                yield {
                    "type": "stream_token",
                    "data": content_buffer.strip(),
                    "node": node,
                }
            yield {
                "type": "error",
                "data": "메시지 처리 중 오류가 발생했습니다.",
            }


if __name__ == "__main__":
    import asyncio
    import os
    from uuid import uuid4

    from dotenv import load_dotenv
    from langchain_core.messages import HumanMessage

    load_dotenv()

    mcp_config = {
        "sequential-thinking": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
            "transport": "stdio",
        }
    }
    agent_factory = OpenAIChatAgent(
        temperature=0.7,
        top_p=0.9,
        openai_api_key=os.getenv("LLM_API_KEY"),
        openai_api_base=os.getenv("LLM_BASE_URL"),
        model_name=os.getenv("LLM_MODEL_NAME"),
        mcp_config=mcp_config,
    )

    async def test_agent_factory():
        async for result in agent_factory.stream(
            messages=[
                HumanMessage(
                    content="Hello, can you help me?, Use Sequential Thinking for answer."
                )
            ],
            client_id=str(uuid4()),
            tools=[],
            user_id="test_user_1",
            agent_id="test_agent_1",
        ):
            print(result)

    asyncio.run(test_agent_factory())
