# /pr-pruner — Stale PR Pruner

14일 이상 활동이 없는 오래된 PR을 탐색하고 정리한다.

## 실행 순서

### 1. 오픈 PR 수집 및 staleness 판단

```bash
bash scripts/clean/babysit-collect.sh
```

출력 형식 (탭 구분): `REPO  NUMBER  TITLE  REVIEW_DECISION  MERGEABLE  DAYS_OLD  IS_DRAFT  LABELS`

`DAYS_OLD` 기준:
- 14일 이상: **stale** → Step 3
- 7~13일: **warning** → Step 2
- 14일 미만 또는 `IS_DRAFT=true` 또는 `LABELS`에 `keep-open` 포함: **스킵**

### 2. Warning PR — 코멘트 남기기

```bash
gh pr comment <number> --repo <repo> --body "⚠️ This PR has had no activity for 7+ days. It will be closed automatically if no action is taken within 7 more days."
```

### 3. Stale PR — 닫기

먼저 확인 코멘트를 남기고 close:
```bash
gh pr comment <number> --repo <repo> --body "Closing this PR due to 14+ days of inactivity. Feel free to reopen if still relevant."
gh pr close <number> --repo <repo>
```

예외:
- Draft PR: 스킵 (개발 중으로 간주)
- `keep-open` 라벨이 있는 PR: 스킵

### 4. 결과 요약

경고 코멘트 남긴 PR, 닫은 PR, 스킵한 PR 목록을 출력.
