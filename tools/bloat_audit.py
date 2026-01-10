#!/usr/bin/env python
"""Generate lightweight repo size/churn metrics using git-tracked files only."""
from __future__ import annotations

import argparse
import collections
import pathlib
import subprocess
import sys
from typing import Iterable


def _git_ls_files() -> list[pathlib.Path]:
    try:
        output = subprocess.check_output(["git", "ls-files"], text=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"git ls-files failed: {exc}")
    files = [line.strip() for line in output.splitlines() if line.strip()]
    return [pathlib.Path(path) for path in files]


def _line_count(path: pathlib.Path) -> int:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return 0
    return sum(1 for _ in text.splitlines())


def _summarize_by_prefix(paths: Iterable[pathlib.Path], depth: int) -> dict[str, dict]:
    counts = collections.Counter()
    locs = collections.Counter()
    for path in paths:
        parts = path.parts
        if not parts:
            continue
        prefix = "/".join(parts[:depth])
        counts[prefix] += 1
        locs[prefix] += _line_count(path)
    summary = {}
    for key in counts:
        summary[key] = {"files": counts[key], "loc": locs[key]}
    return summary


def _print_table(title: str, rows: list[tuple[str, int, int]]) -> None:
    print(title)
    print("dir\tfiles\tloc")
    for name, files, loc in rows:
        print(f"{name}\t{files}\t{loc}")
    print()


def _top_churn(limit: int) -> list[tuple[str, int]]:
    log_output = subprocess.check_output(
        ["git", "log", f"-n{limit}", "--name-only", "--pretty=format:--"],
        text=True,
    )
    counts = collections.Counter()
    for line in log_output.splitlines():
        if not line or line.startswith("--"):
            continue
        counts[line] += 1
    return counts.most_common(10)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--depth",
        type=int,
        default=1,
        help="Directory depth to summarize (1 = top-level, 2 = top-level/subdir)",
    )
    parser.add_argument(
        "--churn-commits",
        type=int,
        default=30,
        help="Number of recent commits to include in churn summary",
    )
    args = parser.parse_args()

    paths = _git_ls_files()
    if not paths:
        print("No tracked files found.")
        return 0

    summary = _summarize_by_prefix(paths, depth=args.depth)
    rows = sorted(
        ((key, value["files"], value["loc"]) for key, value in summary.items()),
        key=lambda item: item[0].lower(),
    )
    _print_table(f"Summary (depth={args.depth})", rows)

    largest = sorted(
        ((key, value["files"], value["loc"]) for key, value in summary.items()),
        key=lambda item: item[2],
        reverse=True,
    )[:10]
    _print_table("Largest areas by LOC", largest)

    churn = _top_churn(args.churn_commits)
    print("Top churn files (recent commits)")
    for path, count in churn:
        print(f"{path}\t{count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
