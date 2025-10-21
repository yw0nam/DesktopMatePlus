# LangGraph Agent Implementation Guide

## Overview

This document describes the implementation of the LangGraph Agent with five core nodes for the DesktopMate+ desktop assistant.

## Architecture

### GraphState Structure

The agent uses an enhanced `GraphState` TypedDict with the following fields:

```python
class GraphState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], add_messages]  # Conversation history
    visual_context: Optional[str]                          # Screen capture analysis
    action_plan: Optional[str]                             # Planned actions
    user_id: str                                          # User identifier
    metadata_terms: List[str]                             # Available memory categories
    relevant_memories: List[Dict[str, Any]]               # Retrieved memories
```

### Five Core Nodes

The agent implements five sequential nodes:

#### 1. **perceive_environment**
- **Purpose**: Capture and analyze visual context from the screen
- **Input**: GraphState with user message
- **Process**:
  - Captures primary screen using `ScreenCaptureService`
  - Analyzes screen with VLM (Vision-Language Model)
  - Generates screen description
- **Output**: Updates `visual_context` and `user_id`
- **Optional**: Only runs if `capture_screen=True` in config

#### 2. **query_memory**
- **Purpose**: Retrieve relevant memories from mem0
- **Input**: GraphState with messages and optional visual_context
- **Process**:
  - Extracts latest user message as query
  - Appends visual context to query if available
  - Searches mem0 for relevant memories (limit 5)
  - Retrieves all metadata categories
- **Output**: Updates `relevant_memories` and `metadata_terms`

#### 3. **reason_and_plan**
- **Purpose**: Analyze context and create action plan
- **Input**: GraphState with all previous context
- **Process**:
  - Builds comprehensive context from:
    - Visual context (screen analysis)
    - Relevant memories
    - User query
  - Uses LLM to generate action plan (2-3 sentences)
- **Output**: Updates `action_plan`

#### 4. **generate_response**
- **Purpose**: Generate final response to user
- **Input**: GraphState with complete context
- **Process**:
  - Builds system message with:
    - Agent persona (Natsume, desktop assistant)
    - Available memory categories
    - Action plan
    - Relevant memories
    - Visual context
  - Trims message history for context window
  - Generates response using LLM
- **Output**: Appends `AIMessage` to messages

#### 5. **update_memory**
- **Purpose**: Store important information in memory
- **Input**: GraphState with conversation history
- **Process**:
  - Analyzes recent conversation (last 4 messages)
  - Uses LLM to extract important facts
  - Identifies appropriate categories
  - Stores facts using `AddMemoryTool`
- **Output**: No state changes (side effects only)

## Workflow

The nodes are connected in a linear workflow:

```
START → perceive_environment → query_memory → reason_and_plan →
generate_response → update_memory → END
```

### State Flow Example

```python
# Initial State
{
    "messages": [HumanMessage(content="What's on my screen?")],
}

# After perceive_environment
{
    "messages": [...],
    "visual_context": "Screen shows VS Code with Python file",
    "user_id": "demo-user"
}

# After query_memory
{
    ...,
    "relevant_memories": [
        {"memory": "User is learning Python", "category": "work_context"}
    ],
    "metadata_terms": ["preferences", "work_context", "personal"]
}

# After reason_and_plan
{
    ...,
    "action_plan": "Analyze the screen context and help with Python code"
}

# After generate_response
{
    ...,
    "messages": [
        HumanMessage(content="What's on my screen?"),
        AIMessage(content="I can see VS Code with a Python file. How can I help?")
    ]
}

# After update_memory
# (New memory stored: "User is working on Python code")
```

## Usage

### Basic Usage

```python
from src.services.agent_service.graph import create_agent_graph
from src.services.agent_service.llm_factory import LLMFactory
from mem0 import Memory
from langchain_core.messages import HumanMessage

# Initialize services
llm = LLMFactory.get_llm_service("openai", ...)
mem0_client = Memory.from_config(MEM0_CONFIG)
vocabulary_manager = PostgreSQLVocabularyManager(...)

# Create graph
graph = create_agent_graph(
    llm=llm,
    mem0_client=mem0_client,
    vocabulary_manager=vocabulary_manager,
)

# Execute
result = await graph.ainvoke(
    {"messages": [HumanMessage(content="Hello")]},
    config={
        "configurable": {
            "user_id": "user-123",
            "agent_id": "desktop-assistant",
            "thread_id": "conversation-1",
            "capture_screen": False,
        }
    }
)
```

### With Screen Capture

```python
# Initialize additional services
vlm_service = VLMFactory.get_vlm_service("openai", ...)
screen_capture_service = ScreenCaptureService()

# Create graph with vision
graph = create_agent_graph(
    llm=llm,
    mem0_client=mem0_client,
    vocabulary_manager=vocabulary_manager,
    vlm_service=vlm_service,
    screen_capture_service=screen_capture_service,
)

# Execute with screen capture
result = await graph.ainvoke(
    {"messages": [HumanMessage(content="What's on my screen?")]},
    config={
        "configurable": {
            "user_id": "user-123",
            "capture_screen": True,  # Enable screen capture
        }
    }
)
```

## Configuration

### Required Configuration

```python
config = {
    "configurable": {
        "user_id": str,        # Required: User identifier
        "agent_id": str,       # Optional: Default "default-agent"
        "thread_id": str,      # Optional: For conversation continuity
        "capture_screen": bool # Optional: Default False
    }
}
```

### Environment Variables

Required for full functionality:

```bash
# LLM Configuration
LLM_API_KEY=your_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4

# VLM Configuration (for screen analysis)
VLM_API_KEY=your_key
VLM_BASE_URL=https://api.openai.com/v1
VLM_MODEL_NAME=gpt-4-vision-preview

# Memory Configuration (mem0)
EMB_API_KEY=your_key
EMB_BASE_URL=https://api.openai.com/v1
EMB_MODEL_NAME=text-embedding-3-large

# Vector Store (Qdrant)
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=desktop_mate_memories

# Graph Store (Neo4j)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Vocabulary DB (PostgreSQL)
VOCABULARY_DB_HOST=localhost
VOCABULARY_DB_NAME=memory_system_dev
VOCABULARY_DB_USER=memory_system
VOCABULARY_DB_PASSWORD=password
VOCABULARY_DB_PORT=5432
```

## Features

### 1. Conversation Continuity
- Uses `thread_id` to maintain conversation state
- Checkpointer persists state across invocations
- Message history is automatically managed

### 2. Memory Management
- Automatic memory extraction from conversations
- Categorized storage with metadata
- Semantic search for relevant context

### 3. Visual Context (Optional)
- Screen capture integration
- VLM-based screen analysis
- Visual context incorporated into reasoning

### 4. Intelligent Reasoning
- Context-aware action planning
- Multi-source information synthesis
- Persona-based responses

### 5. Error Handling
- Graceful degradation if services unavailable
- Detailed logging for debugging
- Fallback responses on errors

## Testing

### Run All Tests

```bash
# Run all agent tests
uv run pytest tests/test_agent_nodes.py tests/test_agent_graph.py -v

# Run with coverage
uv run pytest tests/test_agent_nodes.py tests/test_agent_graph.py --cov=src/services/agent_service -v
```

### Test Coverage

- **Node Tests** (`test_agent_nodes.py`): 13 tests
  - Test each node individually
  - Mock all external dependencies
  - Validate state transitions
  - Test error handling

- **Graph Tests** (`test_agent_graph.py`): 10 tests
  - Test graph construction
  - Validate node connections
  - Test execution flow
  - Test state persistence

## Demo

Run the comprehensive demo:

```bash
uv run python examples/agent_graph_demo.py
```

The demo includes three scenarios:
1. Simple conversation without screen capture
2. Continuing conversation (memory retrieval)
3. Screen analysis with VLM (if configured)

## Files Structure

```
src/services/agent_service/
├── __init__.py
├── state.py              # GraphState and Configuration
├── agent_nodes.py        # Five core node implementations
├── graph.py              # Graph builder and factory
├── llm_factory.py        # LLM service factory
├── message_util.py       # Message trimming utility
├── nodes.py              # Legacy memory agent (kept for compatibility)
└── tools/
    └── memory/           # Memory management tools

tests/
├── test_agent_nodes.py   # Unit tests for nodes
└── test_agent_graph.py   # Integration tests for graph

examples/
└── agent_graph_demo.py   # Comprehensive demo script
```

## Performance Considerations

1. **Message Trimming**: Conversation history is trimmed to maintain context window
2. **Memory Limit**: Max 5 memories retrieved per query
3. **Async Execution**: All nodes are async for efficient I/O
4. **Optional Services**: Screen capture and VLM are optional

## Limitations

1. **Linear Workflow**: Nodes execute sequentially (no conditional branching)
2. **Single Screen**: Only captures primary monitor
3. **Memory Extraction**: Relies on LLM to identify important facts
4. **No Streaming**: Responses are generated completely before returning

## Future Enhancements

1. **Conditional Routing**: Add logic to skip nodes based on context
2. **Multi-screen Support**: Capture and analyze multiple monitors
3. **Streaming Support**: Stream response generation
4. **Tool Integration**: Add more tools beyond memory management
5. **Human-in-the-Loop**: Add approval steps for critical actions

## Troubleshooting

### Issue: Screen capture fails
- Ensure display is available (won't work in headless environments)
- Check that `capture_screen=True` in config
- Verify VLM service is initialized

### Issue: Memory operations fail
- Check database connections (Qdrant, Neo4j, PostgreSQL)
- Verify environment variables are set
- Check mem0 configuration

### Issue: LLM errors
- Verify API keys and base URLs
- Check rate limits
- Ensure model names are correct

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [mem0 Documentation](https://docs.mem0.ai/)
- [Task 10 Requirements](../../.taskmaster/tasks/tasks.json)
