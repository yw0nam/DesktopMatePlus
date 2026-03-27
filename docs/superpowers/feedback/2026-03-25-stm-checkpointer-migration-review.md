# STM Checkpointer Migration Design Review

**Date:** 2026-03-25
**Target Spec:** `docs/superpowers/specs/2026-03-25-stm-checkpointer-migration-design.md`
**Review Context:** `CLAUDE.md` (DesktopMate+ Backend Core Philosophy & Conventions)

---

## 1. 총평 (Overall Review)
본 설계 문서는 `CLAUDE.md`의 핵심 철학인 **"단순화 및 최적화(Simplify and optimize)"**, **"최대한 제거(Eliminate as much as possible)"**에 완벽하게 부합합니다. 기존의 독자적인 `MongoDBSTM` 구현을 완전히 제거하고 LangGraph의 내장 `MongoDBSaver` 체계로 위임함으로써, 아키텍처의 복잡도를 크게 낮추고 향후 확장성을 확보한 훌륭한 아키텍처 결정입니다.

## 2. 강점 및 가이드라인 부합 사항 (Alignments with CLAUDE.md)
- **비동기 우선(Asynchronous First):** `DelegateTaskTool`을 기존 동기식 `httpx.Client`에서 `httpx.AsyncClient` 및 `async _arun()`으로 변경한 점은 비동기 I/O 원칙을 정확히 준수했습니다.
- **타입 힌팅(Type Hinting):** `ReplyChannel | None`과 같이 Python 3.10+ 스타일의 Union 타입(`|`)을 사용하여 컨벤션을 잘 따르고 있습니다.
- **목적에 맞는 데이터 분리:** Checkpointer가 직렬화된 무거운 데이터를 다루는 점을 고려하여, 조회 및 Sweep용으로 얇은 `session_registry` 컬렉션을 분리 유지하기로 한 결정은 성능 및 "Speed up" 철학에 부합하는 좋은 설계입니다.

## 3. 개선 및 고려 사항 (Feedback & Considerations)

### A. 비동기 작업의 안정성 (`asyncio.create_task` vs `BackgroundTasks`)
- 설계 문서(`5-4`, `5-5`, `5-6` 등)에서 논블로킹 처리를 위해 `asyncio.create_task()`가 다수 사용되고 있습니다.
- **피드백:** LangGraph 미들웨어나 깊은 내부 로직에서는 `asyncio.create_task`가 적절할 수 있으나, 작업 중 예외(Exception)가 발생할 경우 조용히 실패(Silent Failure)할 위험이 있습니다. 에러가 발생해도 로깅이 보장되도록 `core/logger` 모듈과 연계된 예외 처리 래퍼(Wrapper)를 씌우거나, FastAPI의 HTTP 요청 범위 내에서 실행되는 경우라면 프레임워크 내장 `BackgroundTasks`의 활용을 고려해 볼 필요가 있습니다.

### B. 용어 및 인터페이스 일관성: `session_id` vs `thread_id`
- 문서의 `5-1` 섹션에서 내부 `configurable` 키를 `"session_id"`에서 `"thread_id"`로 전면 통일한다고 명시했습니다.
- **피드백:** LangGraph 표준인 `thread_id`로 내부를 통일하는 것은 타당합니다. 다만, 외부 노출 API (예: `GET /sessions`, `/v1/stm/...` 및 웹소켓 파라미터)에서도 이를 `thread_id`로 변경할 것인지, 아니면 기존 클라이언트 호환성을 위해 외부는 `session_id`를 유지하고 내부에서만 `thread_id`로 매핑할 것인지 명확한 정책 결정이 필요합니다.

### C. 에러 핸들링 (Error Handling)
- `CLAUDE.md`는 "가능한 경우 사용자 정의 예외 클래스를 사용할 것"을 권장합니다.
- **피드백:** `agent.aupdate_state` 호출 시 MongoDB 연결 장애나 타임아웃으로 인해 상태 업데이트가 실패하는 경우의 처리가 누락되어 있습니다. 특히 태스크 상태 변경(`pending_tasks` 업데이트) 실패 시 상태 불일치가 발생할 수 있으므로, 적절한 재시도(Retry) 로직이나 커스텀 예외 발생 및 로깅 처리가 설계에 반영되면 더 견고해질 것입니다.

### D. 의존성 주입 (Dependency Injection)
- **피드백:** `/v1/stm` 라우트나 웹소켓 핸들러에서 `stm_service` 참조가 제거되고 `agent_service`나 `ltm_service`를 활용하는 구조로 재작성될 때, FastAPI의 `Depends`를 통한 종속성 주입 원칙이 계속해서 일관성 있게 유지되도록 구현 단계에서 주의가 필요합니다.

## 4. 결론 (Conclusion)
전반적으로 코드 볼륨을 크게 줄이면서 시스템의 안정성과 LangGraph 호환성을 높이는 뛰어난 제안입니다. 언급된 `asyncio.create_task`의 예외 로깅 보완과 `session_id` / `thread_id`의 인터페이스 경계 명확화 정도만 구현 시 반영한다면, 설계 원안대로 즉시 진행(Approved)해도 좋을 훌륭한 마이그레이션 계획입니다.
