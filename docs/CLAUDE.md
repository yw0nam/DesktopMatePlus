# backend/docs/ — Backend Documentation Index

Updated: 2026-03-26

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
| `setup/ENVIRONMENT.md` | 환경 변수 전체 목록 (OPENAI, MongoDB, Qdrant, Slack 등) |
| `setup/DEPENDENCIES.md` | 의존성 설치 가이드 |
| `patch/` | 날짜별 변경사항 기록 (YYYYMMDD.md). 새 패치노트는 여기에 추가 |
| `superpowers/plans/` | Claude Code 세션용 구현 계획서 (로컬 작업 파일, git 미커밋) |
| `superpowers/specs/` | 구현 전 설계 스펙 문서 |

> **Dev guides (context-sensitive, auto-loaded):**
> `src/CLAUDE.md` — Logging guide · `tests/CLAUDE.md` — Testing guide

## 자주 참조하는 문서

- [REST API Guide](./api/CLAUDE.md) — 엔드포인트 추가/수정 시 출발점
- [WebSocket API Guide](./websocket/CLAUDE.md) — WS 메시지 타입 추가/수정 시
- [Environment Variables](./setup/ENVIRONMENT.md) — 새 환경 변수 추가 시

---

# Document Authoring Guide

All documents focus on **Actionability** and **Modularity**.

## 1. Core Principles

| Principle | Description |
|-----------|-------------|
| **Zero-Latency Start** | Readers should be able to write code or perform tasks immediately after reading—no additional exploration needed. |
| **Hard Limit 200** | Core content must not exceed 200 lines. Physical limit for agent context windows and human attention span. |
| **Lazy Loading (Appendix)** | Edge cases and detailed configs go into Appendix for on-demand reference. |
| **Reflect src code structure** | Document structure should mirror source code organization. |

## 2. Standard Document Structure

```markdown
# [Document Title]

Updated: YYYY-MM-DD

## 1. Synopsis
- **Purpose**: One-line summary
- **I/O**: Input → Output

## 2. Core Logic
- [Step 1]: Implementation method
- [Constraints]: Rules that must be followed

## 3. Usage
- Happy Path example (brief)

---

## Appendix
### A. Troubleshooting
### B. PatchNote
YYYY-MM-DD: What changed and why
```

## 3. Writing Rules

**200-Line Rule:** Main body (`## 1` through `## 3`) must never exceed 200 lines. Remove background context, optimize snippets, use directive language ("Do X" not "It's recommended to do X").

**Splitting Strategy:** When approaching 200 lines, split by functional units. Manage splits as a thin index document.

**Appendix:** Move edge cases, full references, and error catalogs here. Keep main body focused on the happy path.

**PatchNote:** Always add a dated patch note to Appendix when updating a document.

## 4. Quality Checklist

- [ ] Main body under 200 lines?
- [ ] Can someone write code immediately after reading?
- [ ] Edge cases moved to Appendix?
- [ ] Writing is directive and unambiguous?

---

## Appendix

### PatchNote

2026-03-23: Initial version as directory index.
2026-03-25: Merged Document Authoring Guide content in (moved from `.claude/rules/DOCUMENT_GUIDE.md`). Updated directory map to reflect new guide locations.
2026-03-26: Updated directory map — `stm_service/` removed, checkpointer-based architecture.
