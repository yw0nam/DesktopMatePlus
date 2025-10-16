from typing import Optional, Dict, Any

from src.tools.memory.schemas import UpdateMemoryInput
from langchain_core.tools import BaseTool
from mem0 import Memory


class UpdateMemoryTool(BaseTool):
    """A tool to update an existing memory using its unique ID."""

    name: str = "update_memory"
    description: str = (
        "Use this tool to update an existing memory. You must provide the memory's unique ID, the user's ID, and a payload with the fields to update."
    )
    args_schema: type[UpdateMemoryInput] = UpdateMemoryInput
    mem0_client: Memory

    def __init__(self, mem0_client: Memory, user_id: str):
        super().__init__(mem0_client=mem0_client, user_id=user_id)
        self.user_id = user_id

    def _run(self, memory_id: str, payload: Dict[str, Any]) -> str:
        """Updates a memory synchronously."""
        try:
            # mem0-python 라이브러리의 update 메서드는 payload를 직접 받지 않고,
            # content와 metadata를 개별 인자로 받을 수 있습니다.
            # 따라서 payload에서 해당 키를 추출하여 전달합니다.
            update_data = {
                "id": memory_id,
                "user_id": self.user_id,
                **payload,  # content, metadata 등을 payload에서 언패킹
            }
            self.mem0_client.update(**update_data)
            return f"Memory with ID '{memory_id}' updated successfully."
        except Exception as e:
            return f"Error updating memory: {e}"
