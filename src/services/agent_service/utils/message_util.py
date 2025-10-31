import logging
from typing import List

import psycopg
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger(__name__)


def trim_messages(
    messages: List[BaseMessage], max_messages: int = 20
) -> dict[str, List[BaseMessage]]:
    """
    Trim messages using message type.
    Preserve AI and Human messages, discard Tool and System messages except first system message.
    Args:
        messages (List[BaseMessage]): List of messages to trim.
        max_messages (int): Maximum number of messages to preserve.
    """

    trimmed_messages = []
    for message in reversed(messages):
        if len(trimmed_messages) < max_messages:
            if isinstance(message, HumanMessage):
                trimmed_messages.append(message)
            elif isinstance(message, AIMessage) and message.content.strip() != "":
                trimmed_messages.append(message)
            elif isinstance(message, (ToolMessage, SystemMessage)):
                continue
        else:
            break
    return_messages = list(reversed(trimmed_messages))
    return {"llm_input_messages": return_messages}


def check_table_exists(conn, table_name, schema_name="public"):
    """
    Checks if a table exists in the specified schema of a PostgreSQL database.

    Args:
        conn: A psycopg2 connection object.
        table_name: The name of the table to check.
        schema_name: The name of the schema where the table is expected (defaults to 'public').

    Returns:
        True if the table exists, False otherwise.
    """
    try:
        cursor = conn.cursor()
        query = """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = %s
                AND table_name = %s
            );
        """
        cursor.execute(query, (schema_name, table_name))
        exists = cursor.fetchone()[0]
        cursor.close()
        return exists
    except psycopg.Error as e:
        print(f"Error checking table existence: {e}")
        return False


async def process_message(
    messages: list[BaseMessage], agent: CompiledStateGraph, config: RunnableConfig
):
    """메시지를 처리하고 스트리밍 응답을 생성합니다."""

    chunk_count = 0
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
                        yield {
                            "type": "content",
                            "text": content_buffer.strip(),
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
                    yield {
                        "type": "content",
                        "text": content_buffer.strip(),
                        "node": node,
                    }
                    chunk_count += 1
                    content_buffer = ""

            # AI 메시지 청크 및 툴 콜 처리
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
                        yield {
                            "type": "tool_call",
                            "tool_name": tool_name,
                            "args": args_str,
                            "node": node,
                        }
                        # 상태 리셋
                        tool_called = False
                        gathered = ""

        # 마지막 버퍼 처리
        if content_buffer.strip():
            yield {
                "type": "content",
                "text": content_buffer.strip(),
                "node": node,
            }
            chunk_count += 1
        yield {
            "type": "end",
            "message": "LLM stream completed successfully.",
            "message_history": agent.get_state(config=config).values["messages"],
        }
    except Exception as e:
        # 버퍼에 남은 내용이 있으면 먼저 전송
        if content_buffer.strip():
            yield {"type": "content", "text": content_buffer.strip(), "node": node}
        yield {
            "type": "error",
            "message": f"메시지 처리 중 오류가 발생했습니다.{str(e)}",
        }
