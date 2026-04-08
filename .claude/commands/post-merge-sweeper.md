# /post-merge-sweeper — Post-Merge Comment Sweeper

최근 머지된 PR에서 미처리 리뷰 코멘트를 탐색하고, 필요하면 후속 fix PR을 생성한다.

## 실행 순서

### 1. 최근 24시간 내 머지된 PR 수집 + 미처리 코멘트 탐색

```bash
bash scripts/clean/merged-recent.sh 24
```

출력 형식 (탭 구분): `REPO  NUMBER  TITLE  MERGED_AT  UNRESOLVED  TOTAL_INLINE`

- `UNRESOLVED=0`: 미처리 코멘트 없음 — 스킵
- `UNRESOLVED > 0`: Step 2로 진행
- 출력이 없으면 처리할 PR 없음 → 종료

### 2. 미처리 코멘트 상세 탐색

`UNRESOLVED > 0`인 PR에 대해:

```bash
bash scripts/clean/pr-comments-filter.sh <repo> <number>
```

`UNRESOLVED` 라인에서 파일·경로·내용 확인.

### 3. 유효한 이슈 분류

- **false positive**: 해당 PR 코멘트에 "Addressed: false positive — [이유]" 답변 후 종료.
- **valid fix**: 코드 수정 필요. 수정 후 새 브랜치(`fix/sweep-{date}`)에서 PR 생성.

### 4. 결과 요약

처리한 PR 수, 발견된 미처리 코멘트 수, 생성된 fix PR 수를 출력.
