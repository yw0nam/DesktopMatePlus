# Scripts Reference

`scripts/clean/` 디렉토리의 모든 셸 스크립트 사용 가이드.

---

## scripts/clean/garden.sh

**역할**: GP(Golden Principles) 검증 + 자동 fix + 품질 보고서 생성

```bash
bash scripts/clean/garden.sh [--gp GP-N] [--dry-run]
```

- GP-1~10 verify 커맨드 순서대로 실행
- Minor 위반은 ruff 등으로 자동 수정
- 결과를 `docs/reports/quality-YYYY-MM-DD.md`에 저장
- `--gp GP-N`: 특정 GP 하나만 실행 (예: `--gp GP-11`)
- `--dry-run`: 자동 수정 없이 탐지만

---

## scripts/e2e.sh

**역할**: Backend E2E 검증 파이프라인

```bash
bash scripts/e2e.sh
```

- Phase 순서: External services → Backend 시작 → Health → Examples → Log ERROR 검사

---

## scripts/clean/check_docs.sh

**역할**: 문서 품질 린터 (dead link, 200줄 한도, spec 커버리지)

```bash
bash scripts/clean/check_docs.sh [--fix] [--dry-run]
```

- `docs/` 내 마크다운 dead link 탐지
- 200줄 초과 파일 경고
- `docs/superpowers/specs/` 디렉토리 존재 및 spec 파일 수 확인
- `docs/superpowers/` 는 스캔 제외

---

## scripts/clean/run-quality-agent.sh

**역할**: quality-agent를 `claude` CLI로 실행

```bash
bash scripts/clean/run-quality-agent.sh
```

- cron 설정: `7 9 * * *` (09:07 KST 매일)
- quality-agent 실행 → 보고서 작성 → PR 오픈
- 결과 로그: `docs/reports/YYYY/MM/quality-YYYY-MM-DD.md`

---

## scripts/clean/babysit-collect.sh

**역할**: 오픈 PR 상태 수집 (babysit/pr-pruner 공용 헬퍼)

```bash
bash scripts/clean/babysit-collect.sh
```

출력 형식 (탭 구분):
```
REPO  NUMBER  TITLE  REVIEW_DECISION  MERGEABLE  DAYS_OLD  IS_DRAFT  LABELS
```

- 대상 레포: `yw0nam/DesktopMatePlus` (backend)
- `REVIEW_DECISION`: `APPROVED` | `CHANGES_REQUESTED` | `REVIEW_REQUIRED` | `""`
- `/babysit`, `/pr-pruner` 커맨드가 내부적으로 호출

---

## scripts/clean/merged-recent.sh

**역할**: 최근 N시간 내 머지된 PR + 미처리 코멘트 수 집계

```bash
bash scripts/clean/merged-recent.sh [hours=24]
```

출력 형식 (탭 구분):
```
REPO  NUMBER  TITLE  MERGED_AT  UNRESOLVED  TOTAL_INLINE
```

- `/post-merge-sweeper` 커맨드가 Step 1에서 호출
- `UNRESOLVED > 0`인 PR은 후속 `pr-comments-filter.sh` 처리 대상

---

## scripts/clean/pr-comments-filter.sh

**역할**: 단일 PR의 인라인 리뷰 코멘트 미처리/처리 분류

```bash
bash scripts/clean/pr-comments-filter.sh <owner/repo> <pr_number>
```

출력:
```
SUMMARY: UNRESOLVED=N RESOLVED=N TOTAL=N
UNRESOLVED  <user>  <path>  <body 첫 80자>
```

- 답변이 달린 코멘트 → RESOLVED
- 답변 없는 봇/사람 코멘트 → UNRESOLVED
- `/post-merge-sweeper` Step 2에서 호출

---

## scripts/clean/cleanup-merged.sh

**역할**: 머지 완료된 워크트리 + 원격 브랜치 일괄 정리

```bash
bash scripts/clean/cleanup-merged.sh [--dry-run]
```

- 대상: backend repo
- 브랜치 prefix 패턴: `feat|fix|docs|refactor|chore|test|ci|build|quality|design`
- `--dry-run`: 실제 삭제 없이 대상 목록만 출력
