#!/usr/bin/env python3
"""Project cleanup utility.

Scans for legacy files, unused imports, and zombie commented-out code.
"""
from __future__ import annotations

import ast
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}

LOG_DIR_HINTS = {"logs", "log"}

LEGACY_EXTENSIONS = {".bak", ".tmp", ".log"}


@dataclass
class FileFinding:
    path: Path
    reason: str


@dataclass
class ImportFinding:
    path: Path
    unused: List[str]


@dataclass
class CommentBlockFinding:
    path: Path
    start_line: int
    end_line: int


def iter_python_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            if filename.endswith(".py"):
                yield Path(dirpath) / filename


def scan_unused_files(root: Path) -> Tuple[List[FileFinding], List[Path]]:
    findings: List[FileFinding] = []
    delete_targets: List[Path] = []

    legacy_candidates = [root / "config.yaml.bak"]
    for candidate in legacy_candidates:
        if candidate.exists():
            findings.append(FileFinding(candidate, "Legacy backup file"))
            delete_targets.append(candidate)

    file_manager = root / "utils" / "file_manager.py"
    if file_manager.exists():
        import_count = count_file_manager_imports(root)
        if import_count == 0:
            findings.append(FileFinding(file_manager, "utils.file_manager has 0 references"))
            delete_targets.append(file_manager)

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        current_dir = Path(dirpath)
        if current_dir.name in LOG_DIR_HINTS:
            continue

        for filename in filenames:
            path = current_dir / filename
            if path.suffix in LEGACY_EXTENSIONS:
                findings.append(FileFinding(path, f"Legacy extension {path.suffix}"))
                delete_targets.append(path)
            if path.suffix == ".pyc":
                findings.append(FileFinding(path, "Compiled Python artifact"))
                delete_targets.append(path)

        for dirname in dirnames:
            if dirname == "__pycache__":
                cache_path = current_dir / dirname
                findings.append(FileFinding(cache_path, "Python cache directory"))
                delete_targets.append(cache_path)

    return findings, delete_targets


def count_file_manager_imports(root: Path) -> int:
    count = 0
    for path in iter_python_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "utils.file_manager":
                        count += 1
            if isinstance(node, ast.ImportFrom):
                if node.module == "utils":
                    for alias in node.names:
                        if alias.name == "file_manager":
                            count += 1
    return count


def scan_unused_imports(root: Path) -> List[ImportFinding]:
    findings: List[ImportFinding] = []
    for path in iter_python_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue

        imported: Dict[str, str] = {}
        used: Set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imported[name] = alias.name
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname or alias.name
                    imported[name] = f"{node.module}.{alias.name}" if node.module else alias.name
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used.add(node.id)

        unused = [name for name in imported if name not in used and not name.startswith("_")]
        if unused:
            findings.append(ImportFinding(path, sorted(unused)))

    return findings


def scan_zombie_code(root: Path) -> List[CommentBlockFinding]:
    findings: List[CommentBlockFinding] = []
    for path in iter_python_files(root):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue

        block_start = None
        count = 0
        for idx, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                if block_start is None:
                    block_start = idx
                count += 1
            else:
                if count >= 6 and block_start is not None:
                    findings.append(CommentBlockFinding(path, block_start, idx - 1))
                block_start = None
                count = 0

        if count >= 6 and block_start is not None:
            findings.append(CommentBlockFinding(path, block_start, len(lines)))

    return findings


def format_table(rows: List[List[str]], headers: List[str]) -> str:
    if not rows:
        return "(none)"

    widths = [len(header) for header in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def format_row(row: List[str]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

    divider = "-+-".join("-" * width for width in widths)
    output = [format_row(headers), divider]
    output.extend(format_row(row) for row in rows)
    return "\n".join(output)


def prompt_yes_no(message: str) -> bool:
    response = input(f"{message} ").strip().lower()
    return response in {"y", "yes"}


def delete_targets(paths: List[Path]) -> None:
    for path in paths:
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() or child.is_symlink():
                    child.unlink()
            for child in sorted(path.rglob("*"), reverse=True):
                if child.is_dir():
                    child.rmdir()
            path.rmdir()
        elif path.exists():
            path.unlink()


def main() -> int:
    legacy_findings, delete_list = scan_unused_files(PROJECT_ROOT)
    import_findings = scan_unused_imports(PROJECT_ROOT)
    zombie_findings = scan_zombie_code(PROJECT_ROOT)

    print("\nLegacy files and artifacts:")
    legacy_rows = [[str(f.path.relative_to(PROJECT_ROOT)), f.reason] for f in legacy_findings]
    print(format_table(legacy_rows, ["Path", "Reason"]))

    print("\nUnused imports:")
    import_rows = [
        [str(f.path.relative_to(PROJECT_ROOT)), ", ".join(f.unused)] for f in import_findings
    ]
    print(format_table(import_rows, ["Path", "Unused Imports"]))

    print("\nZombie commented-out code blocks (>5 lines):")
    zombie_rows = [
        [
            str(f.path.relative_to(PROJECT_ROOT)),
            f"Lines {f.start_line}-{f.end_line}",
        ]
        for f in zombie_findings
    ]
    print(format_table(zombie_rows, ["Path", "Location"]))

    if delete_list:
        unique_delete = sorted({path for path in delete_list})
        print("\nDelete candidates:")
        delete_rows = [[str(path.relative_to(PROJECT_ROOT))] for path in unique_delete]
        print(format_table(delete_rows, ["Path"]))
        if prompt_yes_no("Delete these files? (y/N)"):
            delete_targets(unique_delete)
            print("Deleted selected files.")
        else:
            print("No files were deleted.")
    else:
        print("\nNo delete candidates found.")

    if import_findings or zombie_findings:
        print("\nNote: Unused imports and zombie code are reported for manual cleanup.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
