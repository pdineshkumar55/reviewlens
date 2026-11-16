"""Fail if any user-visible string contains banned words or AI-style phrasing.

    python scripts/check_ui_copy.py

Scans string literals (not docstrings or comments) in the UI code and in the
modules whose strings end up on screen or in downloaded files.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reviewlens.sanitize import find_banned_ui_words, find_style_phrases

SCAN = [
    ROOT / "app.py",
    *sorted((ROOT / "ui").glob("*.py")),
    ROOT / "reviewlens" / "report.py",
    ROOT / "reviewlens" / "rules.py",
    ROOT / "reviewlens" / "validation.py",
    ROOT / "reviewlens" / "export.py",
    ROOT / ".streamlit" / "config.toml",
]


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def strings_in(path: Path) -> list[tuple[int, str]]:
    if path.suffix != ".py":
        return [(i, line) for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    skip = _docstring_ids(tree)
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip
    ]


def check(paths: list[Path] = SCAN) -> list[str]:
    problems = []
    for path in paths:
        if not path.exists():
            continue
        for lineno, text in strings_in(path):
            hits = find_banned_ui_words(text) + find_style_phrases(text)
            if hits:
                rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
                problems.append(f"{rel}:{lineno}: {', '.join(hits)} in {text[:70]!r}")
    return problems


def main() -> int:
    problems = check()
    for p in problems:
        print(p)
    if problems:
        print(f"\nUI copy check failed: {len(problems)} problem(s).")
        return 1
    print(f"UI copy check passed ({sum(p.exists() for p in SCAN)} files scanned).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
