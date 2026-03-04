## FastAPI Orchestrator Tasks (Moved)

This document has been split into smaller, actionable files.

Go to:
- [task_fastapi/INDEX.md](task_fastapi/INDEX.md)
          task = asyncio.create_task(self._synthesize_and_send(text, emotion, turn_id, seq))
          self._tasks.add(task)
          task.add_done_callback(self._tasks.discard)
  ```
- **Test**: 3개 문장 동시 TTS 생성 → 각각 독립적으로 완료 확인

#### F4.2: 순서 보장 오디오 전송

- **What**: TTS 결과를 sequence number 기반으로 Unity에 전송
- **Output Format**:
  ```json
  {
    "type": "audio",
    "data": "base64_audio_data",
    "sequence": 0,
    "emotion": "happy",
    "text": "원본 텍스트",
    "turn_id": "...",
    "duration_ms": 1200
  }
  ```
- **Implementation**:
  - 각 TTS 태스크에 sequence number 부여
  - Unity 측에서 sequence 기반 재정렬 (서버는 완료 순서대로 전송)
- **Test**: 3개 문장 (긴 → 짧은 → 중간) → Unity가 sequence 순서로 재생 확인

#### F4.3: 동시 실행 제한 및 Backpressure

- **What**: TTS 태스크 수 제한 + 메모리 보호
- **Implementation**:
  - `asyncio.Semaphore(3)` 으로 동시 TTS 태스크 최대 3개 제한
  - Semaphore 대기 중에도 메인 스트림(토큰 릴레이)은 계속 진행
  - 메모리 사용량 모니터링 (태스크별 오디오 데이터 크기 추적)
- **Test**: 10개 문장 연속 → 동시 실행 3개 이하 확인, 메인 스트림 지연 없음

#### F4.4: TTS 태스크 취소 (Interrupt 연동)

- **What**: Interrupt 발생 시 미완료 TTS 태스크 일괄 취소
- **Implementation**:
  ```python
  async def cancel_all(self) -> int:
      """모든 진행 중인 TTS 태스크 취소, 취소된 수 반환"""
      cancelled = 0
      for task in list(self._tasks):
          if not task.done():
              task.cancel()
              cancelled += 1
      return cancelled
  ```
- **Test**: TTS 3개 진행 중 interrupt → 모든 태스크 cancelled 확인

---

## F5: Interrupt 흐름 구현 (Distributed Sentinel)

> **Phase**: 4 (Week 2-3)
> **Priority**: P1
> **Dependencies**: F2, F4, N4

사용자 중단 요청 시 전체 파이프라인을 즉시 중단하는 분산 중단 메커니즘.

### Subtasks

#### F5.1: Unity → FastAPI Interrupt 수신

- **What**: Unity의 interrupt 메시지 수신 및 처리 시작점
- **Input**: `{"type": "interrupt", "turn_id": "..."}`
- **Implementation**:
  1. NanoClaw SSE 연결 즉시 끊기 (`NanoClawClient.interrupt()`)
  2. `TTSTaskSpawner.cancel_all()` 호출
  3. Unity에 `{"type": "clear_queue"}` 이벤트 전송
  4. `MessageProcessor` 상태를 `INTERRUPTED`로 전환
- **Latency Target**: 수신 → clear_queue 전송까지 50ms 이내

#### F5.2: NanoClaw Interrupt 신호 전달

- **What**: NanoClaw에 중단을 알리고 확인하는 프로토콜
- **Implementation**:
  - SSE 연결 끊기 시 NanoClaw가 자동 감지
  - 추가로 `POST /api/agent/interrupt` 호출 (session_id 전달)
  - NanoClaw가 컨테이너 내 sentinel file 생성하여 agent 중단
- **Test**: 대화 중 interrupt → NanoClaw 로그에서 중단 확인, 컨테이너 정리 확인

#### F5.3: Turn Management 리팩토링

- **What**: 기존 `MessageProcessor`를 NanoClaw 연동용으로 리팩토링
- **Implementation**:
  - 기존 `produce_agent_events` → `StreamInterceptor.process_stream`으로 교체
  - Turn lifecycle: `PROCESSING` → `COMPLETED` / `INTERRUPTED` / `FAILED`
  - 기존 `token_queue` → `StreamInterceptor` 내부 버퍼로 대체
  - `cleanup()` 로직에 NanoClaw session 정리 추가
- **Test**: 정상 완료, 중단, 에러 3가지 시나리오 모두 리소스 누수 없음 확인

---

## F6: Memory 선주입 로직

> **Phase**: 5 (Week 3)
> **Priority**: P1
> **Dependencies**: F1.3, F2

### Subtasks

#### F6.1: STM Pre-injection (매 턴)

- **What**: NanoClaw 요청 전 STM 대화 기록을 프롬프트에 포함
- **Implementation**:
  - `handle_chat_message` 시점에 `STMService.get_chat_history()` 호출
  - 결과를 NanoClaw 요청의 `context.stm_history`에 포함
  - 최근 N개 메시지 (기본 10개, 클라이언트 `limit` 파라미터로 조정)
- **Test**: 이전 대화 내용이 Agent 응답에 반영되는지 확인

#### F6.2: LTM 업데이트 전략

- **What**: LTM을 주기적으로 업데이트하는 전략 구현
- **Implementation**:
  - **턴 카운트 기반**: 5턴마다 `LTMService.add_memory()` 호출
  - **대화 길이 기반**: 누적 토큰 > 2000 시 업데이트 트리거
  - 업데이트는 `asyncio.create_task`로 백그라운드 실행 (응답 지연 없음)
  - LTM 검색은 NanoClaw Agent가 `memory_search_ltm` MCP Tool로 필요 시 호출
- **Test**: 5턴 대화 후 LTM에 기록 저장 확인, 검색으로 이전 대화 내용 조회 확인

---

## F7: 기존 Agent 로직 정리 (Migration Mode)

> **Phase**: 1 (Week 1) — F1과 병행
> **Priority**: P2
> **Dependencies**: None

### Subtasks

#### F7.1: MIGRATION_MODE 플래그 구현

- **What**: `MIGRATION_MODE` 환경변수로 legacy/nanoclaw 모드 분기
- **Implementation**:
  ```python
  MIGRATION_MODE = os.getenv("MIGRATION_MODE", "legacy")
  # "legacy": 기존 OpenAIChatAgent + MessageProcessor
  # "nanoclaw": NanoClaw SSE 연동 + StreamInterceptor
  ```
  - `src/main.py` lifespan에서 모드별 초기화 분기
  - Legacy 모드: 기존 코드 그대로 동작
  - NanoClaw 모드: `NanoClawClient`, `StreamInterceptor`, `TTSTaskSpawner` 초기화
- **Test**: 두 모드 모두 서버 정상 기동 확인

#### F7.2: 라우터 분기 구성

- **What**: WebSocket 핸들러에서 모드별 메시지 처리 분기
- **Implementation**:
  - `MessageHandler.handle_chat_message`에서 모드 확인
  - Legacy: 기존 `AgentService.stream()` → `MessageProcessor`
  - NanoClaw: `NanoClawClient.run_agent()` → `StreamInterceptor`
- **Test**: 각 모드에서 대화 E2E 동작 확인

---

## F8: Health Check & Monitoring

> **Phase**: 5 (Week 3)
> **Priority**: P2
> **Dependencies**: F2

### Subtasks

#### F8.1: NanoClaw Health Check

- **What**: 주기적 NanoClaw 가용성 모니터링
- **Implementation**:
  - 30초마다 `NanoClawClient.health_check()` 호출
  - 실패 시 Circuit Breaker 상태 업데이트
  - 복구 감지 시 Safe Mode → Normal Mode 자동 전환
- **Test**: NanoClaw 다운 → Safe Mode 전환 → NanoClaw 복구 → Normal 복귀 확인

#### F8.2: Performance Metrics 수집

- **What**: 핵심 성능 지표 로깅
- **Metrics**:
  - TTFT (Time To First Token): NanoClaw 요청 → 첫 토큰 수신
  - TTS Latency: 문장 완성 → 오디오 생성 완료
  - E2E Latency: 사용자 메시지 → 첫 text 이벤트 Unity 수신
  - Interrupt Latency: interrupt 수신 → clear_queue 전송
- **Implementation**: Loguru structured logging + 선택적 Prometheus metrics
- **Test**: 메트릭이 정상 수집되고 로그에 기록되는지 확인

---

## Definition of Done (Phase별)

### Phase 1: Backend API 정립

- [ ] 모든 `/v1/*` 엔드포인트 구현 및 OpenAPI 문서 노출
- [ ] 단위 테스트 커버리지 90%+
- [ ] 로컬 네트워크 기준 API 응답 레이턴시 50ms 이내
- [ ] `MIGRATION_MODE=legacy`에서 기존 기능 동일 동작

### Phase 2: Orchestrator 구현

- [ ] NanoClaw SSE → FastAPI → Unity 토큰 릴레이 동작
- [ ] TTFT (Warm) 200ms 이내
- [ ] 동시 20 세션, 1시간 메모리 누수 없음

### Phase 3: TTS 비동기 파이프라인

- [ ] 문장 단위 비동기 TTS 합성 동작
- [ ] TTS 합성이 토큰 스트리밍을 블로킹하지 않음 확인
- [ ] MCP Tool 호출 성공률 98%+

### Phase 4: Unity 연동 + Interrupt

- [ ] 텍스트-오디오 싱크 오차 100ms 이내
- [ ] Interrupt 발생 시 50ms 이내 모든 출력 중단
- [ ] clear_queue 이벤트로 Unity 재생 큐 즉시 비움

### Phase 5: 최종 검증

- [ ] 10분 연속 대화: 연결 끊김 / 메모리 부족 0건
- [ ] Circuit Breaker: NanoClaw 장애 → Safe Mode 전환 → 복구 시나리오 통과
- [ ] 페르소나 일관성: 10개 테스트 질문 통과
