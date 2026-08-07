from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone


class LCARepository:
    """Persistence and relevant-event processing for Lighting Context Analytics.

    MQTT publications are telemetry. They only become analytical events when a
    channel actually changes state or an explicit physical interaction is
    observed.
    """

    def __init__(self, db):
        self.db = db
        self.ensure_schema()
        self._migrate_010_history()
        self._migrate_035_channel_aliases()
        self._migrate_036_logical_circuits()
        self._migrate_037_infrastructure_identity()

    def ensure_schema(self):
        with self.db.connect() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS lca_devices(
                  device_id TEXT PRIMARY KEY, site_id TEXT NOT NULL, name TEXT NOT NULL, topic TEXT,
                  model TEXT, manufacturer TEXT, device_type TEXT NOT NULL DEFAULT 'unknown', status TEXT NOT NULL DEFAULT 'discovered',
                  location_id TEXT, location_name TEXT, adjacent_location_id TEXT, adjacent_location_name TEXT,
                  position_label TEXT, notes TEXT, availability TEXT NOT NULL DEFAULT 'unknown',
                  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, sample_payload_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS lca_channels(
                  channel_id TEXT PRIMARY KEY, device_id TEXT NOT NULL, channel_key TEXT NOT NULL, name TEXT,
                  interaction_point TEXT, location_id TEXT, location_name TEXT, adjacent_location_id TEXT, adjacent_location_name TEXT,
                  direction_hint TEXT, related_light_id TEXT, related_light_name TEXT, virtual_parallel_group TEXT,
                  enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                  FOREIGN KEY(device_id) REFERENCES lca_devices(device_id) ON DELETE CASCADE);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_lca_channel_unique ON lca_channels(device_id,channel_key);
                CREATE TABLE IF NOT EXISTS lca_events(
                  id INTEGER PRIMARY KEY AUTOINCREMENT, lca_event_id TEXT NOT NULL UNIQUE, device_id TEXT NOT NULL,
                  channel_key TEXT, kind TEXT NOT NULL, state TEXT, action TEXT, brightness REAL, occurred_at TEXT NOT NULL,
                  origin_location_id TEXT, origin_location_name TEXT, adjacent_location_id TEXT, adjacent_location_name TEXT,
                  direction_hint TEXT, related_light_id TEXT, related_light_name TEXT, virtual_parallel_group TEXT,
                  payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_lca_events_time ON lca_events(occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_lca_events_device_time ON lca_events(device_id,occurred_at DESC);
                CREATE TABLE IF NOT EXISTS lca_sessions(
                  session_id TEXT PRIMARY KEY, device_id TEXT NOT NULL, channel_key TEXT, related_light_id TEXT,
                  started_at TEXT NOT NULL, ended_at TEXT, duration_seconds INTEGER, start_event_id TEXT NOT NULL,
                  end_event_id TEXT, status TEXT NOT NULL DEFAULT 'open', updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_lca_sessions_start ON lca_sessions(started_at DESC);

                CREATE TABLE IF NOT EXISTS lca_channel_state(
                  device_id TEXT NOT NULL, channel_key TEXT NOT NULL, state TEXT NOT NULL,
                  brightness REAL, first_observed_at TEXT NOT NULL, last_observed_at TEXT NOT NULL,
                  last_changed_at TEXT, updated_at TEXT NOT NULL,
                  PRIMARY KEY(device_id, channel_key));

                CREATE TABLE IF NOT EXISTS lca_messages(
                  message_id TEXT PRIMARY KEY, device_id TEXT NOT NULL, topic TEXT,
                  occurred_at TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_lca_messages_time ON lca_messages(occurred_at DESC);

                CREATE TABLE IF NOT EXISTS lca_metadata(
                  key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);

                CREATE TABLE IF NOT EXISTS lca_device_exclusions(
                  device_id TEXT PRIMARY KEY, reason TEXT,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS lca_light_assets(
                  light_id TEXT PRIMARY KEY, site_id TEXT NOT NULL, name TEXT NOT NULL, location_name TEXT,
                  source_channel_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS lca_scenes(
                  scene_id TEXT PRIMARY KEY, site_id TEXT NOT NULL, name TEXT NOT NULL, description TEXT,
                  auto_learn INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS lca_scene_executions(
                  execution_id TEXT PRIMARY KEY, scene_id TEXT NOT NULL, trigger_device_id TEXT NOT NULL, trigger_channel_key TEXT NOT NULL,
                  occurred_at TEXT NOT NULL, observation_until TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS lca_scene_effects(
                  scene_id TEXT NOT NULL, light_id TEXT NOT NULL, resulting_state TEXT NOT NULL, observations INTEGER NOT NULL DEFAULT 0,
                  executions INTEGER NOT NULL DEFAULT 0, confidence REAL NOT NULL DEFAULT 0, last_seen TEXT, updated_at TEXT NOT NULL,
                  PRIMARY KEY(scene_id,light_id,resulting_state));
                """
            )
            self._ensure_column(c, "lca_channels", "relationship_type", "TEXT NOT NULL DEFAULT 'unassigned'")
            self._ensure_column(c, "lca_channels", "light_asset_id", "TEXT")
            self._ensure_column(c, "lca_channels", "parallel_source_channel_id", "TEXT")
            self._ensure_column(c, "lca_channels", "scene_id", "TEXT")
            self._ensure_column(c, "lca_events", "cause_type", "TEXT")
            self._ensure_column(c, "lca_events", "cause_id", "TEXT")
            self._ensure_column(c, "lca_events", "causal_confidence", "REAL")
            self._ensure_column(c, "lca_events", "source_entity", "TEXT")
            self._ensure_column(c, "lca_events", "source_device_ref", "TEXT")
            self._ensure_column(c, "lca_events", "source_channel_ref", "TEXT")
            self._ensure_column(c, "lca_events", "requested_state", "TEXT")
            self._ensure_column(c, "lca_events", "target_entity", "TEXT")
            self._ensure_column(c, "lca_events", "circuit_id", "TEXT")
            self._ensure_column(c, "lca_events", "interaction_kind", "TEXT")
            self._ensure_column(c, "lca_events", "origin_mode", "TEXT")
            self._ensure_column(c, "lca_events", "ha_context_id", "TEXT")
            self._ensure_column(c, "lca_events", "ha_parent_id", "TEXT")
            self._ensure_column(c, "lca_events", "ha_user_id", "TEXT")
            self._ensure_column(c, "lca_events", "point_role", "TEXT")
            self._ensure_column(c, "lca_events", "point_position", "TEXT")
            self._ensure_column(c, "lca_events", "effect_event_id", "TEXT")
            self._ensure_column(c, "lca_events", "effect_confirmed_at", "TEXT")
            self._ensure_column(c, "lca_events", "confirmation_latency_ms", "INTEGER")
            self._ensure_column(c, "lca_events", "interaction_status", "TEXT")
            self._ensure_column(c, "lca_light_assets", "circuit_id", "TEXT")
            self._ensure_column(c, "lca_light_assets", "archived_at", "TEXT")
            self._ensure_column(c, "lca_light_assets", "merged_into_light_id", "TEXT")
            c.execute("""CREATE TABLE IF NOT EXISTS lca_light_merge_log(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_light_id TEXT NOT NULL,
                target_light_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                merged_at TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}')""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_lca_light_assets_circuit ON lca_light_assets(site_id,circuit_id)")
            c.execute("""CREATE TABLE IF NOT EXISTS lca_pending_interactions(
                lca_event_id TEXT PRIMARY KEY,
                circuit_id TEXT,
                requested_state TEXT,
                occurred_at TEXT NOT NULL,
                item_json TEXT NOT NULL,
                created_at TEXT NOT NULL)""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_lca_pending_interactions_time ON lca_pending_interactions(occurred_at)")

    @staticmethod
    def _ensure_column(c, table, column, declaration):
        names={r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in names:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    def _migrate_010_history(self):
        """Remove only the synthetic state history generated by LCA 0.1.0.

        Interactions and availability evidence are retained. The migration runs
        once and initializes current state again from fresh MQTT observations.
        """
        key = "relevant_event_processing_011"
        with self.db.connect() as c:
            done = c.execute("SELECT value FROM lca_metadata WHERE key=?", (key,)).fetchone()
            if done:
                return
            c.execute("DELETE FROM lca_sessions")
            c.execute("DELETE FROM lca_events WHERE kind='state'")
            c.execute("DELETE FROM lca_channel_state")
            now = datetime.now(timezone.utc).isoformat()
            c.execute(
                "INSERT INTO lca_metadata(key,value,updated_at) VALUES(?,?,?)",
                (key, "completed", now),
            )

    def _migrate_035_channel_aliases(self):
        """Collapse duplicated aliases exposed by some multi-gang devices.

        Models that publish l1/left, l2/center and l3/right are represented as
        three physical channels, not six analytical channels. Existing
        configuration and history are merged into the canonical l1/l2/l3 keys.
        """
        key = "lca_channel_alias_normalization_035"
        pairs = (("l1", "left"), ("l2", "center"), ("l3", "right"))
        with self.db.connect() as c:
            if c.execute("SELECT value FROM lca_metadata WHERE key=?", (key,)).fetchone():
                return
            devices = [r[0] for r in c.execute("SELECT device_id FROM lca_devices").fetchall()]
            for did in devices:
                for canonical, alias in pairs:
                    main = c.execute("SELECT * FROM lca_channels WHERE device_id=? AND channel_key=?", (did, canonical)).fetchone()
                    duplicate = c.execute("SELECT * FROM lca_channels WHERE device_id=? AND channel_key=?", (did, alias)).fetchone()
                    if not main or not duplicate:
                        continue
                    # Preserve whichever side was actually configured, while
                    # keeping the numeric channel as the canonical identity.
                    def pick(field, default=None):
                        a = main[field] if field in main.keys() else None
                        b = duplicate[field] if field in duplicate.keys() else None
                        if a not in (None, "", default):
                            return a
                        return b if b not in (None, "") else a
                    enabled = 1 if bool(main["enabled"]) or bool(duplicate["enabled"]) else 0
                    relationship = pick("relationship_type", "unassigned") or "unassigned"
                    values = {
                        "enabled": enabled,
                        "name": pick("name"),
                        "interaction_point": pick("interaction_point"),
                        "location_id": pick("location_id"),
                        "location_name": pick("location_name"),
                        "adjacent_location_id": pick("adjacent_location_id"),
                        "adjacent_location_name": pick("adjacent_location_name"),
                        "direction_hint": pick("direction_hint"),
                        "related_light_id": pick("related_light_id"),
                        "related_light_name": pick("related_light_name"),
                        "virtual_parallel_group": pick("virtual_parallel_group"),
                        "relationship_type": relationship,
                        "light_asset_id": pick("light_asset_id"),
                        "parallel_source_channel_id": pick("parallel_source_channel_id"),
                        "scene_id": pick("scene_id"),
                    }
                    c.execute("""UPDATE lca_channels SET enabled=:enabled,name=:name,interaction_point=:interaction_point,
                        location_id=:location_id,location_name=:location_name,adjacent_location_id=:adjacent_location_id,
                        adjacent_location_name=:adjacent_location_name,direction_hint=:direction_hint,
                        related_light_id=:related_light_id,related_light_name=:related_light_name,
                        virtual_parallel_group=:virtual_parallel_group,relationship_type=:relationship_type,
                        light_asset_id=:light_asset_id,parallel_source_channel_id=:parallel_source_channel_id,
                        scene_id=:scene_id,updated_at=:updated_at WHERE device_id=:device_id AND channel_key=:channel_key""",
                        {**values, "updated_at": datetime.now(timezone.utc).isoformat(), "device_id": did, "channel_key": canonical})
                    # Keep historical evidence under the physical channel.
                    c.execute("UPDATE lca_events SET channel_key=? WHERE device_id=? AND channel_key=?", (canonical, did, alias))
                    c.execute("UPDATE lca_sessions SET channel_key=? WHERE device_id=? AND channel_key=?", (canonical, did, alias))
                    alias_state = c.execute("SELECT * FROM lca_channel_state WHERE device_id=? AND channel_key=?", (did, alias)).fetchone()
                    main_state = c.execute("SELECT * FROM lca_channel_state WHERE device_id=? AND channel_key=?", (did, canonical)).fetchone()
                    if alias_state and not main_state:
                        c.execute("UPDATE lca_channel_state SET channel_key=? WHERE device_id=? AND channel_key=?", (canonical, did, alias))
                    elif alias_state:
                        c.execute("DELETE FROM lca_channel_state WHERE device_id=? AND channel_key=?", (did, alias))
                    c.execute("DELETE FROM lca_channels WHERE device_id=? AND channel_key=?", (did, alias))
                self._refresh_configuration_status(c, did)
            now = datetime.now(timezone.utc).isoformat()
            c.execute("INSERT INTO lca_metadata(key,value,updated_at) VALUES(?,?,?)", (key, "completed", now))

    def _migrate_036_logical_circuits(self):
        """Consolidate duplicated logical lights into canonical circuits.

        A circuit is the illuminated load. Direct and parallel points are only
        interaction points and must reference the same logical circuit. Older
        versions could create one light asset per direct entity, especially
        when friendly entity names were used. This migration merges safe
        duplicates while preserving channels, sessions, events and audit data.
        """
        key = "lca_logical_circuit_consolidation_036"
        with self.db.connect() as c:
            if c.execute("SELECT value FROM lca_metadata WHERE key=?", (key,)).fetchone():
                return
            now = datetime.now(timezone.utc).isoformat()
            lights = [dict(r) for r in c.execute(
                "SELECT * FROM lca_light_assets WHERE archived_at IS NULL ORDER BY created_at,light_id"
            ).fetchall()]

            def norm(value):
                return self._normalize_identifier(value)

            # Populate stable circuit identifiers first.
            for light in lights:
                name_key = norm(light.get("name")) or norm(light.get("light_id"))
                location_key = norm(light.get("location_name"))
                circuit_id = f"{location_key}_{name_key}" if location_key else name_key
                c.execute(
                    "UPDATE lca_light_assets SET circuit_id=?,updated_at=? WHERE light_id=?",
                    (circuit_id, now, light["light_id"]),
                )
                light["circuit_id"] = circuit_id

            # Group by semantic light name. Merge exact location duplicates and
            # location-less records only when a single located circuit exists.
            by_name = {}
            for light in lights:
                by_name.setdefault(norm(light.get("name")), []).append(light)

            for name_key, group in by_name.items():
                if not name_key or len(group) < 2:
                    continue
                located = {norm(x.get("location_name")) for x in group if norm(x.get("location_name"))}
                buckets = {}
                for light in group:
                    loc = norm(light.get("location_name"))
                    if not loc and len(located) == 1:
                        loc = next(iter(located))
                    buckets.setdefault(loc, []).append(light)

                for loc_key, duplicates in buckets.items():
                    if len(duplicates) < 2 or not loc_key:
                        continue
                    # Prefer the asset with a location, then the one with more
                    # configured points, then the oldest stable identifier.
                    scored = []
                    for light in duplicates:
                        point_count = c.execute(
                            "SELECT COUNT(*) FROM lca_channels WHERE light_asset_id=?",
                            (light["light_id"],),
                        ).fetchone()[0]
                        score = (1 if light.get("location_name") else 0, point_count, -len(light["light_id"]))
                        scored.append((score, light))
                    scored.sort(key=lambda x: x[0], reverse=True)
                    target = scored[0][1]
                    target_id = target["light_id"]
                    target_location = target.get("location_name") or next(
                        (x.get("location_name") for x in duplicates if x.get("location_name")), None
                    )
                    canonical_circuit = f"{loc_key}_{name_key}"
                    c.execute(
                        "UPDATE lca_light_assets SET circuit_id=?,location_name=COALESCE(location_name,?),updated_at=? WHERE light_id=?",
                        (canonical_circuit, target_location, now, target_id),
                    )
                    for _, source in scored[1:]:
                        source_id = source["light_id"]
                        c.execute("UPDATE lca_channels SET light_asset_id=?,related_light_id=?,related_light_name=COALESCE(related_light_name,?),updated_at=? WHERE light_asset_id=?",
                                  (target_id, target_id, target.get("name"), now, source_id))
                        c.execute("UPDATE lca_sessions SET related_light_id=? WHERE related_light_id=?", (target_id, source_id))
                        c.execute("UPDATE lca_events SET related_light_id=?,related_light_name=COALESCE(related_light_name,?) WHERE related_light_id=?",
                                  (target_id, target.get("name"), source_id))
                        # Merge scene statistics without losing observations.
                        effects = c.execute("SELECT * FROM lca_scene_effects WHERE light_id=?", (source_id,)).fetchall()
                        for effect in effects:
                            existing = c.execute("SELECT * FROM lca_scene_effects WHERE scene_id=? AND light_id=? AND resulting_state=?",
                                                 (effect["scene_id"], target_id, effect["resulting_state"])).fetchone()
                            if existing:
                                observations = int(existing["observations"] or 0) + int(effect["observations"] or 0)
                                executions = max(int(existing["executions"] or 0), int(effect["executions"] or 0))
                                confidence = (observations / executions) if executions else 0
                                c.execute("UPDATE lca_scene_effects SET observations=?,executions=?,confidence=?,last_seen=MAX(COALESCE(last_seen,''),?),updated_at=? WHERE scene_id=? AND light_id=? AND resulting_state=?",
                                          (observations, executions, confidence, effect["last_seen"], now, effect["scene_id"], target_id, effect["resulting_state"]))
                            else:
                                c.execute("UPDATE lca_scene_effects SET light_id=?,updated_at=? WHERE scene_id=? AND light_id=? AND resulting_state=?",
                                          (target_id, now, effect["scene_id"], source_id, effect["resulting_state"]))
                        c.execute("DELETE FROM lca_scene_effects WHERE light_id=?", (source_id,))
                        c.execute("INSERT INTO lca_light_merge_log(source_light_id,target_light_id,reason,merged_at,details_json) VALUES(?,?,?,?,?)",
                                  (source_id, target_id, "same_name_and_location", now,
                                   json.dumps({"name": source.get("name"), "location": source.get("location_name")}, ensure_ascii=False)))
                        c.execute("DELETE FROM lca_light_assets WHERE light_id=?", (source_id,))

            # Recalculate identifiers after merges and updated locations.
            remaining = c.execute("SELECT light_id,name,location_name FROM lca_light_assets WHERE archived_at IS NULL").fetchall()
            for light in remaining:
                name_key = norm(light["name"]) or norm(light["light_id"])
                location_key = norm(light["location_name"])
                circuit_id = f"{location_key}_{name_key}" if location_key else name_key
                c.execute("UPDATE lca_light_assets SET circuit_id=?,updated_at=? WHERE light_id=?", (circuit_id, now, light["light_id"]))
            c.execute("INSERT INTO lca_metadata(key,value,updated_at) VALUES(?,?,?)", (key, "completed", now))

    def _migrate_037_infrastructure_identity(self):
        """Hide synthetic devices created from explicit interaction aliases.

        LCA infrastructure is defined by the real MQTT device/topic and its
        canonical channels (L1, L2, ...). Friendly Home Assistant entity names
        carried by seiden/lca/interactions are diagnostic metadata only and
        must never become standalone infrastructure devices.
        """
        key = "lca_infrastructure_identity_037"
        with self.db.connect() as c:
            if c.execute("SELECT value FROM lca_metadata WHERE key=?", (key,)).fetchone():
                return
            now = datetime.now(timezone.utc).isoformat()
            rows = c.execute("SELECT device_id,topic,sample_payload_json FROM lca_devices WHERE status<>'ignored'").fetchall()
            for row in rows:
                topic = str(row["topic"] or "").strip().lower().rstrip("/")
                sample = str(row["sample_payload_json"] or "").lower()
                synthetic = topic == "seiden/lca/interactions" or '"event_type": "lighting_interaction"' in sample or '"event_type":"lighting_interaction"' in sample
                if not synthetic:
                    continue
                did = row["device_id"]
                # A real infrastructure device has state evidence. Never hide it
                # merely because it also appeared in an interaction payload.
                has_state = c.execute("SELECT 1 FROM lca_events WHERE device_id=? AND kind='state_change' LIMIT 1", (did,)).fetchone()
                if has_state:
                    continue
                c.execute("UPDATE lca_devices SET status='ignored',updated_at=? WHERE device_id=?", (now, did))
                c.execute("INSERT INTO lca_device_exclusions(device_id,reason,created_at,updated_at) VALUES(?,?,?,?) ON CONFLICT(device_id) DO UPDATE SET reason=excluded.reason,updated_at=excluded.updated_at",
                          (did, "synthetic_interaction_alias_037", now, now))
            c.execute("INSERT INTO lca_metadata(key,value,updated_at) VALUES(?,?,?)", (key, "completed", now))

    def ingest(self, items):
        inserted_events = 0
        if not items:
            return inserted_events
        with self.db.connect() as c:
            for item in items:
                now = datetime.now(timezone.utc).isoformat()
                if item.get("kind") == "interaction":
                    resolved = self._resolve_interaction_source(c, item)
                    if resolved:
                        item = dict(item)
                        item["device_id"] = resolved["device_id"]
                        item["device_name"] = resolved["name"]
                        item["channel"] = resolved["resolved_channel_key"] or item.get("source_channel") or item.get("channel")
                    else:
                        # Never create infrastructure from a friendly HA entity
                        # such as switch.sala_painel_virtual. Queue the explicit
                        # interaction until the real Zigbee2MQTT state change
                        # identifies device + canonical channel.
                        self._queue_pending_interaction(c, item, now)
                        continue
                did = item["device_id"]
                ch = item.get("channel")
                blocked = c.execute(
                    "SELECT 1 FROM lca_device_exclusions WHERE device_id=?", (did,)
                ).fetchone()
                ignored = c.execute(
                    "SELECT 1 FROM lca_devices WHERE device_id=? AND status='ignored'", (did,)
                ).fetchone()
                if blocked or ignored:
                    continue
                self._upsert_device(c, item, now)
                if ch:
                    self._upsert_channel(c, did, ch, now)
                cfg = (
                    c.execute(
                        "SELECT * FROM lca_channels WHERE device_id=? AND channel_key=?",
                        (did, ch),
                    ).fetchone()
                    if ch
                    else None
                )

                # Devices may expose relays, outlets or auxiliary gangs that do
                # not belong to the analytical scope of the LCA. Disabled
                # channels are discarded before message storage, baselining,
                # sessions and analytical events. Other channels in the same
                # device continue to be processed normally.
                if cfg is not None and not bool(cfg["enabled"]):
                    continue

                self._record_message(c, item, now)
                kind = item["kind"]
                if kind == "state":
                    if self._process_state(c, item, cfg, now):
                        inserted_events += 1
                        self._resolve_pending_with_state(c, item, cfg, now)
                elif kind == "availability":
                    if self._process_availability(c, item, cfg, now):
                        inserted_events += 1
                elif kind == "interaction":
                    if self._process_interaction(c, item, cfg, now):
                        inserted_events += 1
        return inserted_events

    @staticmethod
    def _normalize_identifier(value):
        import re, unicodedata
        text=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode().lower()
        text=re.sub(r"^(switch\.|light\.)", "", text)
        text=re.sub(r"^(gr_|grupo_)", "", text)
        text=re.sub(r"_(real|virtual|retorno)$", "", text)
        return re.sub(r"[^a-z0-9]+", "_", text).strip("_")

    @classmethod
    def _resolve_interaction_source(cls, c, item):
        ref=str(item.get("source_device") or "").strip().lower()
        source_channel=str(item.get("source_channel") or "").strip().lower()

        # 1) Exact infrastructure identity. This is the preferred path when
        # the publisher already sends the Zigbee2MQTT device + L1/L2/... .
        if ref:
            row=c.execute("""SELECT d.*,ch.channel_key resolved_channel_key,ch.channel_id resolved_channel_id
                FROM lca_devices d LEFT JOIN lca_channels ch ON ch.device_id=d.device_id AND lower(ch.channel_key)=?
                WHERE d.status<>'ignored' AND lower(COALESCE(d.topic,''))<>'seiden/lca/interactions'
                  AND (lower(d.name)=? OR lower(d.device_id)=? OR lower(COALESCE(d.topic,'')) LIKE ?)
                ORDER BY CASE WHEN lower(d.name)=? THEN 0 WHEN lower(d.device_id)=? THEN 1 ELSE 2 END
                LIMIT 1""",(source_channel,ref,ref,"%/"+ref,ref,ref)).fetchone()
            if row and (source_channel or row["resolved_channel_key"]):
                return row

        # 2) Friendly entity names are intentionally ignored. Resolve the
        # physical point from the real MQTT state transition associated with
        # the configured logical circuit.
        circuit=cls._normalize_identifier(item.get("circuit_id"))
        requested=str(item.get("requested_state") or "").lower()
        if circuit and requested in {"on","off"}:
            t=cls._parse_time(item.get("occurred_at"))
            lo=(t-timedelta(seconds=2)).isoformat(); hi=(t+timedelta(seconds=1)).isoformat()
            rows=c.execute("""SELECT d.*,ch.channel_key resolved_channel_key,ch.channel_id resolved_channel_id,
                       ch.relationship_type,l.circuit_id,e.occurred_at effect_at
                FROM lca_events e
                JOIN lca_devices d ON d.device_id=e.device_id AND d.status<>'ignored'
                JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key AND ch.enabled=1
                LEFT JOIN lca_light_assets l ON l.light_id=ch.light_asset_id
                WHERE e.kind='state_change' AND e.state=? AND e.occurred_at BETWEEN ? AND ?
                ORDER BY ABS(julianday(e.occurred_at)-julianday(?))""",
                (requested,lo,hi,item.get("occurred_at"))).fetchall()
            for row in rows:
                rc=cls._normalize_identifier(row["circuit_id"])
                if rc and (circuit==rc or circuit.endswith("_"+rc) or rc.endswith("_"+circuit)):
                    return row

        # 3) If a circuit has exactly one configured interaction point, it is
        # safe to resolve without relying on entity naming. Multiple points are
        # left pending until their real state transition identifies the source.
        if circuit:
            candidates=c.execute("""SELECT d.*,ch.channel_key resolved_channel_key,ch.channel_id resolved_channel_id,l.circuit_id
                FROM lca_channels ch JOIN lca_devices d ON d.device_id=ch.device_id
                JOIN lca_light_assets l ON l.light_id=ch.light_asset_id
                WHERE ch.enabled=1 AND d.status<>'ignored'
                  AND ch.relationship_type IN ('direct','parallel') AND l.archived_at IS NULL""").fetchall()
            matched=[r for r in candidates if cls._normalize_identifier(r["circuit_id"]) and
                     (circuit==cls._normalize_identifier(r["circuit_id"]) or circuit.endswith("_"+cls._normalize_identifier(r["circuit_id"])) or cls._normalize_identifier(r["circuit_id"]).endswith("_"+circuit))]
            if len(matched)==1:
                return matched[0]
        return None

    @staticmethod
    def _queue_pending_interaction(c, item, now):
        c.execute("""INSERT INTO lca_pending_interactions(lca_event_id,circuit_id,requested_state,occurred_at,item_json,created_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(lca_event_id) DO UPDATE SET item_json=excluded.item_json,created_at=excluded.created_at""",
            (item["lca_event_id"], item.get("circuit_id"), item.get("requested_state"), item["occurred_at"], json.dumps(item,ensure_ascii=False), now))
        cutoff=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
        c.execute("DELETE FROM lca_pending_interactions WHERE created_at<?", (cutoff,))

    def _resolve_pending_with_state(self, c, state_item, cfg, now):
        if not cfg or not cfg["light_asset_id"] or state_item.get("state") not in {"on","off"}:
            return
        light=c.execute("SELECT circuit_id FROM lca_light_assets WHERE light_id=?", (cfg["light_asset_id"],)).fetchone()
        if not light or not light["circuit_id"]:
            return
        circuit=self._normalize_identifier(light["circuit_id"])
        t=self._parse_time(state_item["occurred_at"]); lo=(t-timedelta(seconds=1)).isoformat(); hi=(t+timedelta(seconds=3)).isoformat()
        rows=c.execute("""SELECT * FROM lca_pending_interactions WHERE requested_state=? AND occurred_at BETWEEN ? AND ? ORDER BY occurred_at""",
                       (state_item["state"],lo,hi)).fetchall()
        for row in rows:
            pending_circuit=self._normalize_identifier(row["circuit_id"])
            if not pending_circuit or not (pending_circuit==circuit or pending_circuit.endswith("_"+circuit) or circuit.endswith("_"+pending_circuit)):
                continue
            item=json.loads(row["item_json"]); item["device_id"]=state_item["device_id"]
            dev=c.execute("SELECT name FROM lca_devices WHERE device_id=?", (state_item["device_id"],)).fetchone()
            item["device_name"]=dev["name"] if dev else state_item.get("device_name")
            item["channel"]=state_item.get("channel")
            self._record_message(c,item,now)
            self._process_interaction(c,item,cfg,now)
            c.execute("DELETE FROM lca_pending_interactions WHERE lca_event_id=?", (row["lca_event_id"],))
            break

    def _upsert_device(self, c, item, now):
        c.execute(
            """INSERT INTO lca_devices(device_id,site_id,name,topic,model,manufacturer,first_seen,last_seen,sample_payload_json,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(device_id) DO UPDATE SET
                 name=COALESCE(NULLIF(excluded.name,''),lca_devices.name),
                 topic=COALESCE(excluded.topic,lca_devices.topic),
                 model=COALESCE(excluded.model,lca_devices.model),
                 manufacturer=COALESCE(excluded.manufacturer,lca_devices.manufacturer),
                 last_seen=excluded.last_seen,
                 sample_payload_json=excluded.sample_payload_json,
                 updated_at=excluded.updated_at""",
            (
                item["device_id"], self.db.site_id, item["device_name"], item.get("topic"),
                item.get("model"), item.get("manufacturer"), item["occurred_at"],
                item["occurred_at"], json.dumps(item["payload"], ensure_ascii=False), now,
            ),
        )

    @staticmethod
    def _upsert_channel(c, did, ch, now):
        cid = f"{did}:{ch}"
        c.execute(
            """INSERT INTO lca_channels(channel_id,device_id,channel_key,created_at,updated_at)
               VALUES(?,?,?,?,?) ON CONFLICT(device_id,channel_key)
               DO UPDATE SET updated_at=excluded.updated_at""",
            (cid, did, ch, now, now),
        )

    @staticmethod
    def _record_message(c, item, now):
        message_id = item.get("message_id") or item["lca_event_id"].split(":", 1)[0]
        try:
            c.execute(
                "INSERT INTO lca_messages(message_id,device_id,topic,occurred_at,payload_json,created_at) VALUES(?,?,?,?,?,?)",
                (message_id, item["device_id"], item.get("topic"), item["occurred_at"],
                 json.dumps(item["payload"], ensure_ascii=False), now),
            )
        except sqlite3.IntegrityError:
            pass

    def _process_state(self, c, item, cfg, now):
        did, ch, new_state = item["device_id"], item.get("channel") or "main", item["state"]
        previous = c.execute(
            "SELECT * FROM lca_channel_state WHERE device_id=? AND channel_key=?",
            (did, ch),
        ).fetchone()

        # First observation establishes baseline only. It is not an event.
        if previous is None:
            c.execute(
                """INSERT INTO lca_channel_state(device_id,channel_key,state,brightness,first_observed_at,last_observed_at,last_changed_at,updated_at)
                   VALUES(?,?,?,?,?,?,NULL,?)""",
                (did, ch, new_state, item.get("brightness"), item["occurred_at"], item["occurred_at"], now),
            )
            return False

        # Repeated state report: update telemetry timestamp, produce no event.
        if previous["state"] == new_state:
            c.execute(
                """UPDATE lca_channel_state SET brightness=COALESCE(?,brightness),last_observed_at=?,updated_at=?
                   WHERE device_id=? AND channel_key=?""",
                (item.get("brightness"), item["occurred_at"], now, did, ch),
            )
            return False

        event = dict(item)
        # Associate state changes with the most recent scene execution in the
        # three-second causal window, preventing scene effects from looking like
        # independent route evidence.
        scene_exec = c.execute("SELECT * FROM lca_scene_executions WHERE occurred_at<=? AND observation_until>=? ORDER BY occurred_at DESC LIMIT 1", (item["occurred_at"], item["occurred_at"])).fetchone()
        if scene_exec:
            event["cause_type"]="scene"; event["cause_id"]=scene_exec["scene_id"]; event["causal_confidence"]=0.95
        event["kind"] = "state_change"
        event["action"] = f"{previous['state']}->{new_state}"
        event["lca_event_id"] = item["lca_event_id"] + ":change"
        if not self._insert_event(c, event, cfg, now):
            return False

        c.execute(
            """UPDATE lca_channel_state SET state=?,brightness=?,last_observed_at=?,last_changed_at=?,updated_at=?
               WHERE device_id=? AND channel_key=?""",
            (new_state, item.get("brightness"), item["occurred_at"], item["occurred_at"], now, did, ch),
        )
        self._update_session(c, event, cfg, now)
        if not event.get("cause_type"):
            self._correlate_pending_interaction(c,event,cfg,now)
        if event.get("cause_type") == "scene" and cfg and cfg["light_asset_id"]:
            self._learn_scene_effect(c,event["cause_id"],cfg["light_asset_id"],new_state,item["occurred_at"],now)
        return True

    def _process_availability(self, c, item, cfg, now):
        current = c.execute("SELECT availability FROM lca_devices WHERE device_id=?", (item["device_id"],)).fetchone()
        previous = current["availability"] if current else "unknown"
        c.execute(
            "UPDATE lca_devices SET availability=?,updated_at=? WHERE device_id=?",
            (item["state"], now, item["device_id"]),
        )
        if previous in {"unknown", item["state"]}:
            return False
        event = dict(item)
        event["kind"] = "availability_change"
        event["action"] = f"{previous}->{item['state']}"
        return self._insert_event(c, event, cfg, now)

    def _process_interaction(self, c, item, cfg, now):
        event=dict(item)
        event["point_role"] = cfg["relationship_type"] if cfg else None
        event["point_position"] = None
        if cfg:
            dev=c.execute("SELECT position_label FROM lca_devices WHERE device_id=?",(item["device_id"],)).fetchone()
            event["point_position"] = dev["position_label"] if dev else None
        event["interaction_status"] = "pending_confirmation"

        # Scene triggers are analytical parent events. Their downstream state
        # changes are grouped during a short observation window.
        if cfg is not None and cfg["relationship_type"] == "scene" and cfg["scene_id"]:
            execution_id = item["lca_event_id"] + ":scene_execution"
            occurred = self._parse_time(item["occurred_at"])
            until = (occurred + timedelta(seconds=3)).isoformat()
            c.execute("INSERT OR IGNORE INTO lca_scene_executions(execution_id,scene_id,trigger_device_id,trigger_channel_key,occurred_at,observation_until,created_at) VALUES(?,?,?,?,?,?,?)",
                      (execution_id,cfg["scene_id"],item["device_id"],item.get("channel") or "default",item["occurred_at"],until,now))
            event["cause_type"]="scene"; event["cause_id"]=cfg["scene_id"]; event["causal_confidence"]=1.0
            event["interaction_status"]="scene_observation"

        cutoff = self._parse_time(item["occurred_at"]) - timedelta(seconds=2)
        recent = c.execute(
            """SELECT occurred_at FROM lca_events
               WHERE device_id=? AND channel_key IS ? AND kind='interaction' AND action=?
               ORDER BY occurred_at DESC LIMIT 1""",
            (item["device_id"], item.get("channel"), item.get("action")),
        ).fetchone()
        if recent and self._parse_time(recent["occurred_at"]) >= cutoff:
            return False
        # A direct point event is emitted from the state transition itself.
        # Therefore it is already a valid effect confirmation, even when the
        # entity has a free-form name and no separate technical event exists.
        if cfg is not None and cfg["relationship_type"] == "direct" and item.get("requested_state") in {"on","off"}:
            event["interaction_status"] = "confirmed"
            event["effect_confirmed_at"] = item["occurred_at"]
            event["confirmation_latency_ms"] = 0
            event["causal_confidence"] = 1.0
        inserted=self._insert_event(c,event,cfg,now)
        if inserted and event.get("interaction_status") != "confirmed":
            self._correlate_existing_effect(c,event,cfg,now)
        return inserted

    def _correlate_existing_effect(self,c,item,cfg,now):
        if not cfg or not cfg["light_asset_id"] or item.get("requested_state") not in {"on","off"}:return
        t=self._parse_time(item["occurred_at"])
        lo=(t-timedelta(seconds=2)).isoformat(); hi=(t+timedelta(seconds=1)).isoformat()
        effect=c.execute("""SELECT e.lca_event_id,e.occurred_at FROM lca_events e
            LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
            WHERE e.kind='state_change' AND ch.light_asset_id=? AND e.state=? AND e.occurred_at BETWEEN ? AND ?
            ORDER BY ABS(julianday(e.occurred_at)-julianday(?)) LIMIT 1""",
            (cfg["light_asset_id"],item["requested_state"],lo,hi,item["occurred_at"])).fetchone()
        if effect:self._confirm_interaction(c,item["lca_event_id"],effect["lca_event_id"],effect["occurred_at"],item["occurred_at"],now)

    def _correlate_pending_interaction(self,c,event,cfg,now):
        if not cfg or not cfg["light_asset_id"]:return
        t=self._parse_time(event["occurred_at"]); lo=(t-timedelta(seconds=3)).isoformat()
        interaction=c.execute("""SELECT e.lca_event_id,e.occurred_at FROM lca_events e
            LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
            WHERE e.kind='interaction' AND ch.light_asset_id=? AND e.requested_state=?
              AND e.occurred_at BETWEEN ? AND ? AND COALESCE(e.interaction_status,'pending_confirmation')='pending_confirmation'
            ORDER BY e.occurred_at DESC LIMIT 1""",
            (cfg["light_asset_id"],event["state"],lo,event["occurred_at"])).fetchone()
        if interaction:self._confirm_interaction(c,interaction["lca_event_id"],event["lca_event_id"],event["occurred_at"],interaction["occurred_at"],now)

    @classmethod
    def _confirm_interaction(cls,c,interaction_id,effect_id,effect_at,interaction_at,now):
        latency=max(0,int((cls._parse_time(effect_at)-cls._parse_time(interaction_at)).total_seconds()*1000))
        c.execute("""UPDATE lca_events SET effect_event_id=?,effect_confirmed_at=?,confirmation_latency_ms=?,interaction_status='confirmed'
            WHERE lca_event_id=?""",(effect_id,effect_at,latency,interaction_id))
        c.execute("""UPDATE lca_events SET cause_type='interaction',cause_id=?,causal_confidence=1.0 WHERE lca_event_id=? AND cause_type IS NULL""",(interaction_id,effect_id))

    @staticmethod
    def _learn_scene_effect(c, scene_id, light_id, state, occurred_at, now):
        executions=c.execute("SELECT COUNT(*) FROM lca_scene_executions WHERE scene_id=?",(scene_id,)).fetchone()[0]
        row=c.execute("SELECT observations FROM lca_scene_effects WHERE scene_id=? AND light_id=? AND resulting_state=?",(scene_id,light_id,state)).fetchone()
        observations=(row["observations"] if row else 0)+1
        confidence=observations/max(1,executions)
        c.execute("INSERT INTO lca_scene_effects(scene_id,light_id,resulting_state,observations,executions,confidence,last_seen,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(scene_id,light_id,resulting_state) DO UPDATE SET observations=excluded.observations,executions=excluded.executions,confidence=excluded.confidence,last_seen=excluded.last_seen,updated_at=excluded.updated_at",(scene_id,light_id,state,observations,executions,confidence,occurred_at,now))

    @staticmethod
    def _parse_time(value):
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)

    @staticmethod
    def _insert_event(c, item, cfg, now):
        try:
            c.execute(
                """INSERT INTO lca_events(lca_event_id,device_id,channel_key,kind,state,action,brightness,occurred_at,
                   origin_location_id,origin_location_name,adjacent_location_id,adjacent_location_name,direction_hint,
                   related_light_id,related_light_name,virtual_parallel_group,cause_type,cause_id,causal_confidence,
                   source_entity,source_device_ref,source_channel_ref,requested_state,target_entity,circuit_id,interaction_kind,
                   origin_mode,ha_context_id,ha_parent_id,ha_user_id,point_role,point_position,effect_event_id,
                   effect_confirmed_at,confirmation_latency_ms,interaction_status,payload_json,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    item["lca_event_id"], item["device_id"], item.get("channel"), item["kind"],
                    item.get("state"), item.get("action"), item.get("brightness"), item["occurred_at"],
                    cfg["location_id"] if cfg else None, cfg["location_name"] if cfg else None,
                    cfg["adjacent_location_id"] if cfg else None, cfg["adjacent_location_name"] if cfg else None,
                    cfg["direction_hint"] if cfg else None, cfg["related_light_id"] if cfg else None,
                    cfg["related_light_name"] if cfg else None, cfg["virtual_parallel_group"] if cfg else None,
                    item.get("cause_type"), item.get("cause_id"), item.get("causal_confidence"),
                    item.get("source_entity"),item.get("source_device"),item.get("source_channel"),item.get("requested_state"),
                    item.get("target_entity"),item.get("circuit_id"),item.get("interaction_kind"),item.get("origin_mode"),
                    item.get("ha_context_id"),item.get("ha_parent_id"),item.get("ha_user_id"),item.get("point_role"),
                    item.get("point_position"),item.get("effect_event_id"),item.get("effect_confirmed_at"),
                    item.get("confirmation_latency_ms"),item.get("interaction_status"),json.dumps(item["payload"], ensure_ascii=False), now,
                ),
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def _update_session(self, c, item, cfg, now):
        did, ch = item["device_id"], item.get("channel")
        light = cfg["related_light_id"] if cfg else None
        open_row = c.execute(
            """SELECT * FROM lca_sessions WHERE device_id=? AND channel_key IS ? AND status='open'
               ORDER BY started_at DESC LIMIT 1""",
            (did, ch),
        ).fetchone()
        if item["state"] == "on" and not open_row:
            sid = f"{did}:{ch or 'main'}:{item['occurred_at']}"
            c.execute(
                """INSERT OR IGNORE INTO lca_sessions(session_id,device_id,channel_key,related_light_id,started_at,start_event_id,status,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (sid, did, ch, light, item["occurred_at"], item["lca_event_id"], "open", now),
            )
        elif item["state"] == "off" and open_row:
            start = self._parse_time(open_row["started_at"])
            end = self._parse_time(item["occurred_at"])
            duration = max(0, int((end - start).total_seconds()))
            c.execute(
                """UPDATE lca_sessions SET ended_at=?,duration_seconds=?,end_event_id=?,status='closed',updated_at=?
                   WHERE session_id=?""",
                (item["occurred_at"], duration, item["lca_event_id"], now, open_row["session_id"]),
            )

    @staticmethod
    def _configured_channel_count(c, did):
        return c.execute(
            """SELECT COUNT(*) FROM lca_channels
               WHERE device_id=? AND enabled=1
                 AND relationship_type IN ('direct','parallel','scene')
                 AND COALESCE(NULLIF(TRIM(name),''),NULLIF(TRIM(related_light_name),''),NULLIF(TRIM(scene_id),'')) IS NOT NULL""",
            (did,),
        ).fetchone()[0]

    @classmethod
    def _refresh_configuration_status(cls, c, did):
        row = c.execute("SELECT status,location_name FROM lca_devices WHERE device_id=?", (did,)).fetchone()
        if not row or row["status"] == "ignored":
            return
        total_channels = c.execute("SELECT COUNT(*) FROM lca_channels WHERE device_id=?", (did,)).fetchone()[0]
        total = c.execute("SELECT COUNT(*) FROM lca_channels WHERE device_id=? AND enabled=1", (did,)).fetchone()[0]
        configured = cls._configured_channel_count(c, did)
        if total_channels > 0 and total == 0:
            status = "configured"
        elif row["location_name"] and total > 0 and configured == total:
            status = "configured"
        elif row["location_name"] or configured > 0:
            status = "incomplete"
        else:
            status = "discovered"
        c.execute("UPDATE lca_devices SET status=? WHERE device_id=?", (status, did))

    def devices(self, include_ignored=False):
        with self.db.connect() as c:
            where = "" if include_ignored else "WHERE d.status<>'ignored'"
            rows = c.execute(
                f"""SELECT d.*,
                          (SELECT COUNT(*) FROM lca_channels x WHERE x.device_id=d.device_id) channel_count,
                          (SELECT COUNT(*) FROM lca_channels x WHERE x.device_id=d.device_id AND x.enabled=1) monitored_channel_count,
                          (SELECT COUNT(*) FROM lca_channels x WHERE x.device_id=d.device_id AND x.enabled=0) excluded_channel_count,
                          (SELECT COUNT(*) FROM lca_channels x WHERE x.device_id=d.device_id AND x.enabled=1
                             AND COALESCE(NULLIF(TRIM(x.name),''),NULLIF(TRIM(x.related_light_name),'')) IS NOT NULL) configured_channel_count
                   FROM lca_devices d
                   {where}
                   ORDER BY CASE d.status WHEN 'discovered' THEN 0 WHEN 'incomplete' THEN 1 WHEN 'configured' THEN 2 ELSE 3 END,d.name"""
            ).fetchall()
            return [dict(r) for r in rows]

    def device(self, did):
        with self.db.connect() as c:
            d = c.execute("SELECT * FROM lca_devices WHERE device_id=?", (did,)).fetchone()
            if not d:
                return None
            channels = c.execute("SELECT * FROM lca_channels WHERE device_id=? ORDER BY channel_key", (did,)).fetchall()
            out = dict(d)
            out["channels"] = [dict(x) for x in channels]
            out["configured_channel_count"] = self._configured_channel_count(c, did)
            out["channel_count"] = len(channels)
            out["monitored_channel_count"] = sum(1 for x in channels if bool(x["enabled"]))
            out["excluded_channel_count"] = sum(1 for x in channels if not bool(x["enabled"]))
            return out

    def update_device(self, did, p):
        allowed = ["name", "device_type", "status", "location_id", "location_name", "adjacent_location_id", "adjacent_location_name", "position_label", "notes"]
        fields = [k for k in allowed if k in p]
        if not fields:
            return self.device(did)
        with self.db.connect() as c:
            exists = c.execute("SELECT 1 FROM lca_devices WHERE device_id=?", (did,)).fetchone()
            if not exists:
                return None
            now = datetime.now(timezone.utc).isoformat()
            vals = [p[k] for k in fields] + [now, did]
            c.execute(f"UPDATE lca_devices SET {','.join(k+'=?' for k in fields)},updated_at=? WHERE device_id=?", vals)
            if p.get("status") == "ignored":
                c.execute(
                    "INSERT INTO lca_device_exclusions(device_id,reason,created_at,updated_at) VALUES(?,?,?,?) "
                    "ON CONFLICT(device_id) DO UPDATE SET reason=excluded.reason,updated_at=excluded.updated_at",
                    (did, "ignored_by_user", now, now),
                )
            elif "status" in p and p.get("status") != "ignored":
                c.execute("DELETE FROM lca_device_exclusions WHERE device_id=?", (did,))
            self._refresh_configuration_status(c, did)
        return self.device(did)

    def ignored_devices(self):
        with self.db.connect() as c:
            rows = c.execute(
                """SELECT d.*,
                          (SELECT COUNT(*) FROM lca_channels x WHERE x.device_id=d.device_id) channel_count,
                          (SELECT COUNT(*) FROM lca_events e WHERE e.device_id=d.device_id) historical_event_count
                   FROM lca_devices d WHERE d.status='ignored' ORDER BY d.name"""
            ).fetchall()
            return [dict(r) for r in rows]

    def reactivate_device(self, did):
        with self.db.connect() as c:
            exists = c.execute("SELECT 1 FROM lca_devices WHERE device_id=?", (did,)).fetchone()
            if not exists:
                return None
            now = datetime.now(timezone.utc).isoformat()
            c.execute("DELETE FROM lca_device_exclusions WHERE device_id=?", (did,))
            c.execute("UPDATE lca_devices SET status='discovered',updated_at=? WHERE device_id=?", (now, did))
            self._refresh_configuration_status(c, did)
        return self.device(did)

    def remove_device(self, did, preserve_history=True, ignore_future=False):
        with self.db.connect() as c:
            exists = c.execute("SELECT 1 FROM lca_devices WHERE device_id=?", (did,)).fetchone()
            if not exists:
                return False
            now = datetime.now(timezone.utc).isoformat()
            if ignore_future:
                c.execute(
                    "INSERT INTO lca_device_exclusions(device_id,reason,created_at,updated_at) VALUES(?,?,?,?) "
                    "ON CONFLICT(device_id) DO UPDATE SET reason=excluded.reason,updated_at=excluded.updated_at",
                    (did, "removed_and_blocked", now, now),
                )
            else:
                c.execute("DELETE FROM lca_device_exclusions WHERE device_id=?", (did,))
            c.execute("DELETE FROM lca_sessions WHERE device_id=?", (did,))
            c.execute("DELETE FROM lca_channel_state WHERE device_id=?", (did,))
            c.execute("DELETE FROM lca_messages WHERE device_id=?", (did,))
            c.execute("DELETE FROM lca_channels WHERE device_id=?", (did,))
            if not preserve_history:
                c.execute("DELETE FROM lca_events WHERE device_id=?", (did,))
            c.execute("DELETE FROM lca_devices WHERE device_id=?", (did,))
        return True

    def update_channel(self, did, ch, p):
        role=str(p.get("relationship_type") or p.get("role") or "unassigned")
        now=datetime.now(timezone.utc).isoformat()
        with self.db.connect() as c:
            cid=f"{did}:{ch}"
            c.execute("INSERT OR IGNORE INTO lca_channels(channel_id,device_id,channel_key,created_at,updated_at) VALUES(?,?,?,?,?)",(cid,did,ch,now,now))
            previous=c.execute("SELECT enabled FROM lca_channels WHERE device_id=? AND channel_key=?",(did,ch)).fetchone()
            enabled=0 if role=="ignored" or p.get("enabled") is False else 1
            name=(p.get("name") or "").strip() or None
            location=(p.get("location_name") or "").strip() or None
            light_id=None; related_name=None; parallel_source=None; scene_id=None
            if role=="direct":
                related_name=(p.get("light_name") or p.get("related_light_name") or name or "").strip() or None
                name_key=self._normalize_identifier(related_name or ch)
                location_key=self._normalize_identifier(location)
                circuit_id=f"{location_key}_{name_key}" if location_key else name_key
                # Reuse an existing logical circuit instead of creating one
                # light asset per direct entity. A location-less asset is reused
                # only when it is the unique circuit with that semantic name.
                existing=c.execute("SELECT * FROM lca_light_assets WHERE archived_at IS NULL AND site_id=? AND circuit_id=? LIMIT 1",
                                   (self.db.site_id,circuit_id)).fetchone()
                if not existing and location_key:
                    existing=c.execute("""SELECT * FROM lca_light_assets
                        WHERE archived_at IS NULL AND site_id=? AND lower(name)=lower(?)
                          AND (location_name IS NULL OR trim(location_name)='') LIMIT 1""",
                                       (self.db.site_id,related_name or ch)).fetchone()
                if existing:
                    light_id=existing["light_id"]
                    c.execute("UPDATE lca_light_assets SET name=?,location_name=COALESCE(?,location_name),circuit_id=?,updated_at=? WHERE light_id=?",
                              (related_name or ch,location,circuit_id,now,light_id))
                else:
                    light_id=f"light:{did}:{ch}"
                    c.execute("INSERT INTO lca_light_assets(light_id,site_id,name,location_name,source_channel_id,circuit_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(light_id) DO UPDATE SET name=excluded.name,location_name=excluded.location_name,circuit_id=excluded.circuit_id,updated_at=excluded.updated_at",
                              (light_id,self.db.site_id,related_name or ch,location,cid,circuit_id,now,now))
            elif role=="parallel":
                parallel_source=p.get("parallel_source_channel_id")
                src=c.execute("SELECT light_asset_id,related_light_name,location_name FROM lca_channels WHERE channel_id=?",(parallel_source,)).fetchone() if parallel_source else None
                if src:
                    light_id=src["light_asset_id"]; related_name=src["related_light_name"]; location=src["location_name"]
            elif role=="scene":
                scene_name=(p.get("scene_name") or name or "Cena").strip()
                scene_id=p.get("scene_id") or f"scene:{did}:{ch}"
                c.execute("INSERT INTO lca_scenes(scene_id,site_id,name,description,auto_learn,created_at,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(scene_id) DO UPDATE SET name=excluded.name,description=excluded.description,auto_learn=excluded.auto_learn,updated_at=excluded.updated_at",(scene_id,self.db.site_id,scene_name,p.get("scene_description"),1 if p.get("auto_learn",True) else 0,now,now))
                name=scene_name
            c.execute("UPDATE lca_channels SET enabled=?,name=?,location_name=?,relationship_type=?,light_asset_id=?,parallel_source_channel_id=?,scene_id=?,related_light_id=?,related_light_name=?,updated_at=? WHERE device_id=? AND channel_key=?",(enabled,name,location,role,light_id,parallel_source,scene_id,light_id,related_name,now,did,ch))
            current=c.execute("SELECT enabled FROM lca_channels WHERE device_id=? AND channel_key=?",(did,ch)).fetchone()
            if previous and current and bool(previous["enabled"])!=bool(current["enabled"]):
                c.execute("DELETE FROM lca_channel_state WHERE device_id=? AND channel_key=?",(did,ch)); c.execute("DELETE FROM lca_sessions WHERE device_id=? AND channel_key=? AND status='open'",(did,ch))
            self._refresh_configuration_status(c,did)
        return self.device(did)

    def relationship_catalog(self):
        with self.db.connect() as c:
            points=[dict(r) for r in c.execute("SELECT ch.channel_id,ch.device_id,ch.channel_key,ch.related_light_name light_name,ch.location_name,d.name device_name,l.circuit_id FROM lca_channels ch JOIN lca_devices d ON d.device_id=ch.device_id LEFT JOIN lca_light_assets l ON l.light_id=ch.light_asset_id WHERE ch.relationship_type='direct' AND ch.enabled=1 AND ch.light_asset_id IS NOT NULL AND l.archived_at IS NULL ORDER BY ch.location_name,ch.related_light_name,d.name").fetchall()]
            scenes=[dict(r) for r in c.execute("SELECT s.*, (SELECT COUNT(*) FROM lca_scene_executions x WHERE x.scene_id=s.scene_id) execution_count FROM lca_scenes s ORDER BY s.name").fetchall()]
            effects=[dict(r) for r in c.execute("SELECT e.*,l.name light_name FROM lca_scene_effects e LEFT JOIN lca_light_assets l ON l.light_id=e.light_id ORDER BY e.scene_id,e.confidence DESC").fetchall()]
            return {"direct_points":points,"scenes":scenes,"scene_effects":effects}

    def events(self, hours=24, limit=200, device_id=None):
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        where, params = ["occurred_at>=?"], [since]
        if device_id:
            where.append("device_id=?")
            params.append(device_id)
        params.append(limit)
        with self.db.connect() as c:
            query = f"""SELECT e.* FROM lca_events e
                        JOIN lca_devices d ON d.device_id=e.device_id
                        LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                        WHERE {' AND '.join('e.'+w if w.startswith('occurred_at') or w.startswith('device_id') else w for w in where)}
                          AND d.status<>'ignored'
                          AND (e.channel_key IS NULL OR ch.enabled=1)
                        ORDER BY e.occurred_at DESC LIMIT ?"""
            return [dict(r) for r in c.execute(query, params).fetchall()]

    def dashboard(self, hours=24, action_page=1, action_page_size=10):
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        action_page = max(1, int(action_page or 1))
        action_page_size = max(5, min(50, int(action_page_size or 10)))
        action_offset = (action_page - 1) * action_page_size
        with self.db.connect() as c:
            totals = dict(c.execute("""SELECT COUNT(*) events,COUNT(DISTINCT e.device_id) active_devices
                FROM lca_events e JOIN lca_devices d ON d.device_id=e.device_id
                LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                WHERE e.occurred_at>=? AND d.status<>'ignored'
                  AND (e.channel_key IS NULL OR ch.enabled=1)""", (since,)).fetchone())
            totals["messages_received"] = c.execute("SELECT COUNT(*) FROM lca_messages WHERE occurred_at>=?", (since,)).fetchone()[0]
            totals["discovered_devices"] = c.execute("SELECT COUNT(*) FROM lca_devices WHERE status<>'ignored'").fetchone()[0]
            totals["ignored_devices"] = c.execute("SELECT COUNT(*) FROM lca_devices WHERE status='ignored'").fetchone()[0]
            totals["unconfigured_devices"] = c.execute("SELECT COUNT(*) FROM lca_devices WHERE status IN ('discovered','incomplete')").fetchone()[0]
            totals["interactions"] = c.execute("""SELECT COUNT(*) FROM lca_events e JOIN lca_devices d ON d.device_id=e.device_id
                LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                WHERE e.occurred_at>=? AND e.kind='interaction' AND d.status<>'ignored'
                  AND (e.channel_key IS NULL OR ch.enabled=1)""", (since,)).fetchone()[0]
            totals["state_changes"] = c.execute("""SELECT COUNT(*) FROM lca_events e JOIN lca_devices d ON d.device_id=e.device_id
                LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                WHERE e.occurred_at>=? AND e.kind='state_change' AND d.status<>'ignored'
                  AND (e.channel_key IS NULL OR ch.enabled=1)""", (since,)).fetchone()[0]
            # Estado lógico consolidado: cada luz é contada uma única vez,
            # independentemente da quantidade de gangs diretos ou paralelos.
            current_lights = [dict(r) for r in c.execute("""
                SELECT l.light_id,l.circuit_id,l.name,l.location_name,
                       COUNT(DISTINCT CASE WHEN d.device_id IS NOT NULL THEN ch.channel_id END) point_count,
                       COUNT(DISTINCT CASE WHEN d.device_id IS NOT NULL AND ch.relationship_type='direct' THEN ch.channel_id END) direct_point_count,
                       COUNT(DISTINCT CASE WHEN d.device_id IS NOT NULL AND ch.relationship_type='parallel' THEN ch.channel_id END) parallel_point_count,
                       (
                         SELECT cs.state
                         FROM lca_channels ch2
                         JOIN lca_channel_state cs
                           ON cs.device_id=ch2.device_id AND cs.channel_key=ch2.channel_key
                         JOIN lca_devices d2 ON d2.device_id=ch2.device_id
                         WHERE ch2.light_asset_id=l.light_id
                           AND ch2.enabled=1 AND d2.status<>'ignored'
                         ORDER BY CASE WHEN ch2.relationship_type='direct' THEN 0 ELSE 1 END,
                                  COALESCE(cs.last_changed_at,cs.last_observed_at) DESC
                         LIMIT 1
                       ) state,
                       (
                         SELECT COALESCE(cs.last_changed_at,cs.last_observed_at)
                         FROM lca_channels ch2
                         JOIN lca_channel_state cs
                           ON cs.device_id=ch2.device_id AND cs.channel_key=ch2.channel_key
                         JOIN lca_devices d2 ON d2.device_id=ch2.device_id
                         WHERE ch2.light_asset_id=l.light_id
                           AND ch2.enabled=1 AND d2.status<>'ignored'
                         ORDER BY CASE WHEN ch2.relationship_type='direct' THEN 0 ELSE 1 END,
                                  COALESCE(cs.last_changed_at,cs.last_observed_at) DESC
                         LIMIT 1
                       ) last_updated_at
                FROM lca_light_assets l
                LEFT JOIN lca_channels ch ON ch.light_asset_id=l.light_id AND ch.enabled=1
                LEFT JOIN lca_devices d ON d.device_id=ch.device_id AND d.status<>'ignored'
                WHERE l.archived_at IS NULL
                GROUP BY l.light_id,l.circuit_id,l.name,l.location_name
                HAVING COUNT(DISTINCT CASE WHEN d.device_id IS NOT NULL THEN ch.channel_id END)>0
                ORDER BY l.location_name,l.name
            """).fetchall()]
            totals["monitored_lights"] = len(current_lights)
            totals["monitored_points"] = sum(int(light.get("point_count") or 0) for light in current_lights)
            totals["direct_points"] = sum(int(light.get("direct_point_count") or 0) for light in current_lights)
            totals["parallel_points"] = sum(int(light.get("parallel_point_count") or 0) for light in current_lights)
            totals["active_lights"] = sum(1 for light in current_lights if str(light.get("state") or "").upper() == "ON")
            totals["unknown_lights"] = sum(1 for light in current_lights if not light.get("state"))
            # Mantido para compatibilidade com clientes antigos da API.
            totals["open_sessions"] = totals["active_lights"]
            totals["confirmed_interactions"] = c.execute("""SELECT COUNT(*) FROM lca_events e JOIN lca_devices d ON d.device_id=e.device_id
                LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                WHERE e.occurred_at>=? AND e.kind='interaction' AND e.interaction_status='confirmed'
                  AND d.status<>'ignored' AND (e.channel_key IS NULL OR ch.enabled=1)""", (since,)).fetchone()[0]
            totals["unconfirmed_interactions"] = c.execute("""SELECT COUNT(*) FROM lca_events e JOIN lca_devices d ON d.device_id=e.device_id
                LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                WHERE e.occurred_at>=? AND e.kind='interaction'
                  AND COALESCE(e.interaction_status,'pending_confirmation')<>'confirmed'
                  AND d.status<>'ignored' AND (e.channel_key IS NULL OR ch.enabled=1)""", (since,)).fetchone()[0]
            by_hour = [dict(r) for r in c.execute("""SELECT substr(e.occurred_at,1,13)||':00' bucket,COUNT(*) value
                FROM lca_events e JOIN lca_devices d ON d.device_id=e.device_id
                LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                WHERE e.occurred_at>=? AND d.status<>'ignored'
                  AND (e.channel_key IS NULL OR ch.enabled=1) GROUP BY bucket ORDER BY bucket""", (since,)).fetchall()]
            top = [dict(r) for r in c.execute("SELECT COALESCE(d.name,e.device_id) name,e.device_id,COUNT(*) events FROM lca_events e LEFT JOIN lca_devices d ON d.device_id=e.device_id LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key WHERE e.occurred_at>=? AND d.status<>'ignored' AND (e.channel_key IS NULL OR ch.enabled=1) GROUP BY e.device_id ORDER BY events DESC LIMIT 10", (since,)).fetchall()]
            routes = [dict(r) for r in c.execute("""SELECT e.origin_location_name,e.adjacent_location_name,e.direction_hint,
                COUNT(*) evidence_count,MAX(e.occurred_at) last_seen
                FROM lca_events e JOIN lca_devices d ON d.device_id=e.device_id
                LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                WHERE e.occurred_at>=? AND e.kind='interaction' AND d.status<>'ignored'
                  AND (e.channel_key IS NULL OR ch.enabled=1)
                  AND (e.direction_hint IS NOT NULL OR e.adjacent_location_name IS NOT NULL)
                GROUP BY e.origin_location_name,e.adjacent_location_name,e.direction_hint
                ORDER BY evidence_count DESC LIMIT 10""", (since,)).fetchall()]
            action_total = c.execute("""SELECT COUNT(*)
                FROM lca_events e LEFT JOIN lca_devices d ON d.device_id=e.device_id
                LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                WHERE e.occurred_at>=? AND e.kind='interaction' AND d.status<>'ignored'
                  AND (e.channel_key IS NULL OR ch.enabled=1)""", (since,)).fetchone()[0]
            action_rows = [dict(r) for r in c.execute("""SELECT e.*,d.name device_name,d.position_label device_position,
                COALESCE(l.name,e.related_light_name) light_name,ch.relationship_type point_relationship
                FROM lca_events e LEFT JOIN lca_devices d ON d.device_id=e.device_id
                LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                LEFT JOIN lca_light_assets l ON l.light_id=ch.light_asset_id
                WHERE e.occurred_at>=? AND e.kind='interaction' AND d.status<>'ignored'
                  AND (e.channel_key IS NULL OR ch.enabled=1)
                ORDER BY e.occurred_at DESC LIMIT ? OFFSET ?""", (since, action_page_size, action_offset)).fetchall()]
            actions=[]
            for item in action_rows:
                effects=[]
                if item.get("lca_event_id"):
                    effects=[dict(x) for x in c.execute("""SELECT e.lca_event_id,e.device_id,e.channel_key,e.state,e.action,e.occurred_at,
                        d.name device_name,ch.relationship_type,COALESCE(l.name,e.related_light_name) light_name
                        FROM lca_events e LEFT JOIN lca_devices d ON d.device_id=e.device_id
                        LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                        LEFT JOIN lca_light_assets l ON l.light_id=ch.light_asset_id
                        WHERE (e.cause_type='interaction' AND e.cause_id=?) OR e.lca_event_id=?
                        ORDER BY e.occurred_at""",(item["lca_event_id"],item.get("effect_event_id"))).fetchall()]
                item["effects"]=effects
                actions.append(item)
            technical=[dict(r) for r in c.execute("""SELECT e.*,d.name device_name,d.position_label device_position,
                COALESCE(l.name,e.related_light_name) light_name,ch.relationship_type point_relationship
                FROM lca_events e LEFT JOIN lca_devices d ON d.device_id=e.device_id
                LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                LEFT JOIN lca_light_assets l ON l.light_id=ch.light_asset_id
                WHERE e.occurred_at>=? AND e.kind<>'interaction' AND d.status<>'ignored'
                  AND (e.channel_key IS NULL OR ch.enabled=1)
                ORDER BY e.occurred_at DESC LIMIT 30""", (since,)).fetchall()]
            origin_breakdown = [dict(r) for r in c.execute("""
                SELECT COALESCE(e.origin_mode,'unknown') key,COUNT(*) value
                FROM lca_events e JOIN lca_devices d ON d.device_id=e.device_id
                LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                WHERE e.occurred_at>=? AND e.kind='interaction' AND d.status<>'ignored'
                  AND (e.channel_key IS NULL OR ch.enabled=1)
                GROUP BY COALESCE(e.origin_mode,'unknown') ORDER BY value DESC
            """, (since,)).fetchall()]
            role_breakdown = [dict(r) for r in c.execute("""
                SELECT COALESCE(ch.relationship_type,'unassigned') key,COUNT(*) value
                FROM lca_events e JOIN lca_devices d ON d.device_id=e.device_id
                LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                WHERE e.occurred_at>=? AND e.kind='interaction' AND d.status<>'ignored'
                  AND (e.channel_key IS NULL OR ch.enabled=1)
                GROUP BY COALESCE(ch.relationship_type,'unassigned') ORDER BY value DESC
            """, (since,)).fetchall()]
            merge_count = c.execute("SELECT COUNT(*) FROM lca_light_merge_log").fetchone()[0]
            missing_location = c.execute("SELECT COUNT(*) FROM lca_light_assets WHERE archived_at IS NULL AND (location_name IS NULL OR trim(location_name)='')").fetchone()[0]
            parallel_without_circuit = c.execute("SELECT COUNT(*) FROM lca_channels WHERE enabled=1 AND relationship_type='parallel' AND light_asset_id IS NULL").fetchone()[0]
            circuits_without_direct = c.execute("""SELECT COUNT(*) FROM lca_light_assets l WHERE l.archived_at IS NULL
                AND NOT EXISTS(SELECT 1 FROM lca_channels ch WHERE ch.light_asset_id=l.light_id AND ch.enabled=1 AND ch.relationship_type='direct')""").fetchone()[0]
            configuration_quality = {
                "merged_circuits": merge_count,
                "circuits_without_location": missing_location,
                "parallels_without_circuit": parallel_without_circuit,
                "circuits_without_direct_point": circuits_without_direct,
            }
            recent=(actions+technical)[:30]
        return {"period_hours": hours, "summary": totals, "by_hour": by_hour, "top_devices": top,
                "route_evidence": routes, "recent_actions": actions, "technical_events": technical,
                "current_lights": current_lights, "origin_breakdown": origin_breakdown,
                "role_breakdown": role_breakdown, "configuration_quality": configuration_quality, "recent_events": recent[:30],
                "action_pagination": {
                    "page": action_page,
                    "page_size": action_page_size,
                    "total": action_total,
                    "total_pages": max(1, (action_total + action_page_size - 1) // action_page_size)
                },
                "updated_at": datetime.now(timezone.utc).isoformat()}
