import logging
import traceback
from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import BaseCheckpointSaver, MemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from src.services.agent_service.service import AgentService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

    async def is_healthy(self) -> tuple[bool, str]:
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

    async def process_message(
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

    async def stream(
        self,
        messages: list[BaseMessage],
        client_id: str = "default_client",
        tools: list[BaseTool] = None,
    ):
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

            logger.debug("Creating react agent.")
            agent = create_react_agent(
                self.llm,
                tools=tools + mcp_tools if tools else mcp_tools,
                checkpointer=self.checkpoint,
            )
            run_id = str(uuid4())
            config = {"configurable": {"thread_id": client_id}, "run_id": run_id}
            # stream 메서드는 process_message 라는 비동기 제너레이터를 반환합니다.
            yield {
                "type": "stream_start",
                "data": {"turn_id": run_id, "client_id": client_id},
            }
            async for item in self.process_message(
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
        except Exception as e:
            logger.error(f"Error in stream method: {e}")

            traceback.print_exc()
            raise


if __name__ == "__main__":
    import asyncio
    import os

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
            client_id="test_client_1",
            tools=[],
        ):
            print(result)

    asyncio.run(test_agent_factory())
