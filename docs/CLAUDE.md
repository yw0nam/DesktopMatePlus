# backend/docs/ — Backend Documentation Index

Updated: 2026-03-23

FastAPI 백엔드의 API 스펙, WebSocket 프로토콜, 데이터 흐름, 개발 가이드를 보관한다.
코드는 없으며, 읽기·참조 전용.

## Directory Map

| 경로 | 목적 |
|------|------|
| `api/CLAUDE.md` | REST API 전체 엔드포인트 목록 및 링크 허브 (`/v1` 기준, base: `127.0.0.1:5500`) |
| `api/*.md` | 개별 엔드포인트 상세 (STM, LTM, Nanoclaw Callback, Slack Events 등) |
| `websocket/CLAUDE.md` | WebSocket 메시지 프로토콜 허브 (`/ws/chat`) |
| `websocket/WebSocket_*.md` | 개별 메시지 타입 상세 (StreamToken, TtsChunk, InterruptStream 등) |
| `data_flow/` | 주요 흐름 Mermaid 시퀀스 다이어그램. `chat/`, `channel/`, `session/` 별 분류 |
| `.claude/rules/DOCUMENT_GUIDE.md` | 문서 작성 규칙 (200줄 한도, 표준 구조, PatchNote 규칙) |
| `.claude/rules/TESTING_GUIDE.md` | 테스트 작성 가이드 |
| `.claude/rules/LOGGING_GUIDE.md` | Loguru 로깅 가이드 |
| `setup/ENVIRONMENT.md` | 환경 변수 전체 목록 (OPENAI, MongoDB, Qdrant, Slack 등) |
| `setup/DEPENDENCIES.md` | 의존성 설치 가이드 |
| `patch/` | 날짜별 변경사항 기록 (YYYYMMDD.md). 새 패치노트는 여기에 추가 |
| `superpowers/plans/` | Claude Code 세션용 구현 계획서 (로컬 작업 파일, git 미커밋) |
| `superpowers/specs/` | 구현 전 설계 스펙 문서 |

## 자주 참조하는 문서

- [REST API Guide](./api/CLAUDE.md) — 엔드포인트 추가/수정 시 출발점
- [WebSocket API Guide](./websocket/CLAUDE.md) — WS 메시지 타입 추가/수정 시
- [Environment Variables](./setup/ENVIRONMENT.md) — 새 환경 변수 추가 시
