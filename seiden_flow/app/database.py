from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


class FlowDatabase:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                schema_version TEXT NOT NULL,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                source_event_id TEXT,
                occurred_at TEXT NOT NULL,
                received_at TEXT NOT NULL,
                reader_id TEXT,
                reader_name TEXT,
                location_id TEXT,
                person_id TEXT,
                person_name TEXT,
                action TEXT,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_events_occurred ON events(occurred_at DESC);
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
            CREATE INDEX IF NOT EXISTS idx_events_person ON events(person_id, occurred_at DESC);
            CREATE INDEX IF NOT EXISTS idx_events_reader ON events(reader_id, occurred_at DESC);
            CREATE TABLE IF NOT EXISTS persons_state (
                person_key TEXT PRIMARY KEY,
                person_id TEXT,
                person_name TEXT NOT NULL,
                presence_status TEXT NOT NULL,
                current_location_id TEXT,
                current_reader_id TEXT,
                entered_at TEXT,
                last_event_id TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sources_state (
                source_key TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_name TEXT,
                status TEXT NOT NULL,
                last_event_id TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """)

    def insert_event(self, event: dict[str, Any]) -> bool:
        flat = event.get("_flat", {})
        with self._lock, self.connect() as conn:
            try:
                conn.execute(
                    """INSERT INTO events(event_id,schema_version,event_type,source,source_event_id,occurred_at,received_at,
                    reader_id,reader_name,location_id,person_id,person_name,action,payload_json)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        event["event_id"], event["schema_version"], event["event_type"], event["source"],
                        event.get("correlation", {}).get("source_event_id"), event["timestamp"],
                        event["received_at"], flat.get("reader_id"), flat.get("reader_name"),
                        flat.get("location_id"), flat.get("person_id"), flat.get("person_name"),
                        flat.get("action"), json.dumps({k: v for k, v in event.items() if k != "_flat"}, ensure_ascii=False),
                    ),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def apply_state(self, event: dict[str, Any]) -> None:
        flat = event.get("_flat", {})
        now = event["received_at"]
        event_type = event["event_type"]
        action = flat.get("action")
        person_name = flat.get("person_name")
        person_id = flat.get("person_id")
        if person_name and action in {"entered", "entry", "in", "exited", "exit", "out"}:
            present = action in {"entered", "entry", "in"}
            key = person_id or person_name.strip().lower()
            with self._lock, self.connect() as conn:
                conn.execute(
                    """INSERT INTO persons_state(person_key,person_id,person_name,presence_status,current_location_id,current_reader_id,
                    entered_at,last_event_id,updated_at) VALUES(?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(person_key) DO UPDATE SET person_id=excluded.person_id,person_name=excluded.person_name,
                    presence_status=excluded.presence_status,current_location_id=excluded.current_location_id,
                    current_reader_id=excluded.current_reader_id,entered_at=excluded.entered_at,
                    last_event_id=excluded.last_event_id,updated_at=excluded.updated_at""",
                    (key, person_id, person_name, "inside" if present else "outside", flat.get("location_id"),
                     flat.get("reader_id"), event["timestamp"] if present else None, event["event_id"], now),
                )
        if event_type in {"reader.online", "reader.offline"} or event_type.endswith("reader_online") or event_type.endswith("reader_offline"):
            reader_id = flat.get("reader_id") or "unknown"
            status = "online" if "online" in event_type and "offline" not in event_type else "offline"
            with self._lock, self.connect() as conn:
                conn.execute(
                    """INSERT INTO sources_state(source_key,source_type,source_id,source_name,status,last_event_id,updated_at)
                    VALUES(?,?,?,?,?,?,?) ON CONFLICT(source_key) DO UPDATE SET source_name=excluded.source_name,
                    status=excluded.status,last_event_id=excluded.last_event_id,updated_at=excluded.updated_at""",
                    (f"reader:{reader_id}", "reader", reader_id, flat.get("reader_name"), status, event["event_id"], now),
                )

    def list_events(self, limit: int = 100, event_type: str | None = None, person: str | None = None) -> list[dict]:
        clauses, params = [], []
        if event_type:
            clauses.append("event_type = ?"); params.append(event_type)
        if person:
            clauses.append("(person_name LIKE ? OR person_id = ?)"); params.extend([f"%{person}%", person])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connect() as conn:
            rows = conn.execute(f"SELECT payload_json FROM events{where} ORDER BY occurred_at DESC LIMIT ?", (*params, min(limit, 5000))).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]

    def people_inside(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM persons_state WHERE presence_status='inside' ORDER BY entered_at").fetchall()
        return [dict(r) for r in rows]

    def people_state(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM persons_state ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]

    def sources_state(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM sources_state ORDER BY source_type,source_name,source_id").fetchall()
        return [dict(r) for r in rows]

    def summary(self) -> dict[str, Any]:
        with self.connect() as conn:
            total = conn.execute("SELECT COUNT(*) c FROM events").fetchone()["c"]
            today = conn.execute("SELECT COUNT(*) c FROM events WHERE occurred_at >= date('now')").fetchone()["c"]
            inside = conn.execute("SELECT COUNT(*) c FROM persons_state WHERE presence_status='inside'").fetchone()["c"]
            offline = conn.execute("SELECT COUNT(*) c FROM sources_state WHERE status='offline'").fetchone()["c"]
            last = conn.execute("SELECT occurred_at,event_type,person_name,reader_name FROM events ORDER BY occurred_at DESC LIMIT 1").fetchone()
        return {"events_total": total, "events_today": today, "people_inside": inside, "sources_offline": offline, "last_event": dict(last) if last else None}

    def cleanup(self, retention_days: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        with self._lock, self.connect() as conn:
            cur = conn.execute("DELETE FROM events WHERE occurred_at < ?", (cutoff,))
            return cur.rowcount
