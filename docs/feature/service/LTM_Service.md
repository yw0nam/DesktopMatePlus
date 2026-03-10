# LTM Service (Long-Term Memory)

Updated: 2026-03-10

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

## 3. Consolidation Policy

`add_memory`는 매 턴 호출하지 않습니다. 단편적 메시지로 Mem0를 호출하면 쓸모없는 정보가 Graph/Vector에 누적됩니다.

### Turn-based Batch Consolidation (STM metadata 기반)

- **턴 카운트**: `sum(1 for m in history if isinstance(m, HumanMessage))` — HumanMessage만 카운트.
- **트리거**: STM `session.metadata.ltm_last_consolidated_at_turn`을 읽어 `current_turn - last_consolidated >= LTM_CONSOLIDATION_TURN_INTERVAL` 조건으로 트리거.
- **슬라이스**: `last_consolidated` 번째 HumanMessage 위치를 순회하여 정확한 시작점부터 메시지 추출.
- **배치**: 시작점 이후 메시지를 한 번에 `ltm_service.add_memory()`에 전달 → Mem0 추출 품질 향상.
- **구현**: `AgentService.save_memory()` 내부에서 처리.

```python
# AgentService (service.py)
LTM_CONSOLIDATION_TURN_INTERVAL = 10

current_turn = sum(1 for m in history if isinstance(m, HumanMessage))
last_consolidated = metadata.get("ltm_last_consolidated_at_turn", 0)

if current_turn - last_consolidated >= LTM_CONSOLIDATION_TURN_INTERVAL:
    # Find slice start at last_consolidated-th HumanMessage
    messages_since_last = history[slice_start:]
    ltm_service.add_memory(messages=messages_since_last, ...)
    stm_service.update_session_metadata(session_id, {
        "ltm_last_consolidated_at_turn": current_turn
    })
```

**장점:**
- 재시작/멀티프로세스 안전 (카운트가 DB에 영속됨)
- TOCTOU 중복 트리거 없음
- 추가 STM read 불필요 (metadata는 이미 조회)

## 4. Usage

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

## 5. Output Examples

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

## 6. Appendix

### A. Related Documents

- [Service Layer](./README.md)
- [LTM Configuration](../config/LTM_Config_Fields.md)
