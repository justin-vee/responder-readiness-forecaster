from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class AuditMemory:
    """SQLite-backed short-term trace and aggregate long-term run history."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.path,
            timeout=10.0,
            isolation_level=None,
        )
        self.connection: sqlite3.Connection | None = connection
        try:
            connection.execute("PRAGMA busy_timeout = 10000")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS events "
                "(run_id TEXT NOT NULL, sequence INTEGER NOT NULL, agent TEXT NOT NULL, "
                "action TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS runs "
                "(run_id TEXT PRIMARY KEY, scenario_label TEXT NOT NULL, decision TEXT NOT NULL, "
                "strain TEXT NOT NULL, score INTEGER NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_run_sequence ON events(run_id, sequence)"
            )
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            connection.close()
            self.connection = None
            raise

    def _require_connection(self) -> sqlite3.Connection:
        if self.connection is None:
            raise RuntimeError("audit_memory_is_closed")
        return self.connection

    def log(self, run_id: str, agent: str, action: str, payload: Any) -> None:
        connection = self._require_connection()
        rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        connection.execute("BEGIN IMMEDIATE")
        try:
            row = connection.execute(
                "SELECT COALESCE(MAX(sequence), -1) + 1 FROM events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            sequence = int(row[0])
            connection.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?)",
                (run_id, sequence, agent, action, rendered),
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

    def save_run(self, run_id: str, scenario_label: str, decision: str, strain: str, score: int) -> None:
        connection = self._require_connection()
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?)",
                (run_id, scenario_label, decision, strain, score),
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

    def prior_run_count(self) -> int:
        connection = self._require_connection()
        return int(connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0])

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def __enter__(self) -> "AuditMemory":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
