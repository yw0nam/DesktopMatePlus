#!/usr/bin/env bash
# check_docs.sh — Documentation freshness linter
# Checks dead links, doc line limits, and spec coverage in Plans.md.
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCS_DIR="$WORKSPACE_ROOT/docs"
PLANS_FILE="$WORKSPACE_ROOT/Plans.md"

# ── CLI flags ──────────────────────────────────────────────────────
FIX_MODE=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --fix)      FIX_MODE=true; shift ;;
    --dry-run)  shift ;;  # accepted for garden.sh compat, same as default
    -h|--help)
      echo "Usage: scripts/check_docs.sh [--fix] [--dry-run]"
      echo "  --fix      Cleaner output (no auto-fix for docs, report only)"
      echo "  --dry-run  Same as default (detect only)"
      exit 0 ;;
    *)  echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Result tracking ───────────────────────────────────────────────
DEAD_LINKS=0
TOTAL_LINKS=0
OVERSIZED=0
MISSING_SPECS=0
HAS_HARD_FAILURE=false

# ── Check 1: Dead links in docs/ ─────────────────────────────────
echo "--- Dead link check ---"

while IFS= read -r md_file; do
  dir="$(dirname "$md_file")"
  # Extract markdown links: [text](path) — skip URLs (http/https/mailto)
  while IFS= read -r link; do
    [[ -n "$link" ]] || continue
    ((TOTAL_LINKS++)) || true

    # Strip anchor (#...) from link
    link_path="${link%%#*}"
    [[ -n "$link_path" ]] || continue

    # Resolve relative path
    if [[ "$link_path" == /* ]]; then
      target="$WORKSPACE_ROOT$link_path"
    else
      target="$dir/$link_path"
    fi

    if [[ ! -e "$target" ]]; then
      echo "[FAIL] Dead link in $(realpath --relative-to="$WORKSPACE_ROOT" "$md_file"): $link"
      ((DEAD_LINKS++)) || true
      HAS_HARD_FAILURE=true
    fi
  done < <(grep -oP '\[.*?\]\(\K[^)]+' "$md_file" 2>/dev/null | grep -v '^https\?://' | grep -v '^mailto:')
done < <(find "$DOCS_DIR" -name '*.md' -type f -not -path '*/superpowers/*' -not -path '*/reports/*' 2>/dev/null)

# Also check CLAUDE.md at workspace root
if [[ -f "$WORKSPACE_ROOT/CLAUDE.md" ]]; then
  dir="$WORKSPACE_ROOT"
  while IFS= read -r link; do
    [[ -n "$link" ]] || continue
    ((TOTAL_LINKS++)) || true
    link_path="${link%%#*}"
    [[ -n "$link_path" ]] || continue
    if [[ "$link_path" == /* ]]; then
      target="$WORKSPACE_ROOT$link_path"
    else
      target="$dir/$link_path"
    fi
    if [[ ! -e "$target" ]]; then
      echo "[FAIL] Dead link in CLAUDE.md: $link"
      ((DEAD_LINKS++)) || true
      HAS_HARD_FAILURE=true
    fi
  done < <(grep -oP '\[.*?\]\(\K[^)]+' "$WORKSPACE_ROOT/CLAUDE.md" 2>/dev/null | grep -v '^https\?://' | grep -v '^mailto:')
fi

if [[ "$DEAD_LINKS" -eq 0 ]]; then
  echo "[PASS] No dead links found ($TOTAL_LINKS links checked)"
else
  echo "[FAIL] $DEAD_LINKS dead link(s) found out of $TOTAL_LINKS"
fi

# ── Check 2: Docs exceeding 200 lines ────────────────────────────
echo ""
echo "--- Doc line limit check (200 lines) ---"

while IFS= read -r md_file; do
  lines=$(wc -l < "$md_file" | tr -d ' ')
  if [[ "$lines" -gt 200 ]]; then
    rel="$(realpath --relative-to="$WORKSPACE_ROOT" "$md_file")"
    echo "[WARN] $rel: $lines lines (>200)"
    ((OVERSIZED++)) || true
  fi
done < <(find "$DOCS_DIR" -name '*.md' -type f -not -path '*/superpowers/*' -not -path '*/reports/*' 2>/dev/null)

if [[ "$OVERSIZED" -eq 0 ]]; then
  echo "[PASS] All docs within 200-line limit"
else
  echo "[WARN] $OVERSIZED doc(s) exceed 200 lines"
fi

# ── Check 3: Specs vs Plans.md coverage ───────────────────────────
echo ""
echo "--- Spec coverage check ---"

SPECS_DIR="$DOCS_DIR/superpowers/specs"
if [[ -d "$SPECS_DIR" && -f "$PLANS_FILE" ]]; then
  while IFS= read -r spec_file; do
    spec_name="$(basename "$spec_file")"
    # Check if spec is referenced in Plans.md
    if ! grep -q "$spec_name" "$PLANS_FILE" 2>/dev/null; then
      echo "[WARN] Spec not referenced in Plans.md: $spec_name"
      ((MISSING_SPECS++)) || true
    fi
  done < <(find "$SPECS_DIR" -name '*.md' -type f 2>/dev/null)

  if [[ "$MISSING_SPECS" -eq 0 ]]; then
    echo "[PASS] All specs referenced in Plans.md"
  else
    echo "[WARN] $MISSING_SPECS spec(s) not referenced in Plans.md"
  fi
else
  echo "[PASS] No specs directory or Plans.md (skipped)"
fi

# ── Summary ───────────────────────────────────────────────────────
echo ""
echo "--- Summary ---"
echo "Dead links: $DEAD_LINKS (hard failure)"
echo "Oversized docs: $OVERSIZED (warning)"
echo "Unreferenced specs: $MISSING_SPECS (warning)"

if [[ "$HAS_HARD_FAILURE" == true ]]; then
  exit 1
else
  exit 0
fi
