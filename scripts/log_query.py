#!/usr/bin/env python3
"""Loguru log file parser and CLI query tool.

Log format expected:
    10:30:01.234 | ERROR    | src.services.agent:42 | [req-123] - message
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

LOG_PATTERN = re.compile(
    r"^(\d{2}:\d{2}:\d{2})\.\d+ \| (\w+)\s+\| ([^\|]+:\d+) \| (.*)$"
)

LEVEL_ORDER = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]


def find_log_file() -> Path | None:
    """Auto-detect log file using priority order:
    1. LOG_DIR env var
    2. .run.logdir file
    3. logs/ directory with today's date file
    """
    # 1. LOG_DIR env var
    log_dir_env = os.environ.get("LOG_DIR")
    if log_dir_env:
        log_dir = Path(log_dir_env)
        if log_dir.is_dir():
            today = date.today().strftime("%Y-%m-%d")
            candidate = log_dir / f"app_{today}.log"
            if candidate.exists():
                return candidate
            # Return any .log file in the dir
            logs = sorted(log_dir.glob("*.log"))
            if logs:
                return logs[-1]

    # 2. .run.logdir file
    run_logdir = Path(".run.logdir")
    if run_logdir.exists():
        stored_dir = run_logdir.read_text().strip()
        if stored_dir:
            log_dir = Path(stored_dir)
            if log_dir.is_dir():
                today = date.today().strftime("%Y-%m-%d")
                candidate = log_dir / f"app_{today}.log"
                if candidate.exists():
                    return candidate
                logs = sorted(log_dir.glob("*.log"))
                if logs:
                    return logs[-1]

    # 3. logs/ directory with today's date file
    logs_dir = Path("logs")
    if logs_dir.is_dir():
        today = date.today().strftime("%Y-%m-%d")
        candidate = logs_dir / f"app_{today}.log"
        if candidate.exists():
            return candidate
        # Search in subdirectories
        for log_file in sorted(logs_dir.rglob(f"app_{today}.log")):
            return log_file

    return None


def parse_level(line: str) -> str | None:
    m = LOG_PATTERN.match(line)
    if m:
        return m.group(2).strip()
    return None


def parse_time(line: str) -> str | None:
    m = LOG_PATTERN.match(line)
    if m:
        return m.group(1)
    return None


def level_index(level: str) -> int:
    try:
        return LEVEL_ORDER.index(level.upper())
    except ValueError:
        return -1


def filter_lines(
    lines: list[str],
    level: str | None = None,
    last: int | None = None,
    since: str | None = None,
) -> list[str]:
    """Filter log lines by level, count, or time."""
    result = lines

    # Filter by level (>= specified level)
    if level:
        min_idx = level_index(level.upper())
        filtered = []
        for line in result:
            lvl = parse_level(line)
            if lvl and level_index(lvl) >= min_idx:
                filtered.append(line)
            elif not lvl:
                # Keep non-matching lines that are continuation of previous
                pass
        result = filtered

    # Filter by since time
    if since:
        filtered = []
        since_dt = datetime.strptime(since, "%H:%M:%S").time()
        for line in result:
            t = parse_time(line)
            if t:
                try:
                    line_dt = datetime.strptime(t, "%H:%M:%S").time()
                    if line_dt >= since_dt:
                        filtered.append(line)
                except ValueError:
                    pass
        result = filtered

    # Last N lines
    if last is not None:
        result = result[-last:]

    return result


def print_summary(log_file: Path, lines: list[str]) -> None:
    """Print log summary with level counts and recent errors."""
    level_counts: dict[str, int] = {}
    total = len(lines)

    for line in lines:
        lvl = parse_level(line)
        if lvl:
            level_counts[lvl] = level_counts.get(lvl, 0) + 1

    print(f"=== Log Summary ({log_file}) ===")
    print(f"Total lines : {total}")
    print(f"ERROR       : {level_counts.get('ERROR', 0)}")
    print(f"CRITICAL    : {level_counts.get('CRITICAL', 0)}")

    # Recent errors
    error_lines = []
    for line in lines:
        lvl = parse_level(line)
        if lvl in ("ERROR", "CRITICAL"):
            m = LOG_PATTERN.match(line)
            if m:
                time_str = m.group(1)
                location = m.group(3).strip()
                message = m.group(4).strip()
                error_lines.append((time_str, location, message))

    if error_lines:
        print("\nRecent errors:")
        for time_str, location, message in error_lines[-5:]:
            print(f"  {time_str}  {location:<30}  {message}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query and summarize Loguru log files."
    )
    parser.add_argument("--level", metavar="LEVEL", help="Minimum log level to show")
    parser.add_argument("--last", type=int, metavar="N", help="Show last N lines")
    parser.add_argument(
        "--since", metavar="HH:MM:SS", help="Show lines since this time"
    )
    parser.add_argument(
        "--summary", action="store_true", help="Show level count summary"
    )
    parser.add_argument(
        "logfile",
        nargs="?",
        metavar="FILE",
        help="Log file path (auto-detected if omitted)",
    )
    args = parser.parse_args()

    # Resolve log file
    if args.logfile:
        log_file = Path(args.logfile)
    else:
        log_file = find_log_file()

    if log_file is None:
        if args.summary:
            print("=== Log Summary (no log file found) ===")
            print("Total lines : 0")
            print("ERROR       : 0")
            print("CRITICAL    : 0")
            sys.exit(0)
        print("[log_query] No log file found.", file=sys.stderr)
        print(
            "  Checked: $LOG_DIR, .run.logdir, logs/app_YYYY-MM-DD.log",
            file=sys.stderr,
        )
        sys.exit(0)

    if not log_file.exists():
        if args.summary:
            print(f"=== Log Summary ({log_file}) ===")
            print("Total lines : 0")
            print("ERROR       : 0")
            print("CRITICAL    : 0")
            sys.exit(0)
        print(f"[log_query] Log file not found: {log_file}", file=sys.stderr)
        sys.exit(0)

    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()

    filtered = filter_lines(lines, level=args.level, last=args.last, since=args.since)

    if args.summary:
        print_summary(log_file, filtered)
    else:
        for line in filtered:
            print(line)


if __name__ == "__main__":
    main()
