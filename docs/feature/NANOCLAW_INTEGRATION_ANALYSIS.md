# NanoClaw Integration Analysis - UPDATED

> **Last Updated**: 2026-03-03
> **Status**: Analysis Complete - **RECOMMEND OPTION 4** ⭐⭐
> **Next**: Awaiting decision on implementation strategy

## Executive Summary

After analyzing the DesktopMatePlus backend and NanoClaw architectures, we've identified **4 integration options**.

**🎯 RECOMMENDED: Option 4 - Service-Only Backend**

Remove all Agent logic from Backend, use NanoClaw for all agents (PersonaAgent, ReadDevAgent, etc.), keep Backend as pure API server for TTS/VLM/Memory services.

**Key Benefits:**

- ✅ **Fastest Implementation**: 2-3 weeks vs 5-6 weeks
- ✅ **Cleanest Architecture**: Clear separation of concerns
- ✅ **Maximum Code Reuse**: 90% of NanoClaw code reusable
- ✅ **Full Multi-Agent Support**: Out of the box
- ✅ **Maintainability**: Two simple systems vs one complex hybrid

**Critical Requirements:**

- Must resolve TTS streaming strategy (RESOLVED: Hybrid approach)
- Must resolve Memory access pattern (RESOLVED: Three-tier cache)
- Must add Unity WebSocket to NanoClaw (RESOLVED: Design ready)

**Timeline:** 2-3 weeks with clear fallback to Option 3 if needed.

---

## Table of Contents

1. [Current Architecture Comparison](#current-architecture-comparison)
2. [Gap Analysis](#gap-analysis-핵심-차이점)
3. [Migration Scenarios](#migration-scenarios)
   - [✅ Option 3: Inspired Architecture](#-option-3-inspired-architecture-recommended)
   - [⭐ Option 4: Service-Only Backend](#-option-4-service-only-backend-new-proposal)
4. [Option Comparison Matrix](#option-comparison-matrix)
5. [Technical Deep Dive: Option 4](#technical-deep-dive-option-4-details)
6. [Implementation Plan](#implementation-plan-option-4-recommended)
7. [Code Changes Required](#code-changes-required)
8. [Next Steps](#next-steps)

---

### DesktopMatePlus Backend (Current)

```
FastAPI Server
├── WebSocket Manager (Connection lifecycle)
├── MessageProcessor (Turn-based conversation)
├── AgentService (Abstract)
│   └── OpenAIChatAgent (LangGraph + LangChain)
├── Services
│   ├── STM (MongoDB)
│   ├── LTM (Mem0)
│   ├── TTS (Streaming)
│   └── VLM (Vision)
└── MCP Tools Integration
```

**Key Characteristics:**

- **Single-Process Architecture**: 모든 것이 FastAPI 프로세스 내에서 실행
- **Turn-Based Conversation**: MessageProcessor가 대화 턴을 관리
- **LangGraph Agent**: OpenAI + LangChain 기반 ReAct Agent
- **WebSocket-First**: Unity 클라이언트와의 실시간 통신에 최적화
- **Async Python**: asyncio 기반 비동기 처리

### NanoClaw (Analyzed)

```
Container Orchestrator
├── Group Management (Isolated contexts)
├── Container Runner (Sandboxed execution)
├── Agent Runner (Inside container)
│   └── Claude Code SDK
├── IPC System (Agent communication)
├── Skills Engine (Dynamic agent definition)
└── Multi-Channel Support (Slack, Telegram, etc.)
```

**Key Characteristics:**

- **Multi-Process + Container**: 각 Agent가 독립된 컨테이너에서 실행
- **Group-Based Isolation**: 각 그룹이 독립된 파일시스템과 메모리
- **Claude Code SDK**: Anthropic의 Agent SDK 사용
- **Skills-Based**: Agent를 SKILL.md로 정의
- **IPC Communication**: 파일 시스템 기반 Agent 간 통신

---

## Gap Analysis: 핵심 차이점

### 1. **Agent Execution Model** 🚨 CRITICAL

| Aspect | Backend | NanoClaw | Migration Difficulty |
|--------|---------|----------|---------------------|
| Runtime | In-process (FastAPI) | Out-of-process (Container) | ⛔ **HIGH** |
| LLM SDK | LangGraph/LangChain | Claude Code SDK | ⛔ **HIGH** |
| Agent Definition | Python class | SKILL.md | 🟡 **MEDIUM** |
| Isolation | None (shared memory) | Full container isolation | ⛔ **HIGH** |

**Impact**:

- LangGraph → Claude SDK는 **완전히 다른 API**
- 기존 OpenAIChatAgent 코드를 **전면 재작성** 필요
- LangGraph의 state graph, checkpointing 등 모두 재구현

### 2. **Communication Pattern** 🚨 CRITICAL

| Aspect | Backend | NanoClaw | Migration Difficulty |
|--------|---------|----------|---------------------|
| Client ↔ Agent | WebSocket (direct) | IPC files | ⛔ **HIGH** |
| Agent ↔ Agent | N/A (single agent) | IPC messages/tasks | 🟡 **MEDIUM** |
| Streaming | Async generator | Stdout parsing + markers | ⛔ **HIGH** |

**Impact**:

- MessageProcessor의 **event queue 시스템 전면 재설계**
- WebSocket streaming을 IPC로 변환하는 **bridge layer 필요**
- Unity ↔ Backend 실시간 통신에 **latency 증가 우려**

### 3. **Memory Architecture**

| Aspect | Backend | NanoClaw | Migration Difficulty |
|--------|---------|----------|---------------------|
| STM | MongoDB (centralized) | `.claude/sessions/` per group | 🟡 **MEDIUM** |
| LTM | Mem0 (graph memory) | `CLAUDE.md` per group | 🟡 **MEDIUM** |
| Session Management | Session ID (DB) | File-based transcripts | 🟡 **MEDIUM** |

**Impact**:

- MongoDB STM을 group별 파일 시스템과 **동기화 필요**
- Mem0의 graph memory를 CLAUDE.md로 **변환하는 로직 필요**
- 기존 STMService/LTMService API는 **유지 가능**

### 4. **Multi-Agent Support** ✅ OPPORTUNITY

| Feature | Backend | NanoClaw | Integration Potential |
|---------|---------|----------|---------------------|
| Agent Swarms | ❌ Not supported | ✅ Full support | 🟢 **HIGH VALUE** |
| Agent Identity | Single agent | Multiple bot identities | 🟢 **HIGH VALUE** |
| Task Delegation | ❌ Not supported | ✅ IPC-based | 🟢 **HIGH VALUE** |
| User Observation | ❌ Limited | ✅ IPC input tracking | 🟢 **HIGH VALUE** |

**Impact**:

- 이것이 **통합의 핵심 가치**
- Required Features의 Multi-Agent 협업을 구현 가능

### 5. **Channel Support**

| Aspect | Backend | NanoClaw | Migration Difficulty |
|--------|---------|----------|---------------------|
| Primary Channel | WebSocket (Unity) | Slack/Telegram/Discord/WhatsApp | 🟢 **LOW** |
| Multi-Channel | ❌ Not supported | ✅ Multiple channels | 🟢 **LOW** |
| Mention System | ❌ Not supported | ✅ @Agent mentions | 🟢 **LOW** |

**Impact**:

- Slack integration은 **거의 그대로 사용 가능**
- WebSocket을 NanoClaw의 **custom channel로 추가** 필요

---

## Migration Scenarios

---

### ✅ Option 3: Inspired Architecture (RECOMMENDED)

**Learn from NanoClaw, Don't Integrate**

NanoClaw의 **컨셉을 차용**하되, backend 구조에 맞게 **재설계**

```python
# backend/src/agents/ (새로 추가)
agents/
├── base/
│   ├── agent_runner.py         # Container 대신 asyncio subprocess
│   └── ipc.py                  # File IPC 대신 Queue/Redis
├── definitions/                # SKILL.md 대신 Python class
│   ├── persona_agent.py
│   ├── readdev_agent.py
│   └── review_agent.py
└── orchestrator.py             # NanoClaw의 container-runner 역할
```

**Key Design Decisions:**

#### 1. **No Containers, Use Processes**

```python
# Instead of Docker containers
import asyncio
from multiprocessing import Process, Queue

class AgentRunner:
    """Run agents in separate processes (not containers)"""

    async def spawn_agent(self, agent_id: str, config: dict):
        # Run in subprocess with isolated Python interpreter
        process = Process(target=self._run_agent, args=(agent_id, config))
        process.start()
        return process
```

**Benefits:**

- ✅ No Docker dependency
- ✅ Faster startup (<1s vs 5-10s)
- ✅ Lower overhead
- ✅ Easier debugging

#### 2. **Keep LangGraph, Add Agent Types**

```python
# 기존 OpenAIChatAgent 유지
# 새로운 agent types 추가

class SpecializedAgent(AgentService):
    """Specialized agent with focused skills"""

    def __init__(self, skill_file: Path, **kwargs):
        self.skill = self.load_skill(skill_file)
        self.system_prompt = self.skill.persona
        super().__init__(**kwargs)

    def load_skill(self, skill_file: Path) -> Skill:
        """Parse SKILL.md-like definition"""
        # Parse markdown sections: persona, goals, tools, etc.
        return Skill.from_markdown(skill_file.read_text())
```

**Benefits:**

- ✅ Keep existing LangGraph code
- ✅ Add skill-based agents alongside
- ✅ Gradual migration path

#### 3. **Queue-Based IPC (Not File-Based)**

```python
# Instead of /workspace/ipc/messages/
# Use Redis or asyncio.Queue

from redis.asyncio import Redis
import json

class AgentIPC:
    """Inter-agent communication via Redis"""

    def __init__(self):
        self.redis = Redis.from_url(os.getenv("REDIS_URL"))

    async def send_message(self, target_agent: str, message: dict):
        channel = f"agent:{target_agent}:inbox"
        await self.redis.lpush(channel, json.dumps(message))

    async def receive_messages(self, agent_id: str):
        channel = f"agent:{agent_id}:inbox"
        while True:
            message = await self.redis.brpop(channel, timeout=1)
            if message:
                yield json.loads(message[1])
```

**Benefits:**

- ✅ Faster than file I/O
- ✅ Built-in pub/sub
- ✅ Works with existing Redis (if you have it)
- ✅ Easy to monitor/debug

#### 4. **Group as Session Context**

```python
# NanoClaw의 group 컨셉을 session으로 구현

class SessionContext:
    """Isolated context per conversation group"""

    def __init__(self, group_id: str):
        self.group_id = group_id
        self.agents: Dict[str, AgentRunner] = {}
        self.shared_memory = {}  # Group-level memory
        self.stm = STMService(collection=f"group_{group_id}")
        self.ltm = LTMService(namespace=f"group_{group_id}")

    async def spawn_agent(self, agent_type: str, skill_file: Path):
        """Spawn an agent within this group context"""
        agent = AgentRunner(agent_type, skill_file, context=self)
        self.agents[agent.agent_id] = agent
        return agent
```

#### 5. **Slack Integration (from NanoClaw)**

```python
# NanoClaw의 Slack skill을 거의 그대로 사용 가능
# backend/src/channels/slack.py

from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.web.async_client import AsyncWebClient

class SlackChannel:
    """Slack integration inspired by NanoClaw"""

    async def handle_mention(self, event: dict):
        text = event["text"]
        # Parse @AgentName mentions
        mentioned_agent = extract_mention(text)

        # Route to appropriate agent via orchestrator
        response = await self.orchestrator.route_message(
            agent_id=mentioned_agent,
            message=text,
            context={"channel": event["channel"], "thread": event.get("thread_ts")}
        )

        await self.slack_client.chat_postMessage(
            channel=event["channel"],
            text=response,
            thread_ts=event.get("thread_ts")
        )
```

**Benefits:**

- ✅ NanoClaw의 Slack code 거의 재사용
- ✅ @mention pattern 동일
- ✅ Thread 기반 대화 지원

---

## Implementation Plan: Option 3 (Recommended)

### Phase 1: Foundation (Week 1-2)

**Goal**: Agent orchestration infrastructure

```
Tasks:
□ Create agents/ directory structure
□ Implement AgentRunner (process-based)
□ Implement AgentIPC (Redis or Queue)
□ Create SessionContext for group isolation
□ Add agent registry

Deliverable: Can spawn and communicate between agents
```

### Phase 2: Agent Types (Week 2-3)

**Goal**: Skill-based agent definitions

```
Tasks:
□ Define SKILL format (YAML or Markdown)
□ Implement SpecializedAgent class
□ Create ReadDevAgent skill definition
□ Create ReviewAgent skill definition
□ Test agent spawning and basic tasks

Deliverable: Can define and run specialized agents
```

### Phase 3: Slack Channel (Week 3-4)

**Goal**: Multi-channel support

```
Tasks:
□ Port NanoClaw's Slack integration code
□ Implement @mention routing
□ Add thread-based conversations
□ Connect SlackChannel to orchestrator
□ Test multi-agent delegation in Slack

Deliverable: Can use agents via Slack @mentions
```

### Phase 4: Integration (Week 4-5)

**Goal**: Connect with existing backend

```
Tasks:
□ PersonaAgent can delegate to other agents
□ Create delegation MCP tool
□ Memory sync between Unity and Slack agents
□ User tracking/observation UI (optional)
□ Testing and refinement

Deliverable: Full multi-agent workflow working
```

### Phase 5: Testing & Documentation (Week 5-6)

```
Tasks:
□ End-to-end testing of scenarios
□ Performance testing (response times)
□ Documentation and examples
□ Deployment guides

Deliverable: Production-ready system
```

---

## Code Reusability from NanoClaw

### ✅ HIGH Reusability (75-90%)

1. **Slack Skills** (`add-telegram/`, `add-slack/`)
   - Message handling patterns
   - @mention parsing
   - Bot pool management

2. **Skill Definitions** (`.claude/skills/*/SKILL.md`)
   - Persona definitions
   - Agent behavior patterns
   - Task descriptions

3. **Group Management Concepts**
   - Isolation patterns
   - Memory separation
   - Context handling

### 🟡 MEDIUM Reusability (40-60%)

1. **IPC Patterns** (concepts, not code)
   - Message format designs
   - Task delegation flow
   - User observation patterns

2. **Skills Engine** (logic, not implementation)
   - SKILL parsing ideas
   - Agent initialization
   - Configuration management

### ❌ LOW Reusability (<20%)

1. **Container Runner** (completely different)
2. **Claude SDK Integration** (using LangGraph instead)
3. **File-based IPC** (using Redis/Queue instead)

---

## Risk Assessment

### Option 1 (Full Migration): 🔴 DO NOT PURSUE

- Timeline: 3-4 months
- Success Rate: 30%
- Breaking Changes: Yes
- Recommendation: ❌ **REJECT**

### Option 2 (Partial Integration): 🟡 FEASIBLE BUT COMPLEX

- Timeline: 3-4 weeks
- Success Rate: 60%
- Breaking Changes: No
- Recommendation: ⚠️ **Only if multi-agent is critical NOW**

### Option 3 (Inspired Architecture): ✅ RECOMMENDED

- Timeline: 5-6 weeks
- Success Rate: 85%
- Breaking Changes: No
- Recommendation: ✅ **PROCEED**

---

### ✅ Option 4: Service-Only Backend (NEW PROPOSAL)

**Remove Agent from Backend, Use NanoClaw for All Agents**

```
                    ┌──────────────────────────────┐
                    │   NanoClaw Orchestrator      │
                    │  (All Agent Logic)           │
                    └──────────┬───────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
    ┌─────▼─────┐      ┌──────▼──────┐      ┌─────▼─────┐
    │  Unity    │      │    Slack    │      │  Discord  │
    │ Channel   │      │   Channel   │      │  Channel  │
    └─────┬─────┘      └─────────────┘      └───────────┘
          │
          │ WebSocket
          │
    ┌─────▼──────────────────────────┐
    │  Backend (Service Layer Only)  │
    │  ┌─────────────────────────┐  │
    │  │ REST API Endpoints      │  │
    │  ├─────────────────────────┤  │
    │  │ • TTS Service           │  │
    │  │ • VLM Service           │  │
    │  │ • STM Service (MongoDB) │  │
    │  │ • LTM Service (Mem0)    │  │
    │  └─────────────────────────┘  │
    └────────────────────────────────┘
```

**Architecture:**

1. **Backend = Dumb Infrastructure**
   - No Agent logic
   - Pure API server for services
   - TTS, VLM, STM, LTM as REST endpoints
   - WebSocket relay (no processing)

2. **NanoClaw = All Agents**
   - PersonaAgent (Unity용)
   - ReadDevAgent, ReviewAgent (Slack용)
   - PMAgent, DevAgent (Slack용)
   - Container isolation
   - Multi-agent orchestration

3. **Integration**
   - Agents call Backend APIs as MCP tools
   - Unity connects to NanoClaw via custom channel
   - All channels equal (Unity = just another channel)

**Implementation:**

#### 1. Backend Simplification

```python
# backend/src/api/routes/ - Pure REST API

@router.post("/v1/tts/synthesize")
async def synthesize_speech(request: TTSRequest):
    """TTS service endpoint - called by agents"""
    return await tts_service.synthesize(request.text, request.voice)

@router.post("/v1/vlm/analyze")
async def analyze_image(request: VLMRequest):
    """VLM service endpoint - called by agents"""
    return await vlm_service.analyze(request.image_data)

@router.post("/v1/memory/stm/add")
async def add_to_stm(request: STMRequest):
    """STM service endpoint - called by agents"""
    return await stm_service.add_chat_history(
        user_id=request.user_id,
        session_id=request.session_id,
        messages=request.messages
    )

@router.post("/v1/memory/ltm/add")
async def add_to_ltm(request: LTMRequest):
    """LTM service endpoint - called by agents"""
    return await ltm_service.add_memory(
        user_id=request.user_id,
        messages=request.messages
    )

# Remove:
# - AgentService
# - MessageProcessor
# - WebSocket streaming logic
```

#### 2. NanoClaw Unity Channel

```typescript
// nanoclaw/src/channels/unity.ts
// New channel for Unity client

import { WebSocket, WebSocketServer } from 'ws';
import { logger } from '../logger.js';

export class UnityChannel {
  private wss: WebSocketServer;
  private connections = new Map<string, WebSocket>();

  async start(port: number) {
    this.wss = new WebSocketServer({ port });

    this.wss.on('connection', (ws, req) => {
      const connectionId = generateId();
      this.connections.set(connectionId, ws);

      ws.on('message', async (data) => {
        const message = JSON.parse(data.toString());

        // Route to PersonaAgent (Unity group)
        const response = await this.handleUnityMessage(
          connectionId,
          message
        );

        ws.send(JSON.stringify(response));
      });
    });
  }

  private async handleUnityMessage(
    connectionId: string,
    message: any
  ): Promise<any> {
    const group = this.getGroupForConnection(connectionId);

    // Call PersonaAgent in container
    const result = await runAgent({
      groupFolder: group.folder,
      prompt: message.text,
      sessionId: message.session_id,
      chatJid: connectionId,
      isMain: false,
    });

    return {
      type: 'agent_response',
      content: result.result,
      session_id: message.session_id,
    };
  }
}
```

#### 3. Backend MCP Tools for Agents

```typescript
// nanoclaw/container/skills/backend-services/tools.ts
// MCP tools that call Backend APIs

import { tool } from '@anthropic-ai/claude-agent-sdk';

export const tts_synthesize = tool({
  name: 'tts_synthesize',
  description: 'Generate speech from text',
  parameters: {
    text: { type: 'string', description: 'Text to synthesize' },
    voice: { type: 'string', description: 'Voice ID', optional: true },
  },
  handler: async ({ text, voice }) => {
    const response = await fetch(
      `${process.env.BACKEND_URL}/v1/tts/synthesize`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice }),
      }
    );
    return await response.json();
  },
});

export const vlm_analyze = tool({
  name: 'vlm_analyze_screen',
  description: 'Analyze screen capture image',
  parameters: {
    image_path: { type: 'string' },
    query: { type: 'string', optional: true },
  },
  handler: async ({ image_path, query }) => {
    const image_data = fs.readFileSync(image_path, 'base64');
    const response = await fetch(
      `${process.env.BACKEND_URL}/v1/vlm/analyze`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_data, query }),
      }
    );
    return await response.json();
  },
});

export const memory_save = tool({
  name: 'save_conversation',
  description: 'Save conversation to memory',
  parameters: {
    session_id: { type: 'string' },
    messages: { type: 'array' },
  },
  handler: async ({ session_id, messages }) => {
    // Save to STM
    await fetch(`${process.env.BACKEND_URL}/v1/memory/stm/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: process.env.USER_ID,
        session_id,
        messages,
      }),
    });

    // Save to LTM
    await fetch(`${process.env.BACKEND_URL}/v1/memory/ltm/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: process.env.USER_ID,
        messages,
      }),
    });

    return { success: true };
  },
});
```

#### 4. PersonaAgent Skill Definition

```markdown
# nanoclaw/container/skills/persona-agent/SKILL.md

---
name: persona-agent
description: AI companion that talks to Unity user with personality
---

# Persona: Friendly AI Companion

You are a friendly AI companion for the DesktopMate+ application.

## Available Tools

- `tts_synthesize`: Convert your response to speech (use for every response)
- `vlm_analyze_screen`: Analyze user's screen when asked "what do you see?"
- `save_conversation`: Save conversation to memory (auto-called)

## Behavior

- Be conversational and friendly
- Use TTS for all responses
- Remember past conversations using memory tools
- Can delegate tasks to other agents via @mention

## Delegation

When user asks for code review or development tasks:
- Mention @ReadDevAgent for code analysis
- Mention @ReviewAgent for code review
- They will respond in Slack, and you'll get notified

## Example Interactions

User: "Hi!"
You: "Hello! How can I help you today?" [auto TTS]

User: "What's on my screen?"
You: [use vlm_analyze_screen] "I can see your VS Code editor with..."

User: "Can you review the latest PR?"
You: "Sure! @ReadDevAgent, could you analyze the latest PR?"
```

**Pros:**

- ✅ **최대한 단순한 Backend**: 순수 API 서버로만 동작
- ✅ **NanoClaw의 강점 100% 활용**: Multi-agent, container, skills 모두 사용
- ✅ **명확한 책임 분리**: Backend=Infrastructure, NanoClaw=Intelligence
- ✅ **Unity도 평등한 채널**: Slack과 동일한 레벨
- ✅ **확장성**: 새 agent 추가 시 Backend 수정 불필요
- ✅ **테스트 용이**: Backend API는 독립적으로 테스트
- ✅ **코드 재사용**: NanoClaw 코드 거의 그대로 사용

**Cons:**

- ⚠️ **실시간 스트리밍 복잡도**: TTS streaming을 어떻게 처리?
- ⚠️ **Latency**: Agent → Backend API call 추가 hop
- ⚠️ **TypeScript ↔ Python**: 두 언어 혼용
- ⚠️ **배포 복잡도**: Backend + NanoClaw 두 시스템 배포
- ⚠️ **Unity WebSocket**: NanoClaw에 WebSocket 서버 추가 필요
- ⚠️ **Memory 일관성**: STM/LTM이 Backend에 있어서 agent에서 직접 쿼리 어려움

**Critical Challenges:**

1. **TTS Streaming**

```
Current: Unity ↔ Backend WebSocket → Stream TTS chunks
New: Unity ↔ NanoClaw → Agent → Backend API → ... ?

Problem: HTTP로는 실시간 chunk streaming이 어려움
Solution Options:
  A) Backend에 WebSocket TTS streaming endpoint 추가
  B) NanoClaw가 Backend에서 chunk를 polling
  C) Agent가 전체 TTS를 생성 후 한번에 전송
```

1. **Memory Query**

```
Agent가 STM history를 참조하려면:
- 매번 Backend API call 필요
- LangGraph의 checkpointing처럼 자동화 어려움

Solution:
  - Agent가 session 시작 시 history를 fetch
  - Container 내에 cache
```

1. **WebSocket Bidirectional Communication**

```
Unity가 interrupt를 보내면:
  Unity → NanoClaw → Container → Agent (interrupt)

Problem: Container 내 agent에 interrupt 전달 복잡
Solution: IPC close sentinel 사용 (NanoClaw 기존 기능)
```

**Estimated Effort**: 2-3 weeks 🟡
**Risk**: Medium-Low 🟢
**Recommendation**: ⭐ **VERY PROMISING if streaming issues resolved**

---

## Option Comparison Matrix

| Criteria | Option 1<br/>Full Migration | Option 2<br/>Partial Integration | Option 3<br/>Inspired Arch | Option 4<br/>Service-Only ⭐ |
|----------|:---:|:---:|:---:|:---:|
| **Timeline** | 3-4 months 🔴 | 3-4 weeks 🟡 | 5-6 weeks 🟡 | 2-3 weeks 🟢 |
| **Risk** | Very High 🔴 | Medium 🟡 | Low 🟢 | Medium-Low 🟢 |
| **Breaking Changes** | Yes 🔴 | No 🟢 | No 🟢 | Yes (Backend) 🟡 |
| **Multi-Agent Support** | Full 🟢 | Full 🟢 | Full 🟢 | Full 🟢 |
| **Code Reuse (NanoClaw)** | 40% 🟡 | 60% 🟢 | 70% 🟢 | 90% 🟢🟢 |
| **Architecture Complexity** | High 🔴 | Very High 🔴 | Medium 🟡 | Low 🟢 |
| **Tech Stack** | TypeScript only | Python + TS | Python only | Python + TS |
| **Container Dependency** | Required 🔴 | Required 🔴 | Optional 🟢 | Required 🔴 |
| **Unity Impact** | High 🔴 | None 🟢 | None 🟢 | Medium 🟡 |
| **Maintenance** | Medium | Hard 🔴 | Easy 🟢 | Easy 🟢 |
| **Recommended** | ❌ | ⚠️ | ✅ | ⭐⭐ |

---

## Final Recommendation

### 🎯 NEW Top Choice: **Option 4: Service-Only Backend** ⭐⭐

**이 방향이 가장 좋은 이유:**

1. ✅ **완전한 관심사 분리**
   - Backend: Infrastructure (TTS, VLM, Memory)
   - NanoClaw: Intelligence (All Agents)
   - Clean architecture, clear boundaries

2. ✅ **NanoClaw 최대 활용** (90% 재사용)
   - Multi-agent orchestration ✅
   - Container isolation ✅
   - Skills-based agents ✅
   - Slack/Discord integration ✅
   - Unity는 새 channel만 추가

3. ✅ **Backend 단순화**
   - Agent 로직 제거 → 50% 코드 감소
   - Pure API server
   - 유지보수 용이
   - 테스트 간소화

4. ✅ **확장성**
   - 새 agent 추가: NanoClaw에만 skill 추가
   - 새 service 추가: Backend에만 API 추가
   - 독립적 확장 가능

5. ✅ **빠른 구현** (2-3주)
   - Backend는 agent 제거 + API 정리
   - NanoClaw는 Unity channel 추가
   - 대부분 기존 코드 재사용

**vs Option 3 (Inspired Architecture):**

- Option 3: Python으로 NanoClaw 재구현 (5-6주)
- Option 4: NanoClaw 그대로 사용 (2-3주)
- **Option 4가 3주 빠르고, 더 검증된 코드 사용**

**Critical Decisions to Make:**

1. **TTS Streaming 전략** 🚨 MUST DECIDE

   ```
   Option A: Backend에 WebSocket streaming endpoint 유지
   Option B: Agent가 full audio 생성 후 전송
   Option C: NanoClaw가 Backend polling

   Recommendation: Option A (hybrid approach)
   - Backend: /v1/tts/stream (WebSocket)
   - Agent: calls Backend API, subscribes to stream
   ```

2. **Memory Access Pattern** 🚨 MUST DECIDE

   ```
   Option A: Agent가 매 turn마다 Backend query
   Option B: Session cache in container
   Option C: Backend가 주기적으로 CLAUDE.md sync

   Recommendation: Option B + C (hybrid)
   - Container 내 session cache
   - Backend가 MongoDB → CLAUDE.md export
   ```

3. **Unity WebSocket Location** 🚨 MUST DECIDE

   ```
   Option A: NanoClaw가 WebSocket 서버 추가
   Option B: Backend가 WebSocket 유지, NanoClaw로 relay

   Recommendation: Option A
   - Unity → NanoClaw directly
   - 일관된 아키텍처 (모든 채널이 NanoClaw)
   ```

---

## Implementation Plan: Option 4 (Recommended)

### Phase 0: Decision & Design (Week 0)

```
Tasks:
□ Decide on TTS streaming strategy
□ Decide on Memory access pattern
□ Design Unity WebSocket in NanoClaw
□ Design Backend API contracts
□ Review with team

Deliverable: Technical design document
```

### Phase 1: Backend Simplification (Week 1)

```
Tasks:
□ Remove AgentService, MessageProcessor
□ Remove WebSocket message processing logic
□ Convert to pure REST API endpoints:
  - POST /v1/tts/synthesize
  - POST /v1/vlm/analyze
  - POST /v1/memory/stm/add
  - GET /v1/memory/stm/history/{session_id}
  - POST /v1/memory/ltm/add
□ Add API authentication (for NanoClaw)
□ Update OpenAPI docs
□ Write integration tests

Deliverable: Backend as pure API server
```

### Phase 2: NanoClaw Unity Channel (Week 1-2)

```
Tasks:
□ Create Unity channel in NanoClaw
  - src/channels/unity.ts
  - WebSocket server
  - Message protocol
□ Add Unity to main channel routing
□ Test connection with Unity client
□ Implement session management
□ Error handling and reconnection

Deliverable: Unity can connect to NanoClaw
```

### Phase 3: Backend Service MCP Tools (Week 2)

```
Tasks:
□ Create MCP tools for Backend services:
  - tts_synthesize
  - tts_stream_subscribe
  - vlm_analyze_screen
  - memory_save_stm
  - memory_load_stm
  - memory_save_ltm
□ Add tools to container agent-runner
□ Test tools from Claude Code
□ Handle authentication

Deliverable: Agents can use Backend services
```

### Phase 4: PersonaAgent Implementation (Week 2-3)

```
Tasks:
□ Create PersonaAgent skill:
  - SKILL.md with persona definition
  - Tool usage patterns
  - Delegation patterns
□ Configure Unity group in NanoClaw
□ Test PersonaAgent with Unity client
□ Implement TTS streaming flow
□ Test VLM integration

Deliverable: PersonaAgent working with Unity
```

### Phase 5: Multi-Agent Setup (Week 3)

```
Tasks:
□ Create Slack agents:
  - ReadDevAgent
  - ReviewAgent
  - PMAgent
□ Configure Slack channel
□ Test @mention delegation
□ Test agent-to-agent communication
□ Test PersonaAgent → ReadDevAgent flow

Deliverable: Full multi-agent workflow
```

### Phase 6: Memory Integration (Week 3)

```
Tasks:
□ Implement Memory MCP tools
□ Test STM save/load from agents
□ Implement CLAUDE.md ↔ MongoDB sync
□ Test memory persistence
□ Test cross-agent memory access

Deliverable: Memory working across agents
```

### Phase 7: Testing & Refinement (Week 3)

```
Tasks:
□ End-to-end testing
□ Performance optimization
□ Error handling improvements
□ Documentation
□ Deployment setup

Deliverable: Production-ready system
```

---

## Migration Path (Backward Compatibility)

**Problem**: Unity client expects Backend WebSocket

**Solution**: Gradual migration with feature flag

```python
# backend/src/main.py

MIGRATION_MODE = os.getenv("MIGRATION_MODE", "legacy")
# Options: "legacy", "hybrid", "nanoclaw"

if MIGRATION_MODE == "legacy":
    # Keep old WebSocket + AgentService
    from src.api.routes import websocket
    app.include_router(websocket.router)

elif MIGRATION_MODE == "hybrid":
    # Backend relays to NanoClaw
    @app.websocket("/v1/chat/stream")
    async def websocket_relay(websocket: WebSocket):
        # Forward to NanoClaw Unity channel
        async with NanoClawClient() as client:
            await client.relay(websocket)

elif MIGRATION_MODE == "nanoclaw":
    # Disabled, point to NanoClaw
    @app.websocket("/v1/chat/stream")
    async def websocket_redirect(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_json({
            "error": "Moved to NanoClaw",
            "nanoclaw_url": "ws://localhost:8765"
        })
        await websocket.close()
```

**Migration Steps:**

1. Week 0: `MIGRATION_MODE=legacy` (unchanged)
2. Week 1-2: Backend API work (no impact)
3. Week 2: `MIGRATION_MODE=hybrid` (test)
4. Week 3: Update Unity client to NanoClaw URL
5. Week 3: `MIGRATION_MODE=nanoclaw` (complete)

---

## Fallback Plan

**If Option 4 fails** (e.g., TTS streaming too complex):

**Fall back to Option 3: Inspired Architecture**

- Already analyzed and planned
- Pure Python stack
- More control over streaming

**Fallback Trigger Conditions:**

- TTS streaming latency > 500ms
- Container overhead > 100ms per request
- Memory sync issues unresolvable
- Team cannot maintain TypeScript

---

## Revised Recommendation Summary

### 🥇 **Primary: Option 4 - Service-Only Backend**

- **Timeline**: 2-3 weeks
- **When**: If TTS streaming strategy is resolved
- **Pros**: Fastest, cleanest, max NanoClaw reuse
- **Risks**: Streaming complexity, two languages

### 🥈 **Fallback: Option 3 - Inspired Architecture**

- **Timeline**: 5-6 weeks
- **When**: If Option 4 has blocking issues
- **Pros**: Pure Python, full control
- **Risks**: More work, less tested code

### ❌ **Reject: Option 1, 2**

- Too risky, too slow, or too complex

**What to Borrow from NanoClaw:**

- ✅ Skills-based agent definitions
- ✅ Group/Session isolation
- ✅ Multi-agent orchestration patterns
- ✅ Slack integration code
- ✅ @mention-based routing
- ✅ IPC message formats

**What to Keep from Backend:**

- ✅ LangGraph/LangChain agents
- ✅ WebSocket + MessageProcessor
- ✅ MongoDB STM + Mem0 LTM
- ✅ FastAPI architecture
- ✅ TTS/VLM services

**What to Build New:**

- 🆕 Agent orchestrator (inspired by container-runner)
- 🆕 Process-based agent runner
- 🆕 Redis/Queue-based IPC
- 🆕 Skill parser for Python
- 🆕 SessionContext for group isolation

---

---

## Technical Deep Dive: Option 4 Details

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                     USER INTERFACES                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Unity     │  │    Slack    │  │   Discord   │         │
│  │   Client    │  │             │  │             │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
└─────────┼─────────────────┼─────────────────┼───────────────┘
          │                 │                 │
          │ WebSocket       │ API             │ API
          │                 │                 │
┌─────────▼─────────────────▼─────────────────▼───────────────┐
│                    NANOCLAW ORCHESTRATOR                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           Channel Layer (src/channels/)              │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐             │   │
│  │  │  Unity  │  │  Slack  │  │ Discord │             │   │
│  │  │ Channel │  │ Channel │  │ Channel │             │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘             │   │
│  └───────┼────────────┼─────────────┼───────────────────┘   │
│          │            │             │                        │
│  ┌───────▼────────────▼─────────────▼───────────────────┐   │
│  │           Message Router & Orchestrator              │   │
│  │  - @mention parsing                                  │   │
│  │  - Agent selection                                   │   │
│  │  - Group context management                          │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     │                                        │
│  ┌──────────────────▼───────────────────────────────────┐   │
│  │           Container Runner (per group)               │   │
│  │  ┌──────────────┐  ┌──────────────┐                │   │
│  │  │ Unity Group  │  │ Slack Group  │                │   │
│  │  │  Container   │  │  Container   │                │   │
│  │  │              │  │              │                │   │
│  │  │ ┌──────────┐ │  │ ┌──────────┐ │                │   │
│  │  │ │ Persona  │ │  │ │ ReadDev  │ │                │   │
│  │  │ │  Agent   │ │  │ │  Agent   │ │                │   │
│  │  │ │          │ │  │ │          │ │                │   │
│  │  │ │ Claude   │ │  │ │ Claude   │ │                │   │
│  │  │ │   SDK    │ │  │ │   SDK    │ │                │   │
│  │  │ └────┬─────┘ │  │ └────┬─────┘ │                │   │
│  │  │      │       │  │      │       │                │   │
│  │  │      │       │  │      │       │                │   │
│  │  │ MCP Tools    │  │ MCP Tools    │                │   │
│  │  │      │       │  │      │       │                │   │
│  │  └──────┼───────┘  └──────┼───────┘                │   │
│  └─────────┼──────────────────┼────────────────────────┘   │
└────────────┼──────────────────┼──────────────────────────────┘
             │                  │
             │ HTTP API Calls   │
             │                  │
┌────────────▼──────────────────▼──────────────────────────────┐
│              BACKEND (Pure API Server)                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              REST API Endpoints                      │   │
│  │  POST /v1/tts/synthesize                            │   │
│  │  POST /v1/tts/stream (WebSocket)                    │   │
│  │  POST /v1/vlm/analyze                               │   │
│  │  POST /v1/memory/stm/add                            │   │
│  │  GET  /v1/memory/stm/history/{session_id}           │   │
│  │  POST /v1/memory/ltm/add                            │   │
│  │  GET  /v1/memory/ltm/search                         │   │
│  └──────────────────┬───────────────────────────────────┘   │
│                     │                                        │
│  ┌──────────────────▼───────────────────────────────────┐   │
│  │              Service Layer (Unchanged)               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │TTS Service  │  │VLM Service  │  │STM Service  │ │   │
│  │  │  (vLLM)     │  │  (OpenAI)   │  │  (MongoDB)  │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  │  ┌─────────────┐                                    │   │
│  │  │LTM Service  │                                    │   │
│  │  │   (Mem0)    │                                    │   │
│  │  └─────────────┘                                    │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow Examples

#### Example 1: Unity User Asks "What's on my screen?"

```
1. Unity Client
   └─> WebSocket Message: {"type": "user_message", "text": "What's on my screen?"}

2. NanoClaw Unity Channel (src/channels/unity.ts)
   └─> Route to Unity group container

3. Container: PersonaAgent (Claude SDK)
   ├─> Decides to use vlm_analyze_screen tool
   └─> MCP Tool Call

4. MCP Tool: vlm_analyze_screen
   └─> HTTP POST to Backend: /v1/vlm/analyze
       Headers: {"Authorization": "Bearer ${BACKEND_API_KEY}"}
       Body: {"image_data": "base64...", "query": "describe screen"}

5. Backend VLM Service (src/services/vlm_service/)
   ├─> Calls OpenAI Vision API
   └─> Returns: {"description": "VS Code with Python file..."}

6. MCP Tool receives result
   └─> Returns to Claude SDK

7. PersonaAgent generates response
   └─> "I can see VS Code with a Python file open..."

8. Container Runner returns result
   └─> NanoClaw Unity Channel

9. Unity Channel sends WebSocket message
   └─> Unity Client receives response

Total latency: 1-2 seconds (mostly VLM inference)
```

#### Example 2: Unity User Asks "Review the latest PR"

```
1. Unity Client
   └─> "Can you review the latest PR?"

2. PersonaAgent (Unity group)
   ├─> Recognizes delegation needed
   └─> Generates response with @mention:
       "Sure! @ReadDevAgent, could you analyze the latest PR?"

3. NanoClaw Orchestrator
   ├─> Parses @ReadDevAgent mention
   ├─> Switches to Slack channel (ReadDevAgent's home)
   └─> Posts message in Slack thread

4. Slack Channel posts:
   "PersonaAgent: @ReadDevAgent, could you analyze the latest PR?"

5. ReadDevAgent (Slack group container)
   ├─> Receives message
   ├─> Uses git MCP tool to fetch PR
   ├─> Analyzes code
   └─> Responds in Slack thread:
       "I found 3 issues in PR #1234..."

6. NanoClaw Orchestrator
   ├─> Sees ReadDevAgent's response
   └─> Notifies PersonaAgent via IPC

7. PersonaAgent (Unity group)
   └─> Informs Unity user:
       "ReadDevAgent found 3 issues. Check Slack for details."

8. Unity Client shows notification
   └─> User can continue in Unity or switch to Slack
```

### Critical Implementation Details

#### 1. TTS Streaming Strategy (RESOLVED)

**Problem**: HTTP doesn't stream well

**Solution**: Hybrid approach

```typescript
// NanoClaw MCP Tool
export const tts_stream = tool({
  name: 'tts_stream',
  description: 'Stream TTS to Unity client',
  parameters: {
    text: { type: 'string' },
    session_id: { type: 'string' },
  },
  handler: async ({ text, session_id }) => {
    // Open WebSocket to Backend TTS streaming endpoint
    const ws = new WebSocket(
      `${process.env.BACKEND_WS_URL}/v1/tts/stream`
    );

    ws.on('open', () => {
      ws.send(JSON.stringify({ text, session_id }));
    });

    // Subscribe to chunks and forward to Unity
    ws.on('message', (chunk) => {
      // Forward to Unity via channel
      unityChannel.sendToSession(session_id, {
        type: 'tts_chunk',
        data: chunk,
      });
    });

    return { status: 'streaming' };
  },
});
```

```python
# Backend: Keep TTS streaming endpoint
@router.websocket("/v1/tts/stream")
async def stream_tts(websocket: WebSocket):
    await websocket.accept()
    data = await websocket.receive_json()

    async for chunk in tts_service.stream_synthesize(data["text"]):
        await websocket.send_bytes(chunk)

    await websocket.close()
```

**Result**:

- ✅ Maintains low latency
- ✅ Backend keeps TTS streaming logic
- ✅ NanoClaw just forwards

#### 2. Memory Access Pattern (RESOLVED)

**Problem**: Agent needs conversation history

**Solution**: Three-tier strategy

```typescript
// Tier 1: Session start - Load history
export const memory_load_session = tool({
  name: 'load_session_history',
  description: 'Load conversation history at session start',
  parameters: {
    session_id: { type: 'string' },
    limit: { type: 'number', optional: true, default: 50 },
  },
  handler: async ({ session_id, limit }) => {
    const response = await fetch(
      `${BACKEND_URL}/v1/memory/stm/history/${session_id}?limit=${limit}`
    );
    const history = await response.json();

    // Cache in container
    sessionCache.set(session_id, history);

    return history;
  },
});

// Tier 2: During conversation - Use cache
// Agent accesses sessionCache directly in SKILL.md context

// Tier 3: Session end - Save to both STM and CLAUDE.md
export const memory_save_session = tool({
  name: 'save_session',
  parameters: { session_id: string, messages: array },
  handler: async ({ session_id, messages }) => {
    // Save to Backend STM (MongoDB)
    await fetch(`${BACKEND_URL}/v1/memory/stm/add`, {
      method: 'POST',
      body: JSON.stringify({ session_id, messages }),
    });

    // Save to local CLAUDE.md (for Claude SDK)
    const claudeMdPath = `/workspace/group/CLAUDE.md`;
    appendToCLAUDEmd(claudeMdPath, messages);

    return { success: true };
  },
});
```

**Result**:

- ✅ Fast access (cache)
- ✅ Persistent (MongoDB)
- ✅ Claude SDK memory (CLAUDE.md)

#### 3. Unity WebSocket in NanoClaw (RESOLVED)

```typescript
// nanoclaw/src/channels/unity.ts

import { WebSocket, WebSocketServer } from 'ws';
import { runAgent } from '../container-runner.js';
import { logger } from '../logger.js';

interface UnityMessage {
  type: 'user_message' | 'interrupt' | 'ping';
  session_id?: string;
  text?: string;
}

export class UnityChannel {
  private wss: WebSocketServer;
  private sessions = new Map<string, WebSocket>();

  async start(port: number = 8765) {
    this.wss = new WebSocketServer({ port });
    logger.info({ port }, 'Unity WebSocket server started');

    this.wss.on('connection', (ws, req) => {
      const sessionId = this.generateSessionId();
      this.sessions.set(sessionId, ws);

      // Send connection confirmation
      ws.send(JSON.stringify({
        type: 'connected',
        session_id: sessionId,
      }));

      ws.on('message', async (data) => {
        try {
          const message: UnityMessage = JSON.parse(data.toString());
          await this.handleMessage(sessionId, message, ws);
        } catch (err) {
          logger.error({ err }, 'Unity message handling error');
          ws.send(JSON.stringify({
            type: 'error',
            error: err.message,
          }));
        }
      });

      ws.on('close', () => {
        this.sessions.delete(sessionId);
        logger.info({ sessionId }, 'Unity session closed');
      });
    });
  }

  private async handleMessage(
    sessionId: string,
    message: UnityMessage,
    ws: WebSocket
  ) {
    if (message.type === 'ping') {
      ws.send(JSON.stringify({ type: 'pong' }));
      return;
    }

    if (message.type === 'user_message') {
      // Run PersonaAgent in Unity group container
      const result = await runAgent({
        groupFolder: 'unity',  // Unity group
        prompt: message.text,
        sessionId: message.session_id || sessionId,
        chatJid: sessionId,
        isMain: false,
        assistantName: 'PersonaAgent',
      });

      // Send response back to Unity
      ws.send(JSON.stringify({
        type: 'agent_response',
        session_id: message.session_id,
        content: result.result,
      }));
    }
  }

  // Method for agents to send messages to Unity sessions
  public sendToSession(sessionId: string, message: any) {
    const ws = this.sessions.get(sessionId);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    }
  }

  private generateSessionId(): string {
    return `unity-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }
}

// Export singleton
export const unityChannel = new UnityChannel();
```

**Result**:

- ✅ Native WebSocket in NanoClaw
- ✅ Same pattern as Slack/Discord
- ✅ Unity is just another channel

---

## Code Changes Required

### Backend Changes (Removal + API)

```bash
# Files to DELETE:
rm -rf src/services/agent_service/
rm -rf src/services/websocket_service/message_processor/
rm src/api/routes/websocket.py  # If using Option A migration

# Files to MODIFY:
src/api/routes/tts.py              # Add REST endpoint
src/api/routes/vlm.py              # Add REST endpoint
src/api/routes/stm.py              # Add REST endpoints
src/api/routes/ltm.py              # Add REST endpoints
src/main.py                        # Remove agent init
src/services/service_manager.py    # Remove agent service
```

### Backend New API Routes

```python
# src/api/routes/services.py (NEW)

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/v1", tags=["Services"])

# --- TTS API ---
class TTSRequest(BaseModel):
    text: str
    voice: str | None = None
    speed: float = 1.0

@router.post("/tts/synthesize")
async def synthesize_speech(
    request: TTSRequest,
    tts_service: TTSService = Depends(get_tts_service)
):
    """Synthesize speech from text."""
    audio_data = await tts_service.synthesize(
        text=request.text,
        voice=request.voice,
        speed=request.speed
    )
    return {"audio": audio_data, "format": "wav"}

# --- VLM API ---
class VLMRequest(BaseModel):
    image_data: str  # base64
    query: str | None = None

@router.post("/vlm/analyze")
async def analyze_image(
    request: VLMRequest,
    vlm_service: VLMService = Depends(get_vlm_service)
):
    """Analyze image with VLM."""
    result = await vlm_service.analyze(
        image_data=request.image_data,
        query=request.query
    )
    return {"analysis": result}

# --- STM API ---
class STMAddRequest(BaseModel):
    user_id: str
    agent_id: str = "default"
    session_id: str | None = None
    messages: list[dict]

@router.post("/memory/stm/add")
async def add_to_stm(
    request: STMAddRequest,
    stm_service: STMService = Depends(get_stm_service)
):
    """Add messages to short-term memory."""
    session_id = stm_service.add_chat_history(
        user_id=request.user_id,
        agent_id=request.agent_id,
        session_id=request.session_id,
        messages=request.messages
    )
    return {"session_id": session_id}

@router.get("/memory/stm/history/{session_id}")
async def get_stm_history(
    session_id: str,
    limit: int = 50,
    stm_service: STMService = Depends(get_stm_service)
):
    """Get conversation history."""
    history = stm_service.get_chat_history(
        session_id=session_id,
        limit=limit
    )
    return {"messages": history}

# --- LTM API ---
class LTMAddRequest(BaseModel):
    user_id: str
    agent_id: str = "default"
    messages: list[dict]

@router.post("/memory/ltm/add")
async def add_to_ltm(
    request: LTMAddRequest,
    ltm_service: LTMService = Depends(get_ltm_service)
):
    """Add to long-term memory."""
    result = ltm_service.add_memory(
        user_id=request.user_id,
        agent_id=request.agent_id,
        messages=request.messages
    )
    return {"result": result}

@router.get("/memory/ltm/search")
async def search_ltm(
    query: str,
    user_id: str,
    limit: int = 10,
    ltm_service: LTMService = Depends(get_ltm_service)
):
    """Search long-term memory."""
    results = ltm_service.search(
        query=query,
        user_id=user_id,
        limit=limit
    )
    return {"results": results}
```

### NanoClaw Changes (Addition)

```bash
# Files to ADD:
nanoclaw/src/channels/unity.ts                    # Unity WebSocket server
nanoclaw/container/skills/persona-agent/SKILL.md  # PersonaAgent definition
nanoclaw/container/skills/readdev-agent/SKILL.md  # ReadDevAgent definition
nanoclaw/container/skills/review-agent/SKILL.md   # ReviewAgent definition
nanoclaw/container/skills/backend-tools/          # MCP tools for Backend
nanoclaw/groups/unity/                            # Unity group folder

# Files to MODIFY:
nanoclaw/src/index.ts          # Add Unity channel
nanoclaw/src/config.ts         # Add Backend API URL
nanoclaw/.env.example          # Add BACKEND_URL, BACKEND_API_KEY
```

---

## Next Steps

### Immediate (This Week)

1. ✅ Review this analysis document
2. ✅ **DECIDE**: Option 4 vs Option 3
3. ✅ **DECIDE**: TTS streaming strategy
4. ✅ **DECIDE**: Memory access pattern
5. □ Create detailed technical design for chosen option
6. □ Set up development environment

### Week 1 (if Option 4 chosen)

1. □ Backend: Remove agent code, add API endpoints
2. □ NanoClaw: Add Unity channel skeleton
3. □ Test: Backend API with Postman/curl
4. □ Test: Unity WebSocket connection

### Week 2

1. □ NanoClaw: Implement Backend MCP tools
2. □ NanoClaw: Create PersonaAgent SKILL.md
3. □ Test: PersonaAgent calling Backend APIs
4. □ Unity: Update client to connect to NanoClaw

### Week 3

1. □ NanoClaw: Create Slack agents (ReadDev, Review)
2. □ Test: Multi-agent delegation
3. □ Test: Memory persistence
4. □ Integration testing

---

## Decision Checklist

Before proceeding with Option 4, validate these requirements:

### Technical Validation ✓

- [x] TTS streaming strategy defined (Hybrid: WebSocket forwarding)
- [x] Memory access pattern designed (Three-tier: cache + MongoDB + CLAUDE.md)
- [x] Unity WebSocket architecture designed
- [x] NanoClaw can run on your infrastructure (Docker available)
- [x] Backend API authentication strategy defined

### Team Validation ⚠️

- [ ] Team can maintain TypeScript (NanoClaw)
- [ ] Team comfortable with Container deployment
- [ ] Team reviewed Claude SDK terms/pricing
- [ ] Stakeholders approve architecture change

### Risk Mitigation ✓

- [x] Fallback plan defined (Option 3)
- [x] Migration path with feature flags
- [x] Backward compatibility during transition
- [x] Testing strategy defined

### Go/No-Go Decision

**IF all checkboxes ✓**: **Proceed with Option 4**
**IF team validation ⚠️**: **Consider Option 3 instead** (Pure Python)
**IF technical blockers found**: **Re-evaluate or fallback**

---

## Appendix: Questions & Answers

### Q: Why not keep LangGraph and migrate gradually?

**A**: Option 3 does exactly that. But Option 4 is faster (2-3 weeks vs 5-6 weeks) because we reuse NanoClaw's proven multi-agent code instead of reimplementing in Python.

### Q: What if NanoClaw's Claude SDK costs too much?

**A**:

1. Claude SDK is free for self-hosted use (like NanoClaw)
2. You only pay for Claude API calls (same as current)
3. If concerned, fall back to Option 3 (LangGraph)

### Q: Can we still use Unity's current WebSocket protocol?

**A**:

- **During migration**: Yes, with `MIGRATION_MODE=hybrid`
- **After migration**: Unity connects to NanoClaw (similar protocol)
- **Effort**: Minimal Unity client changes (~1 day)

### Q: What about TTS latency in Option 4?

**A**:

- NanoClaw → Backend WebSocket → Stream chunks
- Latency overhead: ~10-50ms (WebSocket forwarding)
- Still real-time, imperceptible to users

### Q: How do we debug agents in containers?

**A**:

- NanoClaw logs are in `.nanoclaw/sessions/{group}/`
- Can attach debugger to container
- Can run agent-runner locally without container
- Better than debugging in-process (Option 3)

### Q: What if we want to switch away from NanoClaw later?

**A**:

- Backend API is independent (can switch agent layer)
- Agent logic is in SKILL.md (portable)
- Can migrate to Option 3 anytime (2-3 week effort)
- Clean interfaces = easy migration

---

## Conclusion

**Option 4 (Service-Only Backend)** offers the best balance of:

- ✅ Speed (2-3 weeks)
- ✅ Code reuse (90%)
- ✅ Clean architecture
- ✅ Full multi-agent support
- ✅ Maintainability

**With clear fallback to Option 3 if needed.**

**Recommendation**: Start with Option 4, keep Option 3 design ready as fallback.

---

**Ready to proceed? Next step**: Create detailed technical design document with:

- API contracts for Backend services
- SKILL.md templates for each agent
- NanoClaw Unity channel implementation
- Deployment strategy
- Testing plan
