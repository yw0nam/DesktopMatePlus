# STM Service (Short-Term Memory)

Updated: 2025-12-04

## 1. Synopsis

- **Purpose**: Session-based chat history and conversation management using MongoDB
- **I/O**: User/Agent IDs + Messages → Stored sessions and chat history

> **Note**: Images are stripped from messages before storage. Only text content is preserved in chat history. This is because the current screen context matters for the agent, not the history of previous screens.

## 2. Core Logic

### Interface Methods

| Method | Input | Output |
|--------|-------|--------|
| `initialize_memory()` | - | `MemoryClientType` |
| `is_healthy()` | - | `(bool, str)` |
| `add_chat_history()` | user_id, agent_id, session_id, messages | `str` (session_id) |
| `get_chat_history()` | user_id, agent_id, session_id, limit | `list[BaseMessage]` |
| `list_sessions()` | user_id, agent_id | `list[dict]` |
| `delete_session()` | user_id, agent_id, session_id | `bool` |
| `update_session_metadata()` | user_id, agent_id, session_id, metadata | `bool` |

### Data Model

```python
# Session
{
    "session_id": "uuid",
    "user_id": "user_001",
    "agent_id": "agent_001",
    "created_at": datetime,
    "updated_at": datetime,
    "metadata": {}
}

# Message (OpenAI-compatible format, text only)
{
    "session_id": "uuid",
    "role": "user|assistant|system",
    "content": "...",  # Images are stripped, only text is stored
    "timestamp": datetime
}
```

### Implementation: MongoDBSTM

- MongoDB-backed storage
- Separate collections for sessions and messages
- Images are stripped from messages (text only storage)
- OpenAI-compatible message format
- Idempotent session creation using MongoDB upsert operations
- Session timestamps: `created_at` (set once), `updated_at` (refreshed on each update)

### Configuration

```yaml
# yaml_files/services/stm_service/mongodb.yml
stm_config:
  type: "mongodb"
  configs:
    connection_string: "mongodb://admin:test@localhost:27017/"
    database_name: "stm_db"
    sessions_collection_name: "sessions"
    messages_collection_name: "messages"
```

## 3. Usage

```python
from src.services import get_stm_service
from langchain_core.messages import HumanMessage, AIMessage

stm = get_stm_service()

# Create new session and add messages
session_id = stm.add_chat_history(
    user_id="user_001",
    agent_id="agent_001",
    session_id=None,  # Creates new session
    messages=[
        HumanMessage(content="Hello!"),
        AIMessage(content="Hi there!")
    ]
)

# Get chat history
history = stm.get_chat_history(
    user_id="user_001",
    agent_id="agent_001",
    session_id=session_id,
    limit=10
)

# List all sessions
sessions = stm.list_sessions(user_id="user_001", agent_id="agent_001")
```

---

## Appendix

### A. Related Documents

- [Service Layer](./README.md)
- [STM Configuration](../config/STM_Config_Fields.md)
- [STM API Endpoints](../../api/REST_API_GUIDE.md)
