#!/usr/bin/env bash
# Pre-commit hook: block direct commits to master branch.
# Bypass: ALLOW_MASTER=1 git commit ...

branch=$(git branch --show-current)

if [ "$branch" = "master" ] && [ -z "$ALLOW_MASTER" ]; then
    echo ""
    echo "  Direct commits to master are blocked."
    echo "  Use a worktree:  git worktree add worktrees/<name> -b <branch>"
    echo "  Or bypass:       ALLOW_MASTER=1 git commit ..."
    echo ""
    exit 1
fi
