from typing import List

from langchain_core.messages import (
    BaseMessage,
    AIMessage,
    SystemMessage,
    HumanMessage,
    ToolMessage,
)


def trim_messages(
    messages: List[BaseMessage], max_messages: int = 20
) -> List[BaseMessage]:
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
    return return_messages
