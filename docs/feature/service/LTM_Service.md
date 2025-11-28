# LTM Service (Long-Term Memory)

Updated: 2025-11-28

## 1. Synopsis

- **Purpose**: Semantic long-term memory for user preferences and context using mem0
- **I/O**: Conversation messages → Extracted memories; Query → Relevant memories

## 2. Core Logic

### Interface Methods

| Method | Input | Output |
|--------|-------|--------|
| `initialize_memory()` | - | `MemoryClientType` |
| `is_healthy()` | - | `(bool, str)` |
| `search_memory()` | query, user_id, agent_id | `dict` |
| `add_memory()` | messages, user_id, agent_id | `dict` |
| `delete_memory()` | user_id, agent_id, memory_id | `dict` |

### Implementation: Mem0LTM

- mem0 library integration
- Vector store (Qdrant) for semantic search
- Graph store (Neo4j) for relationships
- LLM-powered memory extraction

### Architecture Components

| Component | Provider | Purpose |
|-----------|----------|---------|
| LLM | OpenAI-compatible | Memory extraction |
| Embedder | LangChain | Text embeddings |
| Vector Store | Qdrant | Semantic search |
| Graph Store | Neo4j | Relationship mapping |

### Configuration

```yaml
# yaml_files/services/ltm_service/mem0.yml
ltm_config:
  type: "mem0"
  configs:
    llm:
      provider: "openai"
      config:
        openai_base_url: "http://localhost:55235/v1"
        model: "chat_model"
    embedder:
      provider: "langchain"
      config:
        openai_base_url: "http://localhost:5504/v1"
        model_name: "chat_model"
        embedding_dims: 2560
    vector_store:
      provider: "qdrant"
      config:
        url: "localhost"
        collection_name: "ltm_collection"
    graph_store:
      provider: "neo4j"
      config:
        url: "bolt://localhost:7687"
```

## 3. Usage

```python
from src.services import get_ltm_service
from langchain_core.messages import HumanMessage, AIMessage

ltm = get_ltm_service()

# Search for relevant memories
results = ltm.search_memory(
    query="user preferences for coffee",
    user_id="user_001",
    agent_id="agent_001"
)

# Add memories from conversation
ltm.add_memory(
    messages=[
        HumanMessage(content="I prefer dark roast coffee"),
        AIMessage(content="Noted! I'll remember you like dark roast.")
    ],
    user_id="user_001",
    agent_id="agent_001"
)

# Delete specific memory
ltm.delete_memory(
    user_id="user_001",
    agent_id="agent_001",
    memory_id="mem_12345"
)
```

---

## Appendix

### A. Related Documents

- [Service Layer](./README.md)
- [LTM Configuration](../config/LTM_Config_Fields.md)
