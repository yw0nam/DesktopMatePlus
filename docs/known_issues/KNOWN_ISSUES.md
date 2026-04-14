# Known Issues

각 이슈 상세는 `docs/known_issues/` 개별 파일에 기록.

형식: `- [ ] **KI-{N}** [{severity}] {component}: {one-line summary} → [상세](link)`

> 해결된 이슈는 `docs/release_notes/`에 보관됩니다.

---

## Open Issues

### PR #25–#27 (`feat/phase6*`) — Builtin Tools / MCP / ToolGate

- [ ] **KI-16** [Low] docker: `openai_chat_agent.yml`이 Docker/로컬 공유 — `tool_config.builtin.filesystem.root_dir: /tmp/agent-workspace`가 Docker에서 ephemeral (컨테이너 재시작 시 소멸). 현재 `enabled: false`라 미발현. **해결 방향: filesystem tool 활성화 PR에서 `openai_chat_agent.docker.yml` 분리 + `docker.yml` 참조 변경 + `docker-compose.yml`에 named volume 추가 + `src/configs/agent/openai_chat_agent.py:27` Pydantic 기본값 수정.** (방법 B env var interpolation은 YAML 로더 cross-cutting 변경 필요로 reject)

---

## Resolved Issues

| Issue | PR | Summary | Resolution |
|-------|-----|---------|------------|
| KI-18 | #30 | E2E 테스트 시 MongoDB 세션 누적 | `stm_session` fixture를 `yield` + teardown `DELETE`로 수정 |
| KI-19 | #28 | `_ConcreteAgent.stream` 타입 시그니처 불일치 | `return` 제거, bare `yield`만 남겨 async generator로 수정 |
| KI-20 | #28 | `/health` severity 직렬화 검증 부재 | `ErrorSeverity` enum 사용, `"severity" in module` assertion 추가 |
| KI-21 | #29 | `scripts/run.sh` YAML 경로 참조 우려 | Won't Fix — 실제 미발현 확인 |

---

## Won't Fix

| Issue | Reason |
|-------|--------|
| KI-2 | 6개 서비스 파일 200줄 초과 — YAGNI, 억지 분리 시 가독성 저하 |
| KI-3 | `validate_token()` 항상 `"valid_token"` — 개인 시스템이므로 YAGNI |
| KI-7 | `_severity()` 문자열 키워드 매칭 — 현재 정상 동작 |
| KI-11 | `RestrictedShellTool` cwd 제한 없음 — Docker 샌드박스로 충분 |
