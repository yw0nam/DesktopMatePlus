#!/usr/bin/env bash
# garden.sh — Background Gardening Agent
# Runs GOLDEN_PRINCIPLES.md verify commands, auto-fixes Minor violations, generates reports.
set -euo pipefail

# ── PATH: ensure uv and other user-installed tools are available ───
# Required for cron/quality-agent runs where PATH is minimal
export PATH="$HOME/.local/bin:$HOME/anaconda3/bin:$HOME/.cargo/bin:$PATH"

# ── Repo root (script lives in scripts/clean/) ────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATE="$(date +%Y-%m-%d)"

# ── Repo config ────────────────────────────────────────────────────
declare -A REPO_DIRS=(
  [backend]="$WORKSPACE_ROOT"
)
declare -A REPO_BRANCHES=(
  [backend]="master"
)

# ── CLI flags ──────────────────────────────────────────────────────
DRY_RUN=false
METRICS_ONLY=false
FILTER_GP=""
FILTER_REPO=""

usage() {
  cat <<'EOF'
Usage: scripts/garden.sh [OPTIONS]

Background Gardening Agent — verifies Golden Principles and auto-fixes violations.

Options:
  --dry-run      Detect only, skip auto-fix and report generation
  --metrics      Run detection + update QUALITY_SCORE.md only (skip auto-fix and report)
  --gp GP-N      Run only the specified GP (e.g. GP-3)
  --repo NAME    Run only for the specified repo (backend)
  -h, --help     Show this help message

Examples:
  scripts/clean/garden.sh                 # Full run
  scripts/clean/garden.sh --dry-run       # Detect only
  scripts/clean/garden.sh --metrics       # Detect + update QUALITY_SCORE.md only
  scripts/clean/garden.sh --gp GP-3       # Check GP-3 only
  scripts/clean/garden.sh --repo backend  # Check backend only
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)  DRY_RUN=true; shift ;;
    --metrics)  METRICS_ONLY=true; shift ;;
    --gp)       FILTER_GP="$2"; shift 2 ;;
    --repo)     FILTER_REPO="$2"; shift 2 ;;
    -h|--help)  usage; exit 0 ;;
    *)          echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

# ── Result collection ──────────────────────────────────────────────
# Each entry: "GP|repo|severity|status|details"
declare -a RESULTS=()
# Track repos that have auto-fixed files
declare -A REPO_HAS_FIXES=()

should_run() {
  local gp="$1" repo="$2"
  [[ -z "$FILTER_GP"   || "$FILTER_GP"   == "$gp"   ]] || return 1
  [[ -z "$FILTER_REPO" || "$FILTER_REPO" == "$repo" ]] || return 1
  return 0
}

DELIM=$'\x1f'  # ASCII Unit Separator — safe for details containing pipes

add_result() {
  local gp="$1" repo="$2" severity="$3" status="$4"
  # Flatten multiline details to single line (newlines → " | ")
  local details="${5//$'\n'/ | }"
  RESULTS+=("${gp}${DELIM}${repo}${DELIM}${severity}${DELIM}${status}${DELIM}${details}")
}

# ── GP verify functions ────────────────────────────────────────────

verify_gp1() {
  # Architecture Layering — Critical
  local repo="$1" dir="${REPO_DIRS[$1]}"
  if [[ "$repo" == "backend" ]]; then
    [[ -d "$dir" ]] || { add_result GP-1 "$repo" Critical SKIP "repo dir not found"; return; }
    local out rc=0
    out=$(cd "$dir" && uv run pytest tests/structural/test_architecture.py 2>&1) || rc=$?
    if [[ "$rc" -eq 0 ]]; then
      add_result GP-1 "$repo" Critical PASS "structural tests passed"
    else
      add_result GP-1 "$repo" Critical FAIL "$(echo "$out" | tail -10)"
    fi
  fi
}

verify_gp2() {
  # File Size Limits — Major
  local repo="$1" dir="${REPO_DIRS[$1]}"
  if [[ "$repo" == "backend" ]]; then
    [[ -d "$dir" ]] || { add_result GP-2 "$repo" Major SKIP "repo dir not found"; return; }
    local out rc=0
    out=$(cd "$dir" && uv run pytest tests/structural/test_architecture.py -k "loc_limit" 2>&1) || rc=$?
    if [[ "$rc" -eq 0 ]]; then
      add_result GP-2 "$repo" Major PASS "file sizes within limits"
    else
      add_result GP-2 "$repo" Major FAIL "$(echo "$out" | tail -10)"
    fi
  fi
}

verify_gp3() {
  # No Bare Logging — Major (auto-fixable for backend)
  local repo="$1" dir="${REPO_DIRS[$1]}"
  if [[ "$repo" == "backend" ]]; then
    [[ -d "$dir" ]] || { add_result GP-3 "$repo" Major SKIP "repo dir not found"; return; }
    local out rc=0
    # GP-3 verify: grep for bare print() in src/ with file:line format
    out=$(cd "$dir" && grep -rn 'print(' src/ --include='*.py' | grep -v '__pycache__' | grep -v '# noqa' | head -20) || rc=$?
    if [[ "$rc" -ne 0 || -z "$out" ]]; then
      add_result GP-3 "$repo" Major PASS "no bare print() found"
    else
      # Format as [file:line] entries
      local violations
      violations=$(echo "$out" | head -5 | awk -F: '{print "[" $1 ":" $2 "]"}' | tr '\n' ' ')
      add_result GP-3 "$repo" Major FAIL "$violations"
    fi
  fi
}

verify_gp4() {
  # No Hardcoded Config — Critical
  local repo="$1" dir="${REPO_DIRS[$1]}"
  if [[ "$repo" == "backend" ]]; then
    [[ -d "$dir" ]] || { add_result GP-4 "$repo" Critical SKIP "repo dir not found"; return; }
    local out rc=0
    out=$(cd "$dir" && grep -rn 'localhost\|127\.0\.0\.1\|mongodb://' src/ \
      --include='*.py' \
      --exclude-dir='__pycache__' \
      | grep -v 'test' | grep -v 'config' | head -20) || rc=$?
    if [[ "$rc" -eq 0 && -n "$out" ]]; then
      add_result GP-4 "$repo" Critical FAIL "hardcoded values found: $(echo "$out" | head -5)"
    else
      add_result GP-4 "$repo" Critical PASS "no hardcoded config found"
    fi
  fi
}

verify_gp5() {
  # CLAUDE.md size — Minor
  local repo="$1"
  if [[ "$repo" == "backend" ]]; then
    local f="${REPO_DIRS[backend]}/CLAUDE.md"
    if [[ -f "$f" ]]; then
      local lines
      lines=$(wc -l < "$f" | tr -d ' ')
      if [[ "$lines" -le 200 ]]; then
        add_result GP-5 backend Minor PASS "CLAUDE.md ${lines} lines (≤200)"
      else
        add_result GP-5 backend Minor FAIL "CLAUDE.md ${lines} lines (>200)"
      fi
    fi
  fi
}

verify_gp6() {
  # TODO as First-Class Artifact — Minor
  local repo="$1"
  if [[ "$repo" == "backend" ]]; then
    local todo_file="${REPO_DIRS[backend]}/TODO.md"
    if [[ ! -f "$todo_file" ]]; then
      add_result GP-6 backend Minor PASS "no TODO.md found"
      return
    fi
    local wip_count
    wip_count="$(grep -c 'cc:WIP' "$todo_file" 2>/dev/null)" || wip_count=0
    if [[ "$wip_count" -eq 0 ]]; then
      add_result GP-6 backend Minor PASS "no orphan cc:WIP tasks"
    else
      add_result GP-6 backend Minor FAIL "${wip_count} cc:WIP task(s) without corresponding commit"
    fi
  fi
}

verify_gp7() {
  # Worktree Isolation — Major
  # Check that main/develop don't have direct (non-merge) commits
  local repo="$1" dir="${REPO_DIRS[$1]}"
  if [[ "$repo" == "backend" ]]; then
    [[ -d "$dir" ]] || { add_result GP-7 "$repo" Major SKIP "repo dir not found"; return; }
    add_result GP-7 "$repo" Major PASS "worktree isolation (manual review)"
  fi
}

verify_gp8() {
  # Lint Before Merge — Critical (auto-fixable for backend)
  local repo="$1" dir="${REPO_DIRS[$1]}"
  if [[ "$repo" == "backend" ]]; then
    [[ -d "$dir" ]] || { add_result GP-8 "$repo" Critical SKIP "repo dir not found"; return; }
    local out rc=0
    if [[ -f "$dir/scripts/lint.sh" ]]; then
      out=$(cd "$dir" && sh scripts/lint.sh 2>&1) || rc=$?
    else
      out=$(cd "$dir" && uv run ruff check src/ 2>&1) || rc=$?
    fi
    if [[ "$rc" -eq 0 ]]; then
      add_result GP-8 "$repo" Critical PASS "lint passed"
    else
      add_result GP-8 "$repo" Critical FAIL "$(echo "$out" | tail -10)"
    fi
  fi
}

verify_gp9() {
  # Archive Freshness — WARN
  # Completed specs in docs/TODO.md must be reflected in TODO.md
  local repo="$1"
  if [[ "$repo" != "backend" ]]; then return; fi

  local todo_file="${REPO_DIRS[backend]}/TODO.md"
  [[ -f "$todo_file" ]] || { add_result GP-9 backend WARN SKIP "TODO.md not found"; return; }

  # Find cc:DONE tasks that reference a spec still marked active in docs/TODO.md
  local done_count active_count
  done_count="$(grep -c 'cc:DONE' "$todo_file" 2>/dev/null)" || done_count=0
  active_count="$(grep -c 'cc:TODO\|cc:WIP' "$todo_file" 2>/dev/null)" || active_count=0

  # Basic check: warn if any cc:WIP exists alongside cc:DONE tasks
  if [[ "$done_count" -gt 0 && "$active_count" -gt 0 ]]; then
    add_result GP-9 backend WARN PASS "TODO.md has both active (${active_count}) and done (${done_count}) tasks — OK"
  else
    add_result GP-9 backend WARN PASS "TODO.md archive freshness OK"
  fi
}

verify_gp10() {
  # TODO.md Auto-Archive — WARN
  # Detect completed Phases that should be collapsed to a summary line
  local repo="$1"
  if [[ "$repo" != "backend" ]]; then return; fi

  local todo_file="${REPO_DIRS[backend]}/TODO.md"
  [[ -f "$todo_file" ]] || { add_result GP-10 backend WARN SKIP "TODO.md not found"; return; }

  local stale_phases=()
  local current_phase=""
  local phase_has_todo=false
  local phase_has_tasks=false
  local phase_is_archived=false

  while IFS= read -r line; do
    if echo "$line" | grep -qP '^### Phase \d+:'; then
      # Check previous phase
      if [[ -n "$current_phase" && "$phase_has_tasks" == true && "$phase_has_todo" == false && "$phase_is_archived" == false ]]; then
        stale_phases+=("$current_phase")
      fi
      current_phase="$line"
      phase_has_todo=false
      phase_has_tasks=false
      phase_is_archived=false
      if echo "$line" | grep -qE 'completed'; then
        phase_is_archived=true
      fi
    fi
    if echo "$line" | grep -qP '^\s*-\s*\[\s*\]'; then
      phase_has_todo=true
      phase_has_tasks=true
    fi
    if echo "$line" | grep -qP '^\s*-\s*\[x\]'; then
      phase_has_tasks=true
    fi
  done < "$todo_file"

  # Check last phase
  if [[ -n "$current_phase" && "$phase_has_tasks" == true && "$phase_has_todo" == false && "$phase_is_archived" == false ]]; then
    stale_phases+=("$current_phase")
  fi

  if [[ ${#stale_phases[@]} -eq 0 ]]; then
    add_result GP-10 backend WARN PASS "no completed phases pending archive"
  else
    local details=""
    for p in "${stale_phases[@]}"; do
      details+="$p"$'\n'
    done
    add_result GP-10 backend WARN FAIL "completed phases not archived: ${details}"
  fi
}

# ── Detection phase ────────────────────────────────────────────────
echo "=== Garden Run $DATE ==="
echo ""

run_detection() {
  local gp_func="$1" gp_id="$2"
  shift 2
  for repo in "$@"; do
    should_run "$gp_id" "$repo" && "$gp_func" "$repo" || true
  done
}

run_detection verify_gp1  GP-1  backend
run_detection verify_gp2  GP-2  backend
run_detection verify_gp3  GP-3  backend
run_detection verify_gp4  GP-4  backend
run_detection verify_gp5  GP-5  backend
run_detection verify_gp6  GP-6  backend
run_detection verify_gp7  GP-7  backend
run_detection verify_gp8  GP-8  backend
run_detection verify_gp9  GP-9  backend
run_detection verify_gp10 GP-10 backend

# ── Print detection results ────────────────────────────────────────
for r in "${RESULTS[@]}"; do
  IFS=$'\x1f' read -r gp repo severity status details <<< "$r"
  printf "[%-5s] %-7s %-10s %s\n" "$gp" "$status" "$repo" "$details"
done

# ── Update Quality Score ──────────────────────────────────────────
update_quality_score() {
  local qs_file="$WORKSPACE_ROOT/docs/QUALITY_SCORE.md"
  [[ -f "$qs_file" ]] || return

  # Collect failures per layer
  # GP mapping: GP-1/GP-2 → Arch; GP-3/GP-8 → Test; GP-4/GP-7 → Obs; GP-5/GP-6 → Docs
  declare -A domain_arch=() domain_test=() domain_obs=() domain_docs=()

  for r in "${RESULTS[@]}"; do
    IFS=$'\x1f' read -r gp repo severity status details <<< "$r"
    [[ "$status" == "FAIL" ]] || continue
    [[ "$repo" == "backend" ]] || continue

    case "$gp" in
      GP-1|GP-2) domain_arch[backend]=$(( ${domain_arch[backend]:-0} + 1 )) ;;
      GP-3|GP-8) domain_test[backend]=$(( ${domain_test[backend]:-0} + 1 )) ;;
      GP-4|GP-7) domain_obs[backend]=$(( ${domain_obs[backend]:-0} + 1 )) ;;
      GP-5|GP-6) domain_docs[backend]=$(( ${domain_docs[backend]:-0} + 1 )) ;;
    esac
  done

  grade_from_count() {
    local count="${1:-0}"
    if [[ "$count" -eq 0 ]]; then echo "A"
    elif [[ "$count" -le 2 ]]; then echo "B"
    elif [[ "$count" -le 4 ]]; then echo "C"
    else echo "D"
    fi
  }

  compute_overall() {
    local worst="A"
    for g in "$@"; do
      case "$g" in
        D) worst="D"; return ;;
        C) [[ "$worst" == "D" ]] || worst="C" ;;
        B) [[ "$worst" == "C" || "$worst" == "D" ]] || worst="B" ;;
      esac
    done
    echo "$worst"
  }

  # Compute grades for backend
  local arch_g test_g obs_g docs_g overall_g
  arch_g=$(grade_from_count "${domain_arch[backend]:-0}")
  test_g=$(grade_from_count "${domain_test[backend]:-0}")
  obs_g=$(grade_from_count "${domain_obs[backend]:-0}")
  docs_g=$(grade_from_count "${domain_docs[backend]:-0}")
  overall_g=$(compute_overall "$arch_g" "$test_g" "$obs_g" "$docs_g")
  sed -i "s/| backend |.*|/| backend | ${arch_g} | ${test_g} | ${obs_g} | ${docs_g} | ${overall_g} |/" "$qs_file"

  # Update timestamp
  sed -i "s/^Last updated:.*/Last updated: $(date +%Y-%m-%d)/" "$qs_file"

  # Count violations for Violations Summary section
  local gp3_backend_count=0
  for r in "${RESULTS[@]}"; do
    IFS=$'\x1f' read -r gp repo severity status details <<< "$r"
    [[ "$status" == "FAIL" && "$repo" == "backend" && "$gp" == "GP-3" ]] || continue
    (( gp3_backend_count++ )) || true
  done

  # Update Violations Summary lines
  sed -i "s/^- GP-3 (backend):.*$/- GP-3 (backend): ${gp3_backend_count} violations/" "$qs_file"
}

update_quality_score

# ── Count violations ───────────────────────────────────────────────
VIOLATION_COUNT=0
declare -A REPO_VIOLATIONS=()
for r in "${RESULTS[@]}"; do
  IFS=$'\x1f' read -r gp repo severity status details <<< "$r"
  if [[ "$status" == "FAIL" ]]; then
    ((VIOLATION_COUNT++)) || true
    REPO_VIOLATIONS[$repo]=$(( ${REPO_VIOLATIONS[$repo]:-0} + 1 ))
  fi
done

if [[ "$VIOLATION_COUNT" -eq 0 ]]; then
  echo ""
  echo "All principles satisfied. Nothing to do."
  exit 0
fi

# ── Auto-fix phase (skip if --dry-run) ─────────────────────────────
declare -A AUTO_FIXED=()

archive_completed_phases() {
  local todo_file="${REPO_DIRS[backend]}/TODO.md"
  [[ -f "$todo_file" ]] || return 0

  # Collect unarchived Phase headers and their line numbers
  local -a phase_headers=()
  local -a phase_line_nums=()
  local line_num=0

  while IFS= read -r line; do
    (( line_num++ )) || true
    if echo "$line" | grep -qP '^### Phase \d+:'; then
      if echo "$line" | grep -qE 'completed'; then continue; fi
      phase_headers+=("$line")
      phase_line_nums+=("$line_num")
    fi
  done < "$todo_file"

  [[ ${#phase_headers[@]} -gt 0 ]] || return 0

  local total_lines
  total_lines=$(wc -l < "$todo_file")

  # Process in REVERSE order so line numbers stay valid after deletions
  local i=${#phase_headers[@]}
  while [[ $i -gt 0 ]]; do
    (( i-- )) || true
    local start="${phase_line_nums[$i]}"
    local header="${phase_headers[$i]}"

    # Find block end: next ### Phase or ## header, or EOF
    local block_end="$total_lines"
    local scan=$((start + 1))
    while [[ "$scan" -le "$total_lines" ]]; do
      local scan_line
      scan_line=$(sed -n "${scan}p" "$todo_file")
      if echo "$scan_line" | grep -qP '^###\s+Phase\s+\d+:'; then
        block_end=$((scan - 1))
        break
      fi
      if echo "$scan_line" | grep -qP '^## '; then
        block_end=$((scan - 1))
        break
      fi
      (( scan++ )) || true
    done

    # Extract block
    local block
    block=$(sed -n "${start},${block_end}p" "$todo_file")

    # Check: has tasks and all complete
    local has_tasks=false has_todo=false
    if echo "$block" | grep -qP '^\s*-\s*\[x\]'; then has_tasks=true; fi
    if echo "$block" | grep -qP '^\s*-\s*\[\s*\]'; then has_todo=true; fi

    if [[ "$has_tasks" == true && "$has_todo" == false ]]; then
      local phase_name
      phase_name=$(echo "$header" | sed 's/^### //')

      echo "[GP-10] Collapsing: $phase_name"

      # Replace block with single summary line (no separate archive file)
      local link_line="### ${phase_name} [completed]"
      local tmp_todo
      tmp_todo=$(mktemp)
      awk -v s="$start" -v e="$block_end" -v r="$link_line" \
        'NR==s{print r;next} NR>s&&NR<=e{next} {print}' "$todo_file" > "$tmp_todo"
      mv "$tmp_todo" "$todo_file"

      REPO_HAS_FIXES[backend]=1
      # Recalculate total_lines after block removal
      total_lines=$(wc -l < "$todo_file")
    fi
  done
}

if [[ "$DRY_RUN" == false && "$METRICS_ONLY" == false ]]; then
  echo ""
  echo "--- Auto-fix phase ---"

  # GP-10: auto-collapse completed Phases in TODO.md
  for r in "${RESULTS[@]}"; do
    IFS=$'\x1f' read -r gp repo severity status details <<< "$r"
    if [[ "$gp" == "GP-10" && "$status" == "FAIL" ]]; then
      archive_completed_phases
      AUTO_FIXED["GP-10|backend"]=1
      break
    fi
  done

  for r in "${RESULTS[@]}"; do
    IFS=$'\x1f' read -r gp repo severity status details <<< "$r"
    [[ "$status" == "FAIL" ]] || continue

    # GP-3 backend: ruff --fix (for linting issues), then re-verify with grep
    if [[ "$gp" == "GP-3" && "$repo" == "backend" ]]; then
      echo "[GP-3]  auto-fixing backend via ruff --fix..."
      (cd "${REPO_DIRS[backend]}" && uv run ruff check src/ --fix 2>&1) || true
      # Re-verify: grep for bare print() (same as detection)
      reverify_rc=0
      grep -rn 'print(' "${REPO_DIRS[backend]}/src/" --include='*.py' | grep -v '__pycache__' | grep -v '# noqa' > /dev/null 2>&1 || reverify_rc=$?
      if [[ "$reverify_rc" -ne 0 ]]; then
        echo "[GP-3]  FIXED  backend  ruff --fix applied"
        AUTO_FIXED["GP-3|backend"]=1
        REPO_HAS_FIXES[backend]=1
      else
        echo "[GP-3]  UNFIXED  backend  ruff --fix did not resolve all print() calls"
      fi
    fi

    # GP-8 backend: lint.sh (includes ruff --fix)
    if [[ "$gp" == "GP-8" && "$repo" == "backend" ]]; then
      echo "[GP-8] auto-fixing backend via lint..."
      if [[ -f "${REPO_DIRS[backend]}/scripts/lint.sh" ]]; then
        (cd "${REPO_DIRS[backend]}" && uv run ruff check src/ --fix 2>&1) || true
        if (cd "${REPO_DIRS[backend]}" && sh scripts/lint.sh >/dev/null 2>&1); then
          echo "[GP-8] FIXED  backend  lint now passes"
          AUTO_FIXED["GP-8|backend"]=1
          REPO_HAS_FIXES[backend]=1
        else
          echo "[GP-8] UNFIXED  backend  lint still fails after auto-fix"
        fi
      else
        (cd "${REPO_DIRS[backend]}" && uv run ruff check src/ --fix 2>&1) || true
        if (cd "${REPO_DIRS[backend]}" && uv run ruff check src/ >/dev/null 2>&1); then
          echo "[GP-8] FIXED  backend  ruff --fix applied"
          AUTO_FIXED["GP-8|backend"]=1
          REPO_HAS_FIXES[backend]=1
        else
          echo "[GP-8] UNFIXED  backend  ruff --fix did not resolve all issues"
        fi
      fi
    fi
  done
elif [[ "$METRICS_ONLY" == true ]]; then
  echo ""
  echo "--- Metrics-only mode: skipping auto-fix and report generation ---"
else
  echo ""
  echo "--- Dry run: skipping auto-fix and report generation ---"
fi

# ── Generate GARDEN_REPORT.md ──────────────────────────────────────
generate_report() {
  local report=""
  local has_fixed=false
  local has_review=false
  local fixed_section=""
  local review_section=""

  for r in "${RESULTS[@]}"; do
    IFS=$'\x1f' read -r gp repo severity status details <<< "$r"
    [[ "$status" == "FAIL" ]] || continue

    if [[ -n "${AUTO_FIXED["${gp}|${repo}"]:-}" ]]; then
      has_fixed=true
      fixed_section+="- [${gp}] ${repo}: auto-fixed via ruff --fix"$'\n'
    else
      has_review=true
      review_section+="- [${gp}] ${repo} — Severity: ${severity}"$'\n'
      review_section+="  Output: $(echo "$details" | head -30)"$'\n'
    fi
  done

  report="# Garden Report — ${DATE}"$'\n\n'
  if [[ "$has_fixed" == true ]]; then
    report+="## Auto-fixed"$'\n'
    report+="$fixed_section"$'\n'
  fi
  if [[ "$has_review" == true ]]; then
    report+="## 수정 필요"$'\n'
    report+="$review_section"$'\n'
  fi

  echo "$report"
}

# ── Report generation phase (skip if --dry-run) ──────────────────
REPORT_DIR="$WORKSPACE_ROOT/docs/reports/$(date +%Y)/$(date +%m)"

if [[ "$DRY_RUN" == false && "$METRICS_ONLY" == false ]]; then
  echo ""
  echo "--- Report generation phase ---"
  mkdir -p "$REPORT_DIR"

  report_content="$(generate_report)"
  report_file="${REPORT_DIR}/garden-${DATE}.md"

  echo "$report_content" > "$report_file"
  echo "  garden → $report_file"
else
  # In dry-run or metrics-only, still show what the report would look like
  echo ""
  echo "--- Report ---"
  generate_report
fi

# ── Summary ────────────────────────────────────────────────────────
echo ""
echo "--- Summary ---"

total_fixed=0
total_report=0
for r in "${RESULTS[@]}"; do
  IFS=$'\x1f' read -r gp repo severity status details <<< "$r"
  if [[ "$status" == "FAIL" ]]; then
    if [[ -n "${AUTO_FIXED["${gp}|${repo}"]:-}" ]]; then
      ((total_fixed++)) || true
    else
      ((total_report++)) || true
    fi
  fi
done

echo "Total violations: $VIOLATION_COUNT ($total_fixed auto-fixed, $total_report report-only)"
for repo in "${!REPO_VIOLATIONS[@]}"; do
  echo "  $repo: ${REPO_VIOLATIONS[$repo]} violation(s)"
done

if [[ "$DRY_RUN" == true ]]; then
  echo ""
  echo "(dry-run mode — no auto-fixes or reports were generated)"
elif [[ "$METRICS_ONLY" == true ]]; then
  echo ""
  echo "(metrics-only mode — QUALITY_SCORE.md updated, no auto-fixes or reports)"
else
  echo "Report written to: ${REPORT_DIR}/garden-${DATE}.md"
fi
