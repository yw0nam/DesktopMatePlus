# LTM Configuration Fields

## 1. Synopsis

- **Purpose**: Configure mem0-based Long-Term Memory with vector and graph stores
- **I/O**: YAML → `Mem0LongTermMemoryConfig` Pydantic model

## 2. Core Logic

### Component Structure

| Component | Provider | Purpose |
|-----------|----------|---------|
| `llm` | `openai` | Memory extraction |
| `embedder` | `langchain` | Text embeddings |
| `vector_store` | `qdrant` | Semantic search |
| `graph_store` | `neo4j` | Relationship mapping |

### LLM Config

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `openai_base_url` | str | `"http://localhost:55120/v1"` | LLM API URL |
| `api_key` | str | `$LTM_API_KEY` | API key (from env) |
| `model` | str | `"chat_model"` | Model name |
| `enable_vision` | bool | `True` | Enable vision support |

### Embedder Config

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `openai_base_url` | str | `"http://localhost:5504/v1"` | Embedder API URL |
| `openai_api_key` | str | `$EMB_API_KEY` | API key (from env) |
| `model_name` | str | `"chat_model"` | Model name |
| `embedding_dims` | int | `2560` | Embedding dimensions |

### Vector Store Config (Qdrant)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | str | `"http://localhost:6333"` | Qdrant URL |
| `embedding_model_dims` | int | `2560` | Embedding dimensions |
| `collection_name` | str | `"mem0_collection"` | Collection name |

### Graph Store Config (Neo4j)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | str | `"bolt://localhost:7687"` | Neo4j URL |
| `username` | str | `$NEO4J_USER` | Username (from env) |
| `password` | str | `$NEO4J_PASSWORD` | Password (from env) |

## 3. Usage

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
        enable_vision: true
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

---

## Appendix

### A. Related Documents

- [Configuration System](./README.md)
- [LTM Service](../service/LTM_Service.md)
