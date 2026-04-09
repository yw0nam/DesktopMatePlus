# /babysit — PR Lifecycle Manager

오픈 PR 전수 점검. 코드 리뷰 대응, 자동 리베이스, 프로덕션 머지까지 관리.

## 실행 순서

### 1. 오픈 PR 수집

```bash
bash scripts/clean/babysit-collect.sh
```

출력 형식 (탭 구분): `REPO  NUMBER  TITLE  REVIEW_DECISION  MERGEABLE  DAYS_OLD  IS_DRAFT  LABELS`

- `REVIEW_DECISION`: `APPROVED` | `CHANGES_REQUESTED` | `REVIEW_REQUIRED` | `""` (미설정)
- `MERGEABLE`: `MERGEABLE` | `CONFLICTING` | `UNKNOWN`
- 출력이 없으면 오픈 PR 없음 → 종료

### 2. REQUEST_CHANGES 또는 미처리 인라인 코멘트가 있는 PR

`REVIEW_DECISION`이 `CHANGES_REQUESTED`이거나 미처리 코멘트가 의심되는 PR:

```bash
bash scripts/clean/pr-comments-filter.sh <repo> <number>
```

출력:

```
SUMMARY: UNRESOLVED=N RESOLVED=N TOTAL=N
UNRESOLVED  <bot>  <path>  <요약>  # UNRESOLVED > 0 일 때만
```

- `UNRESOLVED=0`: 모든 코멘트 처리 완료 — 다음 단계로
- `UNRESOLVED > 0`: 각 항목 검토 후 처리
  - **false positive**: 해당 코멘트에 답변 후 넘어감
  - **valid**: 코드 수정 후 push, re-request review

### 3. 리베이스가 필요한 PR

`MERGEABLE`이 `CONFLICTING`인 PR: 해당 레포 로컬에서 rebase 후 force push.

### 4. 미승인 PR (`REVIEW_DECISION=""`) → 자동 리뷰 후 승인

`oh-my-claudecode:code-reviewer` + `oh-my-claudecode:security-reviewer` 서브에이전트를 스폰하여 리뷰.

- **Pass**: GitHub API로 APPROVE 후 Step 5로 진행
- **Fail**: 이슈 목록 코멘트 남기고 대기 (머지 안 함)

```bash
# pass 판정 시:
gh api repos/<repo>/pulls/<number>/reviews \
  -X POST \
  -f body="Automated review passed (code-reviewer + security-reviewer). Auto-approving." \
  -f event="APPROVE"
```

### 5. APPROVED + CI 통과 PR → 머지 + CHANGELOG 업데이트

`REVIEW_DECISION=APPROVED`이고 CI 통과한 PR:

```bash
# 1) 머지 전에 커밋 목록을 미리 조회한다 (머지 후에는 PR API 접근 불가)
gh pr view <number> --repo <repo> --json commits,title,baseRefName

# 2) 리모트 머지
gh pr merge <number> --repo <repo> --merge

# 3) base 브랜치로 체크아웃 후 로컬 동기화
git checkout <baseRefName> && git pull
```

#### CHANGELOG 업데이트 방법

step 1에서 조회한 커밋 목록을 사용한다.

1. 커밋 메시지의 type 접두사로 변경 분류:
   - `feat:` → `### Added`
   - `fix:` → `### Fixed`
   - `refactor:` / `chore:` → `### Changed`
   - `docs:` → `### Changed`
   - `BREAKING CHANGE` 포함 → MAJOR bump 필요 명시

2. `CHANGELOG.md`의 `## [Unreleased]` 섹션 아래에 해당 항목 추가.
   - CHANGELOG.md가 없으면 `changelog_guideline.md` 형식으로 신규 생성.
   - 이미 같은 내용이 있으면 중복 추가 금지.

3. base 브랜치에서 커밋 후 push:
```bash
git add CHANGELOG.md
git commit -m "chore: update changelog for #<number>"
git push
```

### 6. 머지된 브랜치 · 워크트리 정리

```bash
bash scripts/clean/cleanup-merged.sh
```

- backend repo 대상
- 머지된 `feat|fix|docs|...` 패턴 원격 브랜치 삭제 + 대응 워크트리 제거
- 문제 없이 완료되면 결과 요약에 포함

### 7. 결과 요약

처리한 PR 목록과 액션(코멘트 응답 / 리베이스 / 자동 리뷰+승인 / 머지 / 브랜치 정리 / 스킵)을 출력.
