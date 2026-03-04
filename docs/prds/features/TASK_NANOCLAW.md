# NanoClaw Agent Engine Tasks (Moved)

This document has been split into smaller, actionable files.

Go to:
- [task_nanoclaw/INDEX.md](task_nanoclaw/INDEX.md)

---

## N4: Interrupt / 중단 지원

> **Phase**: 4 (Week 2-3)
> **Priority**: P1
> **Dependencies**: N1

### Subtasks

#### N4.1: SSE 연결 끊김 감지 & Interrupt 엔드포인트

- **What**: FastAPI가 SSE 연결을 끊거나 interrupt 요청을 보낼 때 처리
- **Implementation**:
  - **SSE 연결 끊김**: Express response의 `close` 이벤트 감지 → 컨테이너 중단 트리거
  - **명시적 Interrupt**: `POST /api/agent/interrupt` 엔드포인트 추가
    ```typescript
    app.post('/api/agent/interrupt', async (req, res) => {
      const { session_id } = req.body;
      // 1. 해당 session의 컨테이너 찾기
      // 2. IPC _close sentinel 생성
      // 3. Grace period 후 강제 종료
      res.json({ success: true });
    });
    ```
  - 진행 중인 컨테이너에 `_close` sentinel file 생성 (기존 IPC 패턴 활용)
- **Test**: 대화 중 interrupt → 컨테이너 3초 이내 종료 확인

#### N4.2: 컨테이너 Graceful Shutdown 검증

- **What**: 기존 `_close` sentinel + idle timeout 로직 검증
- **Current State**: `agent-runner/src/index.ts`의 `shouldClose()` 함수가 `_close` sentinel 확인
- **Verification**:
  - `_close` sentinel 생성 → agent runner가 현재 LLM 호출 완료 후 종료
  - 강제 종료: sentinel 생성 후 5초 이내 미종료 시 `SIGTERM` → `SIGKILL`
  - 컨테이너 로그에 graceful shutdown 기록 확인
- **Test**: 긴 응답 생성 중 interrupt → 부분 응답 반환 + 정상 종료

---

## N5: Multi-Agent 설정 (Slack-Centric Specialized Agents)

> **Phase**: 5 (Week 3)
> **Priority**: P2
> **Dependencies**: N2, N3

분석 및 개발 보조를 담당하는 Specialized Agent(ReadDev, Review, PM 등)를 설정한다. 이 에이전트들은 **실시간 Unity Chat(WebSocket)과는 직접 통신하지 않으며, 오직 Slack과 같은 비실시간 채널을 통해서만 상세 결과를 출력**한다. Unity 사용자에게는 PersonaAgent가 요약된 안내만 전달한다.

### Subtasks

#### N5.1: ReadDevAgent Skill 정의 (Slack Only Output)

- **What**: `container/skills/readdev-agent/SKILL.md`
- **Output Channel**: **Slack 전용** (상세 분석 결과는 Slack thread로 직접 출력)
- **Rules**:
  - 상세 파일 경로, 라인 번호, 코드 블록 포함
  - 결과 전송 후 완료 신호를 PersonaAgent에 전달
  - **Unity Output 금지**: 실시간 응답(TTS용)을 생성하지 않음

#### N5.2: ReviewAgent Skill 정의 (Slack Only Output)

- **What**: `container/skills/review-agent/SKILL.md`
- **Output Channel**: **Slack 전용** (상세 리뷰 코멘트는 Slack thread로 출력)
- **Rules**:
  - 코드 리뷰 피드백 및 개선 제안 출력
  - **Unity Output 금지**: 실시간 응답(TTS용)을 생성하지 않음

#### N5.3: Inter-Agent Delegation & Multi-Channel Routing

- **What**: PersonaAgent(Unity) <-> Specialized Agent(Slack) 협업 로직
- **Implementation**:
  1. PersonaAgent가 `@ReadDevAgent` 호출 시, 해당 요청을 Slack 채널로 라우팅
  2. ReadDevAgent는 Slack에 상세 리포트 작성 (Unity로의 텍스트/오디오 전송 없음)
  3. 작업 완료 후 PersonaAgent는 Unity 사용자에게 "분석이 완료되었습니다. 자세한 내용은 슬랙을 확인해주세요." 라고 요약 안내 (음성/텍스트)
- **Test**: Unity에서 분석 요청 -> Slack에 상세 리포트 생성 -> Unity에서는 PersonaAgent의 안내 멘트만 수신

#### N5.4: Slack 채널 연동 (PersonaAgent & Multi-Channel Participation)

- **What**: NanoClaw에 Slack 채널 추가 및 PersonaAgent를 포함한 멀티 에이전트 라우팅 구현
- **Implementation**:
  - `src/channels/slack.ts` 구현 (기존 WhatsApp 채널 패턴 참조)
  - Slack Bot Token, App Token 환경변수 설정
  - **PersonaAgent 연동**: `@PersonaAgent` mention 시 Unity와 동일한 `persona-agent` Skill로 라우팅
  - **공유 메모리**: MCP Tool을 통해 Unity 세션의 STM/LTM을 조회하여 대화 연속성 보장
  - **출력 최적화**: 채널 메타데이터를 기반으로 Slack에서는 마크다운 형식을 사용한 상세 답변 출력
- **Note**: WhatsApp 채널 (`src/channels/whatsapp.ts`)의 구조를 따르되, Slack SDK(`@slack/bolt`) 및 Socket Mode 활용
- **Test**: Slack에서 @PersonaAgent mention → "유니티에서 나눴던 대화 기억해?" 질문 → 연속성 있는 답변 수신 확인

---

## N6: Agent Runner 토큰 스트리밍 확장

> **Phase**: 1-2 (Week 1) — N1.2의 사전 작업
> **Priority**: P0
> **Dependencies**: None

### Subtasks

#### N6.1: Claude SDK `query()` 이벤트 콜백 분석

- **What**: Claude Code SDK의 `query()`가 토큰 단위 이벤트를 제공하는지 확인
- **Analysis**:
  - `@anthropic-ai/claude-agent-sdk`의 streaming 옵션 조사
  - `onEvent`, `onToken`, `onMessage` 등 콜백 존재 여부
  - 만약 없다면: SDK stdout에서 incremental parsing 필요
- **Output**: 토큰 스트리밍 가능 여부 기술 보고서

#### N6.2: 토큰 스트리밍 출력 프로토콜 구현

- **What**: Agent Runner가 토큰을 stdout으로 실시간 출력하는 프로토콜
- **Implementation** (`container/agent-runner/src/index.ts` 수정):
  ```typescript
  const TOKEN_START = '---NANOCLAW_TOKEN---';
  const TOKEN_END = '---NANOCLAW_TOKEN_END---';

  function writeToken(text: string): void {
    console.log(TOKEN_START);
    console.log(JSON.stringify({ text }));
    console.log(TOKEN_END);
  }

  // SDK query() 호출 시 onEvent 콜백에서 writeToken() 호출
  ```
- **Impact**: `container-runner.ts`의 stdout 파싱 로직에 TOKEN_MARKER 처리 추가
- **Test**: 프롬프트 → stdout에 토큰 마커가 순서대로 출력 확인

---

## Definition of Done (Phase별)

### Phase 1: SSE 엔드포인트

- [ ] `POST /api/agent/run` SSE 엔드포인트 동작
- [ ] curl로 토큰 단위 SSE 이벤트 수신 확인
- [ ] 인증 동작 (유효/무효 API Key)
- [ ] Keepalive ping 15초마다 전송

### Phase 2: 토큰 스트리밍

- [ ] Agent Runner → Container Runner → SSE 토큰 파이프라인 동작
- [ ] 단일 프롬프트에서 토큰이 실시간으로 SSE 이벤트로 전달
- [ ] `done` 이벤트에 nanoclaw_session_id 포함

### Phase 3: Skill & MCP Tools

- [ ] PersonaAgent SKILL.md 정의 완료
- [ ] 4개 MCP Tool 모두 구현 및 개별 테스트 통과
- [ ] MCP Tool 호출 성공률 98%+
- [ ] 페르소나 테스트 셋 10개 질문 일관된 톤앤매너

### Phase 4: Interrupt 지원

- [ ] SSE 연결 끊기 → 컨테이너 3초 이내 중단
- [ ] `POST /api/agent/interrupt` → sentinel file 생성 확인
- [ ] Graceful shutdown 로그 기록

### Phase 5: Multi-Agent

- [ ] ReadDevAgent, ReviewAgent Skill 정의 및 동작
- [ ] @mention 위임 → 결과 반환 E2E 동작
- [ ] Slack 채널 기본 동작 (선택)
