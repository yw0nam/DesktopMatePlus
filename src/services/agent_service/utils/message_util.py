
import psycopg
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)


def trim_messages(
    messages: list[BaseMessage], max_messages: int = 20
) -> dict[str, list[BaseMessage]]:
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
            if isinstance(message, HumanMessage) or (isinstance(message, AIMessage) and message.content.strip() != ""):
                trimmed_messages.append(message)
            elif isinstance(message, ToolMessage | SystemMessage):
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


def strip_images_from_messages(messages: list[dict]) -> list[dict]:
    """
    Strip image content from messages, keeping only text.

    Args:
        messages: List of OpenAI-format message dictionaries

    Returns:
        list[dict]: Messages with images removed
    """
    stripped = []
    for msg in messages:
        msg_copy = msg.copy()
        content = msg_copy.get("content")

        if isinstance(content, list):
            # Filter out image_url items, keep only text
            text_items = [
                item
                for item in content
                if not (isinstance(item, dict) and item.get("type") == "image_url")
            ]

            # If only text items remain, simplify to string if single text
            if len(text_items) == 1 and text_items[0].get("type") == "text":
                msg_copy["content"] = text_items[0].get("text", "")
            elif text_items:
                msg_copy["content"] = text_items
            else:
                # All content was images, set to empty string
                msg_copy["content"] = ""

        stripped.append(msg_copy)
    return stripped
