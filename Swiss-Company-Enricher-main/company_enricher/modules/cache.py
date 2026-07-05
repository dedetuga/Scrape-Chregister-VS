"""SQLite progress cache so long enrichment runs can resume."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class ProgressCache:
    """Thread-safe SQLite cache for enriched company rows."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS companies (ide TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.conn.commit()

    def get(self, ide: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute("SELECT payload FROM companies WHERE ide = ?", (ide,)).fetchone()
        return json.loads(row[0]) if row else None

    def set(self, ide: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO companies (ide, payload) VALUES (?, ?)",
                (ide, json.dumps(payload, ensure_ascii=False)),
            )
            self.conn.commit()

    def close(self) -> None:
        with self._lock:
            self.conn.close()
