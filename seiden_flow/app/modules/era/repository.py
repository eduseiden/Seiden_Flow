\
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


class ERARepository:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._migrate()

    def _migrate(self):
        with self.lock:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS incidents(
                incident_id TEXT PRIMARY KEY,
                incident_key TEXT NOT NULL UNIQUE,
                tenant_id TEXT NOT NULL,
                source_module TEXT NOT NULL,
                source_event_key TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                asset_name TEXT NOT NULL,
                severity TEXT NOT NULL,
                state TEXT NOT NULL,
                title TEXT NOT NULL,
                details_json TEXT NOT NULL,
                opened_at TEXT NOT NULL,
                eligible_at TEXT NOT NULL,
                last_event_at TEXT NOT NULL,
                recovered_at TEXT,
                notified_open INTEGER NOT NULL DEFAULT 0,
                notified_recovery INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_era_incidents_state
              ON incidents(state,severity,opened_at);
            CREATE INDEX IF NOT EXISTS idx_era_incidents_asset
              ON incidents(source_module,tenant_id,asset_id,state);

            CREATE TABLE IF NOT EXISTS deliveries(
                delivery_id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL,
                phase TEXT NOT NULL,
                channel TEXT NOT NULL,
                destination TEXT,
                attempted_at TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                FOREIGN KEY(incident_id) REFERENCES incidents(incident_id)
            );
            CREATE INDEX IF NOT EXISTS idx_era_deliveries_incident
              ON deliveries(incident_id,attempted_at);
            """)
            self.conn.commit()

    @staticmethod
    def _incident_key(event: dict[str, Any]) -> str:
        return "|".join((
            str(event.get("tenant_id") or "default"),
            str(event.get("source_module") or "UNKNOWN").upper(),
            str(event.get("asset_id") or "unknown"),
            str(event.get("event_key") or event.get("event_type") or "event"),
        ))

    @staticmethod
    def _delay_minutes(event: dict[str, Any], critical_delay: int, warning_delay: int) -> int:
        severity = str(event.get("severity") or "warning").lower()
        return critical_delay if severity == "critical" else warning_delay

    def apply_event(self, event: dict[str, Any], critical_delay: int = 0, warning_delay: int = 10) -> dict[str, Any]:
        now = str(event.get("timestamp") or utc_now())
        state = str(event.get("state") or "active").lower()
        if state not in ("active", "recovered"):
            raise ValueError("invalid_event_state")
        source_module = str(event.get("source_module") or "").strip().upper()
        tenant_id = str(event.get("tenant_id") or "default").strip()
        asset_id = str(event.get("asset_id") or "").strip()
        event_key = str(event.get("event_key") or event.get("event_type") or "").strip()
        title = str(event.get("title") or event_key or "Evento operacional").strip()
        asset_name = str(event.get("asset_name") or asset_id or "Ativo").strip()
        severity = str(event.get("severity") or "warning").strip().lower()
        if severity not in ("warning", "critical"):
            severity = "warning"
        if not source_module or not asset_id or not event_key:
            raise ValueError("missing_event_identity")

        normalized = {
            **event,
            "source_module": source_module,
            "tenant_id": tenant_id,
            "asset_id": asset_id,
            "asset_name": asset_name,
            "event_key": event_key,
            "title": title,
            "severity": severity,
            "state": state,
            "timestamp": now,
        }
        key = self._incident_key(normalized)

        with self.lock:
            row = self.conn.execute("SELECT * FROM incidents WHERE incident_key=?", (key,)).fetchone()
            if state == "active":
                if row and row["state"] == "open":
                    self.conn.execute(
                        """UPDATE incidents SET severity=?,asset_name=?,title=?,details_json=?,
                           last_event_at=?,updated_at=? WHERE incident_key=?""",
                        (severity, asset_name, title, json.dumps(normalized.get("details") or {}, ensure_ascii=False),
                         now, utc_now(), key),
                    )
                    self.conn.commit()
                    return self.get(row["incident_id"])

                delay = self._delay_minutes(normalized, critical_delay, warning_delay)
                base = _parse_dt(now) or datetime.now(timezone.utc)
                eligible = (base + timedelta(minutes=max(0, delay))).isoformat().replace("+00:00", "Z")
                incident_id = f"ERA-{uuid.uuid4().hex[:10].upper()}"
                if row:
                    self.conn.execute(
                        """UPDATE incidents SET incident_id=?,severity=?,state='open',asset_name=?,title=?,
                           details_json=?,opened_at=?,eligible_at=?,last_event_at=?,recovered_at=NULL,
                           notified_open=0,notified_recovery=0,updated_at=? WHERE incident_key=?""",
                        (incident_id, severity, asset_name, title,
                         json.dumps(normalized.get("details") or {}, ensure_ascii=False),
                         now, eligible, now, utc_now(), key),
                    )
                else:
                    self.conn.execute(
                        """INSERT INTO incidents(
                           incident_id,incident_key,tenant_id,source_module,source_event_key,asset_id,asset_name,
                           severity,state,title,details_json,opened_at,eligible_at,last_event_at,updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (incident_id, key, tenant_id, source_module, event_key, asset_id, asset_name,
                         severity, "open", title, json.dumps(normalized.get("details") or {}, ensure_ascii=False),
                         now, eligible, now, utc_now()),
                    )
                self.conn.commit()
                return self.get(incident_id)

            # recovered
            if not row or row["state"] != "open":
                return {"ignored": True, "reason": "no_open_incident", "incident_key": key}
            self.conn.execute(
                """UPDATE incidents SET state='recovered',last_event_at=?,recovered_at=?,updated_at=?
                   WHERE incident_key=?""",
                (now, now, utc_now(), key),
            )
            self.conn.commit()
            return self.get(row["incident_id"])

    def get(self, incident_id: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
            return self._row(row) if row else None

    def _row(self, row):
        if not row:
            return None
        d = dict(row)
        try:
            d["details"] = json.loads(d.pop("details_json") or "{}")
        except Exception:
            d["details"] = {}
            d.pop("details_json", None)
        d["notified_open"] = bool(d["notified_open"])
        d["notified_recovery"] = bool(d["notified_recovery"])
        return d

    def list(self, state: str = "all", limit: int = 200):
        q = "SELECT * FROM incidents"
        args = []
        if state in ("open", "recovered"):
            q += " WHERE state=?"
            args.append(state)
        q += " ORDER BY CASE WHEN state='open' THEN 0 ELSE 1 END, CASE severity WHEN 'critical' THEN 0 ELSE 1 END, opened_at DESC LIMIT ?"
        args.append(max(1, min(1000, int(limit))))
        with self.lock:
            return [self._row(r) for r in self.conn.execute(q, args).fetchall()]

    def open_for_asset(self, source_module: str, tenant_id: str, asset_id: str):
        with self.lock:
            rows = self.conn.execute(
                """SELECT * FROM incidents WHERE state='open' AND source_module=? AND tenant_id=? AND asset_id=?""",
                (source_module.upper(), tenant_id, asset_id),
            ).fetchall()
            return [self._row(r) for r in rows]

    def due_open(self):
        now = utc_now()
        with self.lock:
            rows = self.conn.execute(
                """SELECT * FROM incidents
                   WHERE state='open' AND notified_open=0 AND eligible_at<=?
                   ORDER BY CASE severity WHEN 'critical' THEN 0 ELSE 1 END, opened_at""",
                (now,),
            ).fetchall()
            return [self._row(r) for r in rows]

    def due_recovery(self):
        with self.lock:
            rows = self.conn.execute(
                """SELECT * FROM incidents
                   WHERE state='recovered' AND notified_open=1 AND notified_recovery=0
                   ORDER BY recovered_at""",
            ).fetchall()
            return [self._row(r) for r in rows]

    def mark_phase_notified(self, incident_id: str, phase: str):
        col = "notified_open" if phase == "open" else "notified_recovery"
        with self.lock:
            self.conn.execute(f"UPDATE incidents SET {col}=1,updated_at=? WHERE incident_id=?", (utc_now(), incident_id))
            self.conn.commit()

    def delivery(self, incident_id: str, phase: str, channel: str, destination: str, ok: bool, error_text: str = ""):
        with self.lock:
            self.conn.execute(
                """INSERT INTO deliveries(delivery_id,incident_id,phase,channel,destination,attempted_at,status,error)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (uuid.uuid4().hex, incident_id, phase, channel, destination, utc_now(), "sent" if ok else "failed", error_text or None),
            )
            self.conn.commit()

    def summary(self):
        today = datetime.now(timezone.utc).date().isoformat()
        with self.lock:
            open_total = self.conn.execute("SELECT COUNT(*) FROM incidents WHERE state='open'").fetchone()[0]
            critical = self.conn.execute("SELECT COUNT(*) FROM incidents WHERE state='open' AND severity='critical'").fetchone()[0]
            warning = self.conn.execute("SELECT COUNT(*) FROM incidents WHERE state='open' AND severity='warning'").fetchone()[0]
            recovered_today = self.conn.execute(
                "SELECT COUNT(*) FROM incidents WHERE state='recovered' AND substr(recovered_at,1,10)=?", (today,)
            ).fetchone()[0]
        return {
            "open": int(open_total),
            "critical": int(critical),
            "warning": int(warning),
            "recovered_today": int(recovered_today),
        }
