import os

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from mem0 import Memory

from src.core.logger import setup_logging
from src.services.agent_service.state import Configuration
from src.services.agent_service.tools.memory import AddMemoryTool, SearchMemoryTool
from src.services.agent_service.tools.memory.metadata_manager import (
    PostgreSQLVocabularyManager,
)
from src.services.agent_service.utils import (
    TextChunkProcessor,
    TTSTextProcessor,
    process_message,
    process_stream_pipeline,
)

logger = setup_logging("chat_agent")


class ChatAgent:
    """
    ChatAgent는 메모리 기반 도구와 LLM을 사용하여 대화형 에이전트를 생성하고 메시지를 처리합니다.
    """

    def __init__(
        self,
        mem0_client: Memory,
        llm: BaseChatModel,
        vocabulary_manager: PostgreSQLVocabularyManager,
        text_chunk_processor: TextChunkProcessor = TextChunkProcessor(),
        text_processor: TTSTextProcessor = TTSTextProcessor(),
    ):
        self._mem0_client = mem0_client
        self._llm = llm
        self._vocabulary_manager = vocabulary_manager
        self._text_chunk_processor = text_chunk_processor
        self._text_processor = text_processor

    def _init_tools(self, agent_id: str, user_id: str):
        """Create the agent graph for memory operations."""
        add_memory_tool = AddMemoryTool(
            mem0_client=self._mem0_client,
            user_id=user_id,
            agent_id=agent_id,
            vocabulary_manager=self._vocabulary_manager,
        )
        search_memory_tool = SearchMemoryTool(
            mem0_client=self._mem0_client,
            user_id=user_id,
            agent_id=agent_id,
            vocabulary_manager=self._vocabulary_manager,
        )
        return add_memory_tool, search_memory_tool

    async def make_agent(
        self,
        config: Configuration,
        system_prompt: str = None,
        mcp_config: dict = None,
    ):
        """Create the memory agent with tools bound to LLM."""
        add_memory_tool, search_memory_tool = self._init_tools(
            agent_id=config.agent_id,
            user_id=config.user_id,
        )
        tools = [add_memory_tool, search_memory_tool]
        client = MultiServerMCPClient(mcp_config)
        mcp_tools = await client.get_tools()
        memory = MemorySaver()

        agent = create_react_agent(
            self._llm,
            tools=tools + mcp_tools,
            prompt=system_prompt,
            checkpointer=memory,
        )
        return agent

    async def process_message(
        self,
        messages: list[BaseMessage],
        agent: CompiledStateGraph,
        config: RunnableConfig,
    ):
        """메시지를 처리하고 스트리밍 응답을 생성합니다."""
        async for response in process_message(messages, agent, config):
            if response.get("node") == "agent" and not response.get("tool_name"):
                yield process_stream_pipeline(
                    response, self._text_chunk_processor, self._text_processor
                )
            elif response.get("type") == "tool_call":
                logger.info(
                    "Client #%s 도구 호출: %s (args: %s)",
                    config.run_id,
                    response.get("tool_name"),
                    response.get("args"),
                )
            elif response.get("node") == "tools":
                logger.info(
                    "Client #%s 도구 응답: %s (args: %s)",
                    config.run_id,
                    response.get("tool_name"),
                    response.get("args"),
                )
            elif response.get("type") == "end":
                logger.info(
                    "Client #%s 상태 업데이트: %s, message: %s",
                    config.run_id,
                    response.get("message_history"),
                    response.get("message"),
                )
                response.get("message_history", None)
                self._text_chunk_processor.reset()


if __name__ == "__main__":
    # 프로세서들은 한 번만 초기화합니다.
    import os

    from dotenv import load_dotenv

    from src.configs.mem0_configs import MEM0_CONFIG, VOCABULARY_DB_CONFIG
    from src.services.agent_service.llm_factory import LLMFactory

    load_dotenv()
    mem0_client = Memory.from_config(MEM0_CONFIG)

    # Initialize vocabulary manager
    vocabulary_manager = PostgreSQLVocabularyManager(db_config=VOCABULARY_DB_CONFIG)
    llm = LLMFactory(
        service_type="openai",
        model=os.getenv("LLM_MODEL_NAME"),
        openai_api_key=os.getenv("LLM_API_KEY"),
        openai_api_base=os.getenv("LLM_BASE_URL"),
    )
    chat_agent = ChatAgent(
        mem0_client=mem0_client, vocabulary_manager=vocabulary_manager, llm=llm
    )
    agent = chat_agent.make_agent(
        config=Configuration(
            agent_id="example_agent",
            user_id="example_user",
        )
    )
