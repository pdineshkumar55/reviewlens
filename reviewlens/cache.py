"""SQLite cache for per-review results, so re-uploading a file is instant and free."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path


def cache_key(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


class ResultCache:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS results ("
                " key TEXT PRIMARY KEY, value TEXT NOT NULL,"
                " created TEXT DEFAULT CURRENT_TIMESTAMP)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def get_many(self, keys: list[str]) -> dict[str, dict]:
        found: dict[str, dict] = {}
        with self._connect() as con:
            for i in range(0, len(keys), 500):
                chunk = keys[i : i + 500]
                marks = ",".join("?" * len(chunk))
                rows = con.execute(f"SELECT key, value FROM results WHERE key IN ({marks})", chunk).fetchall()
                found.update({k: json.loads(v) for k, v in rows})
        return found

    def put_many(self, items: dict[str, dict]) -> None:
        if not items:
            return
        with self._lock, self._connect() as con:
            con.executemany(
                "INSERT OR REPLACE INTO results (key, value) VALUES (?, ?)",
                [(k, json.dumps(v, ensure_ascii=False)) for k, v in items.items()],
            )
