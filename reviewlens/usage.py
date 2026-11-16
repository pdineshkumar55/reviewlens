"""Run logging and usage caps.

* ``logs/runs.jsonl``: one JSON line per run, never containing review text.
* ``.cache/usage.sqlite``: daily run counter for the global cap.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

_lock = threading.Lock()


def log_run(log_dir: Path, record: dict) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    record = {"timestamp": datetime.now(UTC).isoformat(timespec="seconds"), **record}
    with _lock, open(log_dir / "runs.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


class DailyCounter:
    """Counts runs per UTC day in SQLite so the cap holds across restarts."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as con:
            con.execute("CREATE TABLE IF NOT EXISTS runs (day TEXT PRIMARY KEY, count INTEGER NOT NULL)")

    @staticmethod
    def _today() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def count(self) -> int:
        with sqlite3.connect(self.path) as con:
            row = con.execute("SELECT count FROM runs WHERE day = ?", (self._today(),)).fetchone()
        return int(row[0]) if row else 0

    def try_acquire(self, cap: int) -> bool:
        """Increment today's count if it is below ``cap``. Returns False when the cap is hit."""
        with _lock, sqlite3.connect(self.path, isolation_level="IMMEDIATE") as con:
            day = self._today()
            row = con.execute("SELECT count FROM runs WHERE day = ?", (day,)).fetchone()
            current = int(row[0]) if row else 0
            if current >= cap:
                return False
            con.execute(
                "INSERT INTO runs (day, count) VALUES (?, 1) ON CONFLICT(day) DO UPDATE SET count = count + 1",
                (day,),
            )
            return True
