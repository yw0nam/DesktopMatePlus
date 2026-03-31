# External Service Dependencies

DesktopMatePlus Backend requires the following external services. This guide covers installation and configuration.

## Overview

| Service | Purpose | Required | Default URL |
|---------|---------|----------|-------------|
| vLLM | Agent LLM & TTS Omni | Yes | `http://localhost:55235/v1` |
| Fish Speech | Alternative TTS | Optional | `http://localhost:8080` |
| MongoDB | Short-term memory | Yes | `mongodb://localhost:27017` |
| Qdrant | Long-term memory vectors | Yes | `http://localhost:6333` |
| Neo4j | LTM graph relations | Optional | `bolt://localhost:7687` |

## 1. vLLM Server (Agent LLM)

### Installation

```bash
# Install vLLM
pip install vllm

# Start server with your model
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --host 0.0.0.0 \
  --port 55235 \
  --api-key your-api-key
```

### Configuration

```yaml
# yaml_files/services/agent_service/openai_chat_agent.yml
llm_config:
  configs:
    openai_api_base: "http://localhost:55235/v1"
    model_name: "Qwen/Qwen2.5-7B-Instruct"
    temperature: 0.7
    support_image: true  # For vision support
```

### Supported Models

- Any OpenAI-compatible API
- vLLM-served models (Qwen, Llama, Mistral, etc.)
- OpenAI API directly

---

## 2. Fish Speech (TTS)

### Installation

See [Fish Speech GitHub](https://github.com/fishaudio/fish-speech) for complete setup.

```bash
git clone https://github.com/fishaudio/fish-speech.git
cd fish-speech
# Follow their installation instructions
```

### Start Server

```bash
python -m tools.api \
  --listen 0.0.0.0:8080 \
  --llama-checkpoint-path checkpoints/text2semantic-400m-v0.2-4k.pth \
  --decoder-checkpoint-path checkpoints/firefly-gan-vq-fsq-4x1024-42hz-generator.pth
```

### Configuration

```yaml
# yaml_files/services/tts_service/fish_speech.yml
tts_config:
  type: "fish_local_tts"
  configs:
    base_url: "http://localhost:8080/v1/tts"
    chunk_length: 200
    temperature: 0.7
```

### Reference Voices

Place reference audio files in `resources/reference_voices/`:

```text
resources/reference_voices/
├── voice_001.wav
├── voice_001.lab  # Text transcript
└── ...
```

---

## 3. MongoDB (Short-Term Memory)

### Installation

**Using Docker:**

```bash
docker run -d \
  --name mongodb \
  -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=password \
  mongo:7
```

**Native Installation:**

- Download from [MongoDB Community Server](https://www.mongodb.com/try/download/community)
- Follow platform-specific installation

### Configuration

```yaml
# yaml_files/services/stm_service/mongodb.yml
stm_config:
  type: "mongodb"
  configs:
    connection_string: "mongodb://admin:password@localhost:27017/"
    database_name: "stm_db"
    sessions_collection_name: "sessions"
    messages_collection_name: "messages"
```

### Verification

```bash
# Connect to MongoDB
mongosh "mongodb://admin:password@localhost:27017"

# Check collections
use stm_db
show collections
```

---

## 4. Qdrant (Long-Term Memory Vector Store)

### Installation

**Using Docker:**

```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

**Native Installation:**

```bash
# Download from https://github.com/qdrant/qdrant/releases
wget https://github.com/qdrant/qdrant/releases/download/v1.7.0/qdrant-x86_64-unknown-linux-gnu.tar.gz
tar -xvf qdrant-*.tar.gz
./qdrant
```

### Configuration

```yaml
# yaml_files/services/ltm_service/mem0.yml
ltm_config:
  configs:
    vector_store:
      provider: "qdrant"
      config:
        url: "localhost"
        port: 6333
        collection_name: "ltm_collection"
```

### Verification

```bash
# Check Qdrant health
curl http://localhost:6333/health
```

---

## 5. Neo4j (Optional - LTM Graph Store)

### Installation

**Using Docker:**

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  neo4j:latest
```

### Configuration

```yaml
# yaml_files/services/ltm_service/mem0.yml
ltm_config:
  configs:
    graph_store:
      provider: "neo4j"
      config:
        url: "bolt://localhost:7687"
        username: "neo4j"
        password: "your_password"
```

### Verification

- Open Neo4j Browser: `http://localhost:7474`
- Login with credentials

---

## Quick Start Script

```bash
#!/bin/bash
# start_services.sh

# Start MongoDB
docker run -d --name mongodb -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=password mongo:7

# Start Qdrant
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant

# Start vLLM (adjust model as needed)
vllm serve Qwen/Qwen2.5-7B-Instruct --host 0.0.0.0 --port 55235 &

# Start Fish Speech (if installed locally)
cd fish-speech && python -m tools.api --listen 0.0.0.0:8080 &

echo "All services started. Check logs for readiness."
```

---

## Health Checks

Use the backend's health endpoint to verify all services:

```bash
curl http://localhost:5500/v1/health

# Expected response:
{
  "status": "healthy",
  "modules": [
    {"name": "TTS", "ready": true},
    {"name": "Agent", "ready": true},
    {"name": "LTM", "ready": true},
    {"name": "STM", "ready": true}
  ]
}
```

---

## Troubleshooting

### MongoDB Connection Failed

```bash
# Check MongoDB is running
docker ps | grep mongodb

# Check connection string in .env
mongodb://admin:password@localhost:27017/
```

### Qdrant Not Responding

```bash
# Check Qdrant logs
docker logs qdrant

# Verify port is exposed
curl http://localhost:6333/health
```

### vLLM Server Errors

```bash
# Check GPU availability
nvidia-smi

# Verify model is downloaded
ls ~/.cache/huggingface/hub/
```

---

## Related Documents

- [Environment Variables](./ENVIRONMENT.md)
- [Service Configuration](../feature/config/README.md)
- [Health Service](../feature/service/README.md)
