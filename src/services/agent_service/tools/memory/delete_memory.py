from langchain_core.tools import BaseTool
from mem0 import Memory

from src.services.agent_service.tools.memory.schemas import DeleteMemoryInput


class DeleteMemoryTool(BaseTool):
    """A tool to permanently delete a memory using its unique ID."""

    name: str = "delete_memory"
    description: str = "Warning: This tool permanently deletes a memory. Use with extreme caution. It requires the exact memory ID and the user's ID."
    args_schema: type[DeleteMemoryInput] = DeleteMemoryInput
    mem0_client: Memory

    def __init__(self, mem0_client: Memory, user_id: str):
        super().__init__(mem0_client=mem0_client)
        self.user_id = user_id

    def _run(self, memory_id: str) -> str:
        """Deletes a memory synchronously."""
        try:
            self.mem0_client.delete(id=memory_id, user_id=self.user_id)
            return f"Memory with ID '{memory_id}' has been permanently deleted."
        except Exception as e:
            return f"Error deleting memory: {e}"
