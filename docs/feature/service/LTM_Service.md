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

## 4. Output Examples

### Memory Add Output (`add_memory`)

- output format: dict
- Note, this structure may vary based on LTM service.

```python
{
    'results': [
        {
            'id': '146b2c68-0770-45ae-8710-6612d4bb5303',
            'memory': 'Name is Nanami',
            'event': 'ADD'
        },
        # ... more memory items
    ],
    'relations': {
        'deleted_entities': [[], [], []],
        'added_entities': [
            [{'source': 'nanami', 'relationship': 'is', 'target': 'researcher'}],
            # ... more relations
        ]
    }
}
```

### Memory Search Output (`search_memory`)

- output format: dict
- Note, this structure may vary based on LTM service.

```python
{
    'results': [
        {
            'id': 'eb47bffb-95a8-4bc5-a24b-70a0d9c4a9c1',
            'memory': 'Yuri is a Live2D desktop girl',
            'hash': '9b5a5a1fcb7632d250d995a7367a021d',
            'metadata': None,
            'score': 0.57437557,
            'created_at': '2025-11-30T21:13:00.607828-08:00',
            'updated_at': None,
            'user_id': 'nanami_user',
            'agent_id': 'yuri'
        },
        # ... more results
    ],
    'relations': [
        {'source': 'nanami', 'relationship': 'is', 'destination': 'researcher'},
        # ... more relations
    ]
}
```

**Note:** The output keys and structure may vary slightly depending on the underlying memory framework configuration, but generally follow a `{'results': [...], 'relations': [...]}` pattern.

---

## Appendix

### A. Related Documents

- [Service Layer](./README.md)
- [LTM Configuration](../config/LTM_Config_Fields.md)
