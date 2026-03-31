# Environment Variables

Complete guide to environment variables for DesktopMatePlus Backend.

## Required Variables

### Agent Service (OpenAI-compatible LLM)

```bash
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=http://localhost:55235/v1  # Optional, defaults to OpenAI
```

### MongoDB (Short-Term Memory)

```bash
MONGODB_URI=mongodb://admin:password@localhost:27017/
MONGODB_DB_NAME=desktopmate_stm
```

## Optional Variables

### Text-to-Speech (Fish Speech)

```bash
TTS_SERVER_URL=http://localhost:8080
TTS_REFERENCE_AUDIO_DIR=./resources/reference_voices
```

### Text-to-Speech (vLLM Omni - Alternative)

```bash
VLLM_OMNI_BASE_URL=http://localhost:5504/v1
VLLM_OMNI_MODEL_NAME=fixie-ai/ultravox-v0_4-gguf
```

### Long-Term Memory (mem0)

```bash
# Option 1: mem0 Cloud
MEM0_API_KEY=your_mem0_api_key

# Option 2: Self-hosted with Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_qdrant_key  # Optional for local Qdrant
QDRANT_COLLECTION_NAME=ltm_collection

# Option 3: Neo4j Graph Store
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
```

### Embedder Service (for LTM)

```bash
EMB_API_KEY=your_embedding_api_key
EMB_BASE_URL=http://localhost:5504/v1
EMB_MODEL_NAME=BAAI/bge-m3
```

### Server Configuration

```bash
HOST=0.0.0.0
PORT=5500
LOG_LEVEL=INFO           # DEBUG, INFO, WARNING, ERROR
LOG_RETENTION="30 days"  # Loguru retention period
DEBUG=false              # Enable FastAPI debug mode
```

### CORS Configuration

```bash
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8080"]
```

## Example .env File

```bash
# Agent
OPENAI_API_KEY=sk-your-key-here

# TTS
TTS_SERVER_URL=http://localhost:8080

# Memory
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB_NAME=desktopmate_stm
QDRANT_URL=http://localhost:6333

# Server
HOST=0.0.0.0
PORT=5500
LOG_LEVEL=INFO
DEBUG=false
```

## Loading Order

1. `.env` file in project root
2. System environment variables (override .env)
3. YAML config files in `yaml_files/` (service-specific)

## Security Best Practices

- **Never commit `.env`** — Add to `.gitignore`
- **Use secrets management** in production (AWS Secrets Manager, HashiCorp Vault)
- **Rotate API keys** regularly
- **Use read-only keys** where possible
- **Restrict MongoDB/Qdrant access** with proper authentication

---

## Related Documents

- [Dependencies Setup](./DEPENDENCIES.md)
- [Configuration System](../feature/config/README.md)
