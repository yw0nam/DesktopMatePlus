# GitHub Issues Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TODO.md + KNOWN_ISSUES.md를 GitHub Issues로 전면 이전하고, 관련 스크립트/문서 참조를 모두 전환한다.

**Architecture:** GitHub API(`gh` CLI)로 labels/milestones 생성 후 이슈를 생성한다. 기존 파일 참조를 가진 스크립트와 문서를 `gh issue list` 기반으로 전환하고, TODO.md와 KNOWN_ISSUES.md를 삭제한다.

**Tech Stack:** GitHub CLI (`gh`), Bash, Markdown

---

### Task 1: GitHub Labels 생성

**Files:**
- None (GitHub API 호출만)

- [ ] **Step 1: 기존 불필요 기본 라벨 삭제**

```bash
for label in "good first issue" "help wanted" "invalid" "question" "duplicate" "wontfix" "bug" "enhancement" "documentation"; do
  gh api repos/yw0nam/DesktopMatePlus/labels/"$(echo "$label" | sed 's/ /%20/g')" -X DELETE 2>/dev/null || true
done
```

- [ ] **Step 2: Type labels 생성**

```bash
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="type:feature" -f color="1d76db" -f description="신규 기능, enhancement"
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="type:bug" -f color="d93f0b" -f description="버그, 오작동"
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="type:refactor" -f color="fbca04" -f description="리팩토링, chore"
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="type:docs" -f color="0075ca" -f description="문서 추가/수정"
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="type:tech-debt" -f color="e4e669" -f description="기술 부채, KI 항목"
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="type:idea" -f color="d4c5f9" -f description="아이디어, 검토 필요"
```

- [ ] **Step 3: Severity labels 생성**

```bash
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="severity:low" -f color="c5def5" -f description="미발현 또는 영향 적음"
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="severity:medium" -f color="fbca04" -f description="기능 제한"
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="severity:high" -f color="d93f0b" -f description="긴급"
```

- [ ] **Step 4: Component labels 생성**

```bash
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="component:agent" -f color="0e8a16" -f description="Agent 서비스"
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="component:websocket" -f color="0e8a16" -f description="WebSocket 서비스"
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="component:proactive" -f color="0e8a16" -f description="Proactive 서비스"
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="component:tts" -f color="0e8a16" -f description="TTS 서비스"
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="component:docker" -f color="0e8a16" -f description="Docker/인프라"
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="component:mcp" -f color="0e8a16" -f description="MCP 연동"
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="component:channel" -f color="0e8a16" -f description="Channel (Slack) 서비스"
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="component:memory" -f color="0e8a16" -f description="STM (MongoDB) / LTM (mem0)"
```

- [ ] **Step 5: Status label 생성**

```bash
gh api repos/yw0nam/DesktopMatePlus/labels -X POST -f name="status:wontfix" -f color="ffffff" -f description="수정하지 않기로 결정"
```

- [ ] **Step 6: 검증**

```bash
gh api repos/yw0nam/DesktopMatePlus/labels --jq '.[].name' | sort
```

Expected: 18개 라벨 (`component:*` 8개 + `severity:*` 3개 + `status:wontfix` 1개 + `type:*` 6개)

---

### Task 2: GitHub Milestones 생성

**Files:**
- None (GitHub API 호출만)

- [ ] **Step 1: Milestone 생성**

```bash
gh api repos/yw0nam/DesktopMatePlus/milestones -X POST -f title="HitL" -f description="Human-in-the-Loop Phase 2, 3"
gh api repos/yw0nam/DesktopMatePlus/milestones -X POST -f title="MCP" -f description="MCP code-sandbox 서버 연결"
gh api repos/yw0nam/DesktopMatePlus/milestones -X POST -f title="Future Ideas" -f description="스케줄/리마인더, 감정 트래킹, 중간 에이전트 레이어 등"
```

- [ ] **Step 2: 검증 — milestone 번호 확인**

```bash
gh api repos/yw0nam/DesktopMatePlus/milestones --jq '.[] | "\(.number) \(.title)"'
```

Expected: 3개 milestone. 번호를 기록해둔다 (Task 3에서 사용).

---

### Task 3: TODO.md 마커 정리 + open 항목 → GitHub Issues 생성

**Files:**
- Modify: `TODO.md` (Proactive Phase 1-3 마커 갱신)

> Task 2에서 확인한 milestone 번호를 `HITL_MS`, `MCP_MS`, `IDEAS_MS` 변수에 대입하여 사용.

- [ ] **Step 0: Proactive Phase 1-3 마커 갱신**

PR #38에서 이미 완료됐으나 TODO.md 마커가 `cc:TODO`로 남아있음. 삭제 전에 정리:

```bash
# TODO.md에서 Proactive Phase 1-3의 cc:TODO를 cc:DONE으로 변경
sed -i 's/Phase 1: Idle timer.*cc:TODO/Phase 1: Idle timer 트리거 — 일정 시간 무입력 시 자동 발화 cc:DONE — PR #38/' TODO.md
sed -i 's/Phase 2: APScheduler.*cc:TODO/Phase 2: APScheduler 기반 시각 트리거 — 특정 시각 인사\/알림 cc:DONE — PR #38/' TODO.md
sed -i 's/Phase 3: 외부 웹훅.*cc:TODO/Phase 3: 외부 웹훅 트리거 — POST \/v1\/proactive\/trigger cc:DONE — PR #38/' TODO.md
git add TODO.md && ALLOW_MASTER=1 git commit -m "chore: mark Proactive Phase 1-3 as cc:DONE (PR #38)"
```

- [ ] **Step 1: Feature issues 생성**

```bash
HITL_MS=<number>   # Task 2에서 확인한 HitL milestone 번호
MCP_MS=<number>    # Task 2에서 확인한 MCP milestone 번호
IDEAS_MS=<number>  # Task 2에서 확인한 Future Ideas milestone 번호

# MCP code-sandbox
gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="MCP code-sandbox 서버 연결 — pydantic/mcp-run-python (Docker 격리)" \
  -f body="기존 TODO.md에서 이전. Docker 격리된 MCP code-sandbox 서버 연결." \
  -f milestone="$MCP_MS" \
  -f 'labels[]=type:feature' -f 'labels[]=component:mcp'

# HitL Phase 2
gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="HitL Phase 2: 도구 카테고리별 선택적 승인 — 위험도 분류 + HitLMiddleware 설정화" \
  -f body="기존 TODO.md에서 이전. 조사 문서: docs/todo/human-in-the-loop.md" \
  -f milestone="$HITL_MS" \
  -f 'labels[]=type:feature' -f 'labels[]=component:agent'

# HitL Phase 3
gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="HitL Phase 3: 인자 편집 후 재실행 — edited_args 지원" \
  -f body="기존 TODO.md에서 이전. 조사 문서: docs/todo/human-in-the-loop.md" \
  -f milestone="$HITL_MS" \
  -f 'labels[]=type:feature' -f 'labels[]=component:agent'
```

- [ ] **Step 2: Idea issues 생성**

```bash
IDEAS_MS=<number>

# 스케줄/리마인더
gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="스케줄/리마인더 시스템 — cron 기반 예약 메시지" \
  -f body="기존 TODO.md에서 이전. 검토 필요 단계." \
  -f milestone="$IDEAS_MS" \
  -f 'labels[]=type:idea'

# 감정 상태 트래킹
gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="감정 상태 트래킹 — 대화 감정 분석 → 캐릭터 반응 조절" \
  -f body="기존 TODO.md에서 이전. 검토 필요 단계." \
  -f milestone="$IDEAS_MS" \
  -f 'labels[]=type:idea'

# 데스크톱 통합 트리거
gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="데스크톱 통합 트리거 — backend는 트리거/데이터 제공, OS 연동은 DH MOD 담당" \
  -f body="기존 TODO.md에서 이전. 검토 필요 단계." \
  -f milestone="$IDEAS_MS" \
  -f 'labels[]=type:idea'

# 중간 에이전트 레이어
gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="중간 에이전트 레이어 — 수 초~수십 초 자율 추론 위임" \
  -f body="$(cat <<'EOF'
기존 TODO.md에서 이전.

Agent 응답 시간 목표: ≤0.5초. code-sandbox 실행이 이 제약을 넘는 태스크가 반복되면
claude code/opencode 같은 코딩 에이전트를 MCP로 연결하여 비동기 위임하는 중간 레이어 검토.
NanoClaw delegation과 역할 경계 정리 필요 (NanoClaw = 무거운 장기 작업, 중간 에이전트 = 수 초~수십 초 자율 추론).
EOF
)" \
  -f milestone="$IDEAS_MS" \
  -f 'labels[]=type:idea'
```

- [ ] **Step 3: 검증**

```bash
gh issue list --repo yw0nam/DesktopMatePlus --state open --json number,title --jq '.[] | "#\(.number) \(.title)"'
```

Expected: 7개 open issues.

---

### Task 4: KNOWN_ISSUES.md open 항목 → GitHub Issues 생성

**Files:**
- None (GitHub API 호출만)

- [ ] **Step 1: Open tech-debt issues 생성**

```bash
HITL_MS=<number>

# KI-16
gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="[KI-16] Docker openai_chat_agent.yml 공유 — ephemeral 볼륨 문제" \
  -f body="$(cat <<'EOF'
기존 KNOWN_ISSUES.md KI-16에서 이전.

`openai_chat_agent.yml`이 Docker/로컬 공유 — `tool_config.builtin.filesystem.root_dir: /tmp/agent-workspace`가 Docker에서 ephemeral (컨테이너 재시작 시 소멸). 현재 `enabled: false`라 미발현.

**해결 방향**: filesystem tool 활성화 PR에서 `openai_chat_agent.docker.yml` 분리 + `docker.yml` 참조 변경 + `docker-compose.yml`에 named volume 추가 + `src/configs/agent/openai_chat_agent.py:27` Pydantic 기본값 수정.
EOF
)" \
  -f 'labels[]=type:tech-debt' -f 'labels[]=severity:low' -f 'labels[]=component:docker'

# KI-22
gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="[KI-22] HitL E2E 테스트 비결정적 — LLM이 safe tool 대신 MCP tool 선택" \
  -f body="$(cat <<'EOF'
기존 KNOWN_ISSUES.md KI-22에서 이전.

`tests/e2e/test_hitl_e2e.py::TestHitLExistingFlowUnchanged::test_safe_tool_no_hitl_request` E2E 테스트가 비결정적. LLM이 의도한 빌트인 `search_memory` 대신 위험 MCP 툴을 선택할 경우 `pytest.skip()` 처리됨.

**단위 테스트 커버리지 충분**: `test_hitl_middleware.py::test_safe_tool_passes_through`, `test_builtin_tool_is_safe`가 결정론적으로 동일 로직 검증.

**해결 방향**: skip 패턴을 LLM 비결정성의 내재적 한계로 수용하거나, MCP 툴 없이 에이전트를 초기화하는 전용 E2E 픽스처를 추가.
EOF
)" \
  -f milestone="$HITL_MS" \
  -f 'labels[]=type:tech-debt' -f 'labels[]=severity:low' -f 'labels[]=component:agent'

# KI-24
gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="[KI-24] IdleWatcher.scan_once() 순차 처리 — trigger 완료까지 blocking" \
  -f body="$(cat <<'EOF'
기존 KNOWN_ISSUES.md KI-24에서 이전.

`IdleWatcher.scan_once()`가 idle connection을 순차 처리 — `trigger_proactive()` 완료까지 다음 connection 처리 차단. 현재 데스크톱 앱 단일 유저라 미발현.

**해결 방향**: `asyncio.create_task`로 trigger를 비동기 dispatch하여 connection 간 blocking 제거.
EOF
)" \
  -f 'labels[]=type:tech-debt' -f 'labels[]=severity:low' -f 'labels[]=component:proactive'

# KI-25
gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="[KI-25] ScheduleManager._on_schedule_fire() 순차 broadcast" \
  -f body="$(cat <<'EOF'
기존 KNOWN_ISSUES.md KI-25에서 이전.

`ScheduleManager._on_schedule_fire()`가 활성 connection에 순차 broadcast — KI-24와 동일 원인.

**해결 방향**: `asyncio.gather`로 동시 broadcast.
EOF
)" \
  -f 'labels[]=type:tech-debt' -f 'labels[]=severity:low' -f 'labels[]=component:proactive'

# KI-26
gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="[KI-26] CLAUDE.md 미들웨어 순서 stale — HitL 미기재 + before_model 순서 오류" \
  -f body="$(cat <<'EOF'
기존 KNOWN_ISSUES.md KI-26에서 이전.

`CLAUDE.md` "Agent Middleware Chain" 섹션의 미들웨어 순서가 구버전 — `ToolGate → Delegate → LTM → Profile → Summary → TaskStatus`로 기재되어 있으나 실제 코드(`openai_chat_agent.py:171`)는 `ToolGate → HitL → Delegate → Profile → Summary → LTM → TaskStatus`.

**해결 방향**: `CLAUDE.md` ARCHITECTURAL PATTERNS 섹션 해당 라인 수정.
EOF
)" \
  -f 'labels[]=type:tech-debt' -f 'labels[]=severity:low' -f 'labels[]=component:agent'
```

- [ ] **Step 2: 검증**

```bash
gh issue list --repo yw0nam/DesktopMatePlus --label type:tech-debt --json number,title --jq '.[] | "#\(.number) \(.title)"'
```

Expected: 5개 tech-debt issues.

---

### Task 5: Won't Fix 항목 → closed 이슈로 이전

**Files:**
- None (GitHub API 호출만)

- [ ] **Step 1: Won't Fix issues 생성 + 즉시 close**

```bash
# KI-2
ISSUE_NUM=$(gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="[KI-2] 6개 서비스 파일 200줄 초과" \
  -f body="Won't Fix: YAGNI, 억지 분리 시 가독성 저하. KNOWN_ISSUES.md에서 이전." \
  -f 'labels[]=type:tech-debt' -f 'labels[]=status:wontfix' \
  --jq '.number')
gh api repos/yw0nam/DesktopMatePlus/issues/"$ISSUE_NUM" -X PATCH -f state="closed" -f state_reason="not_planned"

# KI-3
ISSUE_NUM=$(gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="[KI-3] validate_token() 항상 valid_token 반환" \
  -f body="Won't Fix: 개인 시스템이므로 YAGNI. KNOWN_ISSUES.md에서 이전." \
  -f 'labels[]=type:tech-debt' -f 'labels[]=status:wontfix' \
  --jq '.number')
gh api repos/yw0nam/DesktopMatePlus/issues/"$ISSUE_NUM" -X PATCH -f state="closed" -f state_reason="not_planned"

# KI-7
ISSUE_NUM=$(gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="[KI-7] _severity() 문자열 키워드 매칭" \
  -f body="Won't Fix: 현재 정상 동작. KNOWN_ISSUES.md에서 이전." \
  -f 'labels[]=type:tech-debt' -f 'labels[]=status:wontfix' \
  --jq '.number')
gh api repos/yw0nam/DesktopMatePlus/issues/"$ISSUE_NUM" -X PATCH -f state="closed" -f state_reason="not_planned"

# KI-11
ISSUE_NUM=$(gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="[KI-11] RestrictedShellTool cwd 제한 없음" \
  -f body="Won't Fix: Docker 샌드박스로 충분. KNOWN_ISSUES.md에서 이전." \
  -f 'labels[]=type:tech-debt' -f 'labels[]=status:wontfix' \
  --jq '.number')
gh api repos/yw0nam/DesktopMatePlus/issues/"$ISSUE_NUM" -X PATCH -f state="closed" -f state_reason="not_planned"

# KI-21
ISSUE_NUM=$(gh api repos/yw0nam/DesktopMatePlus/issues -X POST \
  -f title="[KI-21] scripts/run.sh YAML 경로 참조 우려" \
  -f body="Won't Fix: 실제 미발현 확인. KNOWN_ISSUES.md에서 이전." \
  -f 'labels[]=type:tech-debt' -f 'labels[]=status:wontfix' \
  --jq '.number')
gh api repos/yw0nam/DesktopMatePlus/issues/"$ISSUE_NUM" -X PATCH -f state="closed" -f state_reason="not_planned"
```

- [ ] **Step 2: 검증**

```bash
gh issue list --repo yw0nam/DesktopMatePlus --state closed --label status:wontfix --json number,title --jq '.[] | "#\(.number) \(.title)"'
```

Expected: 5개 closed wontfix issues.

- [ ] **Step 3: 전체 이슈 현황 확인**

```bash
echo "=== Open ===" && gh issue list --repo yw0nam/DesktopMatePlus --state open --json number,title,labels --jq '.[] | "#\(.number) [\(.labels | map(.name) | join(", "))] \(.title)"'
echo "=== Closed ===" && gh issue list --repo yw0nam/DesktopMatePlus --state closed --json number,title --jq '.[] | "#\(.number) \(.title)"'
```

Expected: 12 open + 5 closed = 17 total issues.

---

### Task 6: garden.sh GP-6, GP-9, GP-10 수정

**Files:**
- Modify: `scripts/clean/garden.sh:170-291` (GP-6, GP-9, GP-10 함수)
- Modify: `scripts/clean/garden.sh:416-491` (auto-fix phase)

- [ ] **Step 1: GP-6 수정 — `gh` CLI 기반으로 전환**

`verify_gp6()` 함수 (line 170-187)를 아래로 교체:

```bash
verify_gp6() {
  # Task Tracking via GitHub Issues — Minor
  local repo="$1"
  if [[ "$repo" == "backend" ]]; then
    if ! command -v gh &>/dev/null || ! gh auth status &>/dev/null 2>&1; then
      add_result GP-6 backend Minor SKIP "gh CLI not available or not authenticated"
      return
    fi
    local open_count
    open_count="$(gh issue list --repo yw0nam/DesktopMatePlus --state open --json number --jq 'length' 2>/dev/null)" || open_count=0
    add_result GP-6 backend Minor PASS "${open_count} open issue(s) tracked on GitHub"
  fi
}
```

- [ ] **Step 2: GP-9 수정 — TODO.md 파싱 제거**

`verify_gp9()` 함수 (line 218-238)를 아래로 교체:

```bash
verify_gp9() {
  # Archive Freshness — WARN (legacy: was TODO.md spec-ref check)
  # Now tracked via GitHub Issues — closed issues = archived
  local repo="$1"
  if [[ "$repo" != "backend" ]]; then return; fi
  add_result GP-9 backend WARN PASS "tracked via GitHub Issues (closed = archived)"
}
```

- [ ] **Step 3: GP-10 수정 — TODO.md auto-archive 제거**

`verify_gp10()` 함수 (line 240-292)를 아래로 교체:

```bash
verify_gp10() {
  # Auto-Archive — WARN (legacy: was TODO.md phase collapse)
  # Now tracked via GitHub Issues — close issues to archive
  local repo="$1"
  if [[ "$repo" != "backend" ]]; then return; fi
  add_result GP-10 backend WARN PASS "tracked via GitHub Issues (close to archive)"
}
```

- [ ] **Step 4: auto-fix phase에서 archive_completed_phases 제거**

`archive_completed_phases()` 함수 (line 416-491)와 GP-10 auto-fix 호출 (line 497-505)을 삭제한다.

- [ ] **Step 5: 검증**

```bash
bash scripts/clean/garden.sh --gp GP-6 --dry-run
bash scripts/clean/garden.sh --gp GP-9 --dry-run
bash scripts/clean/garden.sh --gp GP-10 --dry-run
```

Expected: 3개 모두 PASS 또는 SKIP.

- [ ] **Step 6: Commit**

```bash
git add scripts/clean/garden.sh
git commit -m "chore: migrate garden.sh GP-6/9/10 from TODO.md to GitHub Issues"
```

---

### Task 7: check_docs.sh 수정

**Files:**
- Modify: `scripts/clean/check_docs.sh:3,8,107-129`

- [ ] **Step 1: Check 3 (Spec coverage) 수정**

`PLANS_FILE` 변수 (line 8)를 삭제하고, Check 3 섹션 (line 107-129)을 아래로 교체:

Line 3 주석:
```bash
# check_docs.sh — Documentation freshness linter
# Checks dead links and doc line limits.
```

Line 8 삭제:
```bash
# PLANS_FILE="$WORKSPACE_ROOT/TODO.md"  ← 이 줄 삭제
```

Check 3 섹션 (line 107-129) 교체:
```bash
# ── Check 3: Specs directory exists ──────────────────────────────
echo ""
echo "--- Spec coverage check ---"

SPECS_DIR="$DOCS_DIR/superpowers/specs"
if [[ -d "$SPECS_DIR" ]]; then
  spec_count=$(find "$SPECS_DIR" -name '*.md' -type f 2>/dev/null | wc -l)
  echo "[PASS] $spec_count spec(s) found in superpowers/specs/"
else
  echo "[PASS] No specs directory (skipped)"
fi
```

- [ ] **Step 2: 검증**

```bash
bash scripts/clean/check_docs.sh
```

Expected: Dead link check PASS, Doc line limit check, Spec coverage PASS. 전체 exit 0.

- [ ] **Step 3: Commit**

```bash
git add scripts/clean/check_docs.sh
git commit -m "chore: remove TODO.md dependency from check_docs.sh"
```

---

### Task 8: quality-report.md 수정

**Files:**
- Modify: `.claude/commands/quality-report.md`

- [ ] **Step 1: Step 4 (Stale TODO Detection) 수정**

Step 4 (line 51-58) 교체:

```markdown
### 4. Stale Issue Detection

\`\`\`bash
DATE=$(date +%Y-%m-%d); WORKTREE_PATH="worktrees/quality-${DATE}"
cd "$WORKTREE_PATH" && gh issue list --repo yw0nam/DesktopMatePlus --state open --json number,title,createdAt --jq '.[] | "#\(.number) \(.title) (created: \(.createdAt[:10]))"'
\`\`\`

14일 이상 open 상태 이슈 탐지.
```

- [ ] **Step 2: Step 5 (TODO.md Health Check) → GitHub Issues Health로 수정**

Step 5 (line 60-75) 교체:

```markdown
### 5. GitHub Issues Health Check

\`\`\`bash
DATE=$(date +%Y-%m-%d); WORKTREE_PATH="worktrees/quality-${DATE}"
cd "$WORKTREE_PATH"
gh issue list --repo yw0nam/DesktopMatePlus --state open --json number --jq 'length'
gh issue list --repo yw0nam/DesktopMatePlus --state open --label type:tech-debt --json number --jq 'length'
\`\`\`

플래그 대상:
1. **Open issue 총 수** — 30개 초과 시 플래그
2. **Tech-debt 비율** — tech-debt이 전체의 50% 초과 시 플래그

리포트의 `## GitHub Issues Health` 섹션에 기록. 자동 수정 금지.
```

- [ ] **Step 3: Step 7 (Archive Bloat Detection) 수정**

Step 7 (line 87-94) 교체:

```markdown
### 7. Closed Issues Check

\`\`\`bash
DATE=$(date +%Y-%m-%d); WORKTREE_PATH="worktrees/quality-${DATE}"
cd "$WORKTREE_PATH"
gh issue list --repo yw0nam/DesktopMatePlus --state closed --json number --jq 'length'
\`\`\`

Closed 이슈 수 기록. 별도 조치 불필요.
```

- [ ] **Step 4: Report template 수정**

Step 8의 리포트 템플릿 (line 98-132)에서 아래 항목들을 교체:

- `## Stale TODO (2w+)` → `## Stale Issues (2w+)`
- `[Tasks in cc:TODO state for 14+ days]` → `[Issues open for 14+ days]`
- `## TODO.md Health` → `## GitHub Issues Health`
- `## Archive Bloat` → `## Closed Issues`

교체 후 내용:

```markdown
## Stale Issues (2w+)
[Issues open for 14+ days]
- #N: description (created: YYYY-MM-DD)

## GitHub Issues Health
- Open issues: N (threshold: 30)
- Tech-debt ratio: N/M (threshold: 50%)

## Closed Issues
- Closed issues: N
```

- [ ] **Step 5: 제약 사항 섹션 수정**

Line 182의 제약 사항을 수정:

Before:
```markdown
- **garden.sh auto-fix** (GP-10 archive)만 허용. 그 외 소스 수정 불가
```

After:
```markdown
- **garden.sh auto-fix** (ruff 등 Minor 위반)만 허용. 그 외 소스 수정 불가
```

- [ ] **Step 6: Commit**

```bash
git add .claude/commands/quality-report.md
git commit -m "chore: migrate quality-report from TODO.md to GitHub Issues"
```

---

### Task 9: GOLDEN_PRINCIPLES.md 수정

**Files:**
- Modify: `docs/GOLDEN_PRINCIPLES.md:79-136`

- [ ] **Step 1: GP-6 규칙 텍스트 수정**

GP-6 섹션 (line 79-87) 교체:

```markdown
## GP-6: Task Tracking via GitHub Issues

**Rule**: Every task must exist as a GitHub Issue before implementation starts.
Issues use label taxonomy (`type:*`, `severity:*`, `component:*`) for classification.

**Verify**: `gh issue list --repo yw0nam/DesktopMatePlus --state open`

**Severity**: Minor.
```

- [ ] **Step 2: GP-9 규칙 텍스트 수정**

GP-9 섹션 (line 111-121) 교체:

```markdown
## GP-9: Archive Freshness

**Rule**: Completed work must be reflected by closing the corresponding GitHub Issue. When a feature is merged, its issue should be closed (automatically via `fixes #N` or manually).

**Verify**: `gh issue list --repo yw0nam/DesktopMatePlus --state open` — no stale issues for merged features.

**Severity**: WARN — garden.sh reports only.
```

- [ ] **Step 3: GP-10 규칙 텍스트 수정**

GP-10 섹션 (line 125-136) 교체:

```markdown
## GP-10: Issue Hygiene

**Rule**: Open issues should be actionable. Stale issues (30+ days without activity) should be reviewed and either updated, closed, or labeled with a reason for keeping open.

**Verify**: `gh issue list --repo yw0nam/DesktopMatePlus --state open --json number,updatedAt`

**Severity**: WARN — garden.sh reports only; no merge block.
```

- [ ] **Step 4: Commit**

```bash
git add docs/GOLDEN_PRINCIPLES.md
git commit -m "chore: migrate GP-6/9/10 from TODO.md to GitHub Issues"
```

---

### Task 10: CLAUDE.md, docs/CLAUDE.md, CHECKLIST.md, scripts-reference.md 수정

**Files:**
- Modify: `CLAUDE.md:180,184,187`
- Modify: `docs/CLAUDE.md:7` (known_issues row)
- Modify: `CHECKLIST.md:53`
- Modify: `docs/scripts-reference.md:45`

- [ ] **Step 1: CLAUDE.md Task Tracking 섹션 수정**

Line 180 교체:

```markdown
## Task Tracking

- Tasks and known issues tracked via [GitHub Issues](https://github.com/yw0nam/DesktopMatePlus/issues) with label taxonomy (`type:*`, `severity:*`, `component:*`).
```

Appendix에서 TODO/KI 링크 수정 (line 184, 187):

```markdown
- [GitHub Issues](https://github.com/yw0nam/DesktopMatePlus/issues): Task and tech-debt tracking.
```

`[TODO](./TODO.md)` 줄과 `[Known Issues](./docs/known_issues/KNOWN_ISSUES.md)` 줄을 위의 한 줄로 교체.

- [ ] **Step 2: docs/CLAUDE.md Directory Map 수정**

`known_issues/` 행 (line 7) 삭제:

```
| `known_issues/` | 기술 부채 추적 (KNOWN_ISSUES.md) |  ← 삭제
```

- [ ] **Step 3: CHECKLIST.md 수정**

Line 53 교체:

```markdown
- 신규 태스크: GitHub Issue에 `make e2e PASSED` 체크 필수.
```

- [ ] **Step 4: docs/scripts-reference.md 수정**

Line 45 교체:

```markdown
- GitHub Issues의 open/closed 상태 기반 검증 (GP-9/10)
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/CLAUDE.md CHECKLIST.md docs/scripts-reference.md
git commit -m "chore: update doc references from TODO.md/KNOWN_ISSUES.md to GitHub Issues"
```

---

### Task 11: TODO.md + KNOWN_ISSUES.md 삭제

**Files:**
- Delete: `TODO.md`
- Delete: `docs/known_issues/KNOWN_ISSUES.md`
- Delete: `docs/known_issues/` (directory)

- [ ] **Step 1: 파일 및 디렉토리 삭제**

```bash
rm TODO.md
rm -rf docs/known_issues/
```

- [ ] **Step 2: 검증 — dead link check**

```bash
bash scripts/clean/check_docs.sh
```

Expected: exit 0 (TODO.md/KNOWN_ISSUES.md 링크가 이미 모두 교체된 상태).

- [ ] **Step 3: 검증 — garden.sh**

```bash
bash scripts/clean/garden.sh --dry-run
```

Expected: GP-6 PASS 또는 SKIP, GP-9 PASS, GP-10 PASS. FAIL 없음.

- [ ] **Step 4: Commit**

```bash
git add -A TODO.md docs/known_issues/
git commit -m "chore: remove TODO.md and KNOWN_ISSUES.md — migrated to GitHub Issues"
```

---

### Task 12: 최종 검증 + CHANGELOG 업데이트

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: 전체 lint 검증**

```bash
make lint
```

Expected: exit 0.

- [ ] **Step 2: GitHub Issues 최종 확인**

```bash
echo "=== Open Issues ===" && gh issue list --repo yw0nam/DesktopMatePlus --state open --json number,title,labels --jq '.[] | "#\(.number) [\(.labels | map(.name) | join(", "))] \(.title)"'
echo "" && echo "=== Closed Issues ===" && gh issue list --repo yw0nam/DesktopMatePlus --state closed --json number,title --jq '.[] | "#\(.number) \(.title)"'
echo "" && echo "=== Milestones ===" && gh api repos/yw0nam/DesktopMatePlus/milestones --jq '.[] | "\(.title): \(.open_issues) open, \(.closed_issues) closed"'
```

Expected: 12 open + 5 closed issues, 3 milestones.

- [ ] **Step 3: CHANGELOG 업데이트**

`CHANGELOG.md`의 `## [Unreleased]` 섹션의 `### Changed` 아래에 추가:

```markdown
- migrate TODO.md + KNOWN_ISSUES.md to GitHub Issues — label taxonomy, milestones, script/doc references updated
```

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "chore: update changelog for GitHub Issues migration"
```
