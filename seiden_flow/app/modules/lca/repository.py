from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


class LCARepository:
    """Persistence and relevant-event processing for Lighting Context Analytics.

    MQTT publications are telemetry. They only become analytical events when a
    channel actually changes state or an explicit physical interaction is
    observed.
    """

    def __init__(self, db, timezone_name="UTC"):
        self.db = db
        self.timezone_name = str(timezone_name or "UTC")
        try:
            self.local_timezone = ZoneInfo(self.timezone_name)
        except Exception:
            self.timezone_name = "UTC"
            self.local_timezone = timezone.utc
        self.ensure_schema()
        self._migrate_010_history()
        self._migrate_035_channel_aliases()
        self._migrate_036_logical_circuits()
        self._migrate_037_infrastructure_identity()
        self._migrate_0393_canonical_circuit_state()
        self._migrate_040_circuit_usage_sessions()

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
            c.execute("""CREATE TABLE IF NOT EXISTS lca_circuit_state(
                light_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                first_observed_at TEXT NOT NULL,
                last_changed_at TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_event_id TEXT,
                updated_at TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS lca_circuit_sessions(
                session_id TEXT PRIMARY KEY,
                light_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                duration_seconds INTEGER,
                start_event_id TEXT,
                end_event_id TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                source_type TEXT NOT NULL DEFAULT 'confirmed_interaction',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL)""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_lca_circuit_sessions_light_start ON lca_circuit_sessions(light_id,started_at DESC)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_lca_circuit_sessions_status ON lca_circuit_sessions(status,started_at DESC)")

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

    def _migrate_0393_canonical_circuit_state(self):
        """Create one persistent state per logical lighting circuit.

        The logical circuit state is intentionally independent from the
        instantaneous state of direct/parallel interaction points. Existing
        installations are initialized from the most recent confirmed logical
        interaction when available, falling back to the latest channel state
        only as a startup baseline.
        """
        key = "lca_canonical_circuit_state_0393"
        with self.db.connect() as c:
            if c.execute("SELECT value FROM lca_metadata WHERE key=?", (key,)).fetchone():
                return
            now = datetime.now(timezone.utc).isoformat()
            lights = c.execute("SELECT light_id FROM lca_light_assets WHERE archived_at IS NULL").fetchall()
            for light in lights:
                light_id = light["light_id"]
                interaction = c.execute("""
                    SELECT e.requested_state,COALESCE(e.effect_confirmed_at,e.occurred_at) changed_at,e.lca_event_id
                    FROM lca_events e
                    JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                    WHERE ch.light_asset_id=? AND e.kind='interaction'
                      AND e.interaction_status='confirmed' AND e.requested_state IN ('on','off')
                    ORDER BY COALESCE(e.effect_confirmed_at,e.occurred_at) DESC
                    LIMIT 1
                """, (light_id,)).fetchone()
                if interaction:
                    state = interaction["requested_state"]
                    changed_at = interaction["changed_at"]
                    source_type = "confirmed_interaction_migration"
                    source_event_id = interaction["lca_event_id"]
                else:
                    baseline = c.execute("""
                        SELECT cs.state,COALESCE(cs.last_changed_at,cs.last_observed_at) changed_at
                        FROM lca_channels ch
                        JOIN lca_channel_state cs ON cs.device_id=ch.device_id AND cs.channel_key=ch.channel_key
                        JOIN lca_devices d ON d.device_id=ch.device_id
                        WHERE ch.light_asset_id=? AND ch.enabled=1 AND d.status<>'ignored'
                        ORDER BY COALESCE(cs.last_changed_at,cs.last_observed_at) DESC
                        LIMIT 1
                    """, (light_id,)).fetchone()
                    if not baseline:
                        continue
                    state = str(baseline["state"] or "").lower()
                    if state not in {"on", "off"}:
                        continue
                    changed_at = baseline["changed_at"]
                    source_type = "channel_baseline_migration"
                    source_event_id = None
                c.execute("""INSERT OR REPLACE INTO lca_circuit_state
                    (light_id,state,first_observed_at,last_changed_at,source_type,source_event_id,updated_at)
                    VALUES(?,?,?,?,?,?,?)""",
                    (light_id,state,changed_at,changed_at,source_type,source_event_id,now))
            c.execute("INSERT INTO lca_metadata(key,value,updated_at) VALUES(?,?,?)", (key, "completed", now))

    def _migrate_040_circuit_usage_sessions(self):
        """Build canonical lighting sessions from confirmed circuit interactions.

        LCA 0.4.0 treats a session as a circuit-level ON interval. Point-level
        telemetry remains evidence only; analytics are derived from the
        canonical circuit state introduced in 0.3.9.3.
        """
        key = "lca_circuit_usage_sessions_040"
        with self.db.connect() as c:
            if c.execute("SELECT value FROM lca_metadata WHERE key=?", (key,)).fetchone():
                return
            now = datetime.now(timezone.utc).isoformat()
            c.execute("DELETE FROM lca_circuit_sessions")
            lights = [dict(r) for r in c.execute(
                "SELECT light_id,circuit_id FROM lca_light_assets WHERE archived_at IS NULL"
            ).fetchall()]
            for light in lights:
                rows = [dict(r) for r in c.execute("""
                    SELECT e.lca_event_id,e.requested_state,e.occurred_at,e.effect_confirmed_at,e.circuit_id
                    FROM lca_events e
                    LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                    WHERE e.kind='interaction' AND e.interaction_status='confirmed'
                      AND e.requested_state IN ('on','off')
                      AND (ch.light_asset_id=? OR (e.circuit_id IS NOT NULL AND e.circuit_id=?))
                    ORDER BY COALESCE(e.effect_confirmed_at,e.occurred_at),e.id
                """, (light["light_id"], light.get("circuit_id"))).fetchall()]
                current = None
                open_sid = None
                open_start = None
                for row in rows:
                    state = str(row.get("requested_state") or "").lower()
                    at = row.get("effect_confirmed_at") or row.get("occurred_at")
                    if state == current:
                        continue
                    if state == "on":
                        sid = f"{light['light_id']}:circuit:{at}"
                        c.execute("""INSERT OR IGNORE INTO lca_circuit_sessions
                            (session_id,light_id,started_at,start_event_id,status,source_type,created_at,updated_at)
                            VALUES(?,?,?,?,?,?,?,?)""",
                            (sid,light["light_id"],at,row["lca_event_id"],"open","migration_confirmed_interaction",now,now))
                        open_sid, open_start = sid, at
                    elif state == "off" and open_sid:
                        duration = max(0, int((self._parse_time(at)-self._parse_time(open_start)).total_seconds()))
                        c.execute("""UPDATE lca_circuit_sessions SET ended_at=?,duration_seconds=?,end_event_id=?,status='closed',updated_at=?
                            WHERE session_id=?""", (at,duration,row["lca_event_id"],now,open_sid))
                        open_sid, open_start = None, None
                    current = state
            c.execute("INSERT INTO lca_metadata(key,value,updated_at) VALUES(?,?,?)", (key,"completed",now))

    def _migrate_0404_direct_state_authority(self):
        """Reconcile current circuit state from direct-point evidence only.

        Earlier LCA builds could let a confirmed interaction write
        `lca_circuit_state`. That violates the core invariant:

          interaction = intention/origin
          direct state transition = actual circuit state

        This one-time reconciliation repairs existing installations using the
        latest configured DIRECT point evidence. It does not rewrite historical
        interactions and does not destroy closed usage sessions.
        """
        key = "lca_direct_state_authority_0404"
        with self.db.connect() as c:
            if c.execute("SELECT value FROM lca_metadata WHERE key=?", (key,)).fetchone():
                return

            now = datetime.now(timezone.utc).isoformat()
            lights = c.execute(
                "SELECT light_id FROM lca_light_assets WHERE archived_at IS NULL"
            ).fetchall()

            for light in lights:
                light_id = light["light_id"]

                # Prefer an analytical state_change event emitted by the direct
                # point. This carries the precise transition timestamp.
                latest = c.execute("""
                    SELECT e.state,e.occurred_at,e.lca_event_id
                    FROM lca_events e
                    JOIN lca_channels ch
                      ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                    JOIN lca_devices d ON d.device_id=ch.device_id
                    WHERE ch.light_asset_id=?
                      AND ch.enabled=1
                      AND ch.relationship_type='direct'
                      AND d.status<>'ignored'
                      AND e.kind='state_change'
                      AND e.state IN ('on','off')
                    ORDER BY julianday(e.occurred_at) DESC,e.id DESC
                    LIMIT 1
                """, (light_id,)).fetchone()

                if latest:
                    state = str(latest["state"]).lower()
                    changed_at = latest["occurred_at"]
                    source_event_id = latest["lca_event_id"]
                else:
                    # If no historical event exists, use only the current state
                    # of the configured direct point. Never infer circuit state
                    # from a parallel point or from an interaction.
                    latest = c.execute("""
                        SELECT cs.state,
                               COALESCE(cs.last_changed_at,cs.last_observed_at) occurred_at
                        FROM lca_channels ch
                        JOIN lca_channel_state cs
                          ON cs.device_id=ch.device_id AND cs.channel_key=ch.channel_key
                        JOIN lca_devices d ON d.device_id=ch.device_id
                        WHERE ch.light_asset_id=?
                          AND ch.enabled=1
                          AND ch.relationship_type='direct'
                          AND d.status<>'ignored'
                          AND cs.state IN ('on','off')
                        ORDER BY julianday(COALESCE(cs.last_changed_at,cs.last_observed_at)) DESC
                        LIMIT 1
                    """, (light_id,)).fetchone()
                    if not latest:
                        continue
                    state = str(latest["state"]).lower()
                    changed_at = latest["occurred_at"]
                    source_event_id = None

                existing = c.execute(
                    "SELECT first_observed_at FROM lca_circuit_state WHERE light_id=?",
                    (light_id,),
                ).fetchone()
                first_observed_at = (
                    existing["first_observed_at"] if existing else changed_at
                )

                c.execute("""
                    INSERT INTO lca_circuit_state(
                        light_id,state,first_observed_at,last_changed_at,
                        source_type,source_event_id,updated_at
                    )
                    VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(light_id) DO UPDATE SET
                        state=excluded.state,
                        last_changed_at=excluded.last_changed_at,
                        source_type=excluded.source_type,
                        source_event_id=excluded.source_event_id,
                        updated_at=excluded.updated_at
                """, (
                    light_id, state, first_observed_at, changed_at,
                    "direct_state_reconciliation_0404", source_event_id, now
                ))

                # Reconcile only the currently open session. Closed historical
                # sessions are preserved.
                open_row = c.execute("""
                    SELECT session_id,started_at
                    FROM lca_circuit_sessions
                    WHERE light_id=? AND status='open'
                    ORDER BY started_at DESC LIMIT 1
                """, (light_id,)).fetchone()

                if state == "on" and not open_row:
                    session_id = f"{light_id}:circuit:{changed_at}"
                    c.execute("""
                        INSERT OR IGNORE INTO lca_circuit_sessions(
                            session_id,light_id,started_at,start_event_id,status,
                            source_type,created_at,updated_at
                        ) VALUES(?,?,?,?,?,?,?,?)
                    """, (
                        session_id, light_id, changed_at, source_event_id, "open",
                        "direct_state_reconciliation_0404", now, now
                    ))
                elif state == "off" and open_row:
                    try:
                        duration = max(
                            0,
                            int((
                                self._parse_time(changed_at)
                                - self._parse_time(open_row["started_at"])
                            ).total_seconds()),
                        )
                    except Exception:
                        duration = 0
                    c.execute("""
                        UPDATE lca_circuit_sessions
                        SET ended_at=?,duration_seconds=?,end_event_id=?,
                            status='closed',updated_at=?
                        WHERE session_id=?
                    """, (
                        changed_at, duration, source_event_id, now,
                        open_row["session_id"]
                    ))

            c.execute(
                "INSERT INTO lca_metadata(key,value,updated_at) VALUES(?,?,?)",
                (key, "completed", now),
            )

    @staticmethod
    def _circuit_has_parallel(c, light_id):
        """True when the logical circuit has at least one enabled virtual parallel.

        Supports both current and legacy bindings. Some installations have
        parallel channels linked through related_light_id, while newer saves
        also populate light_asset_id.
        """
        if not light_id:
            return False
        return bool(c.execute("""
            SELECT 1
            FROM lca_channels ch
            JOIN lca_devices d ON d.device_id=ch.device_id
            WHERE (ch.light_asset_id=? OR ch.related_light_id=?)
              AND ch.enabled=1
              AND ch.relationship_type='parallel'
              AND d.status<>'ignored'
            LIMIT 1
        """, (light_id, light_id)).fetchone())

    def _set_circuit_state(self, c, light_id, state, changed_at, source_type, source_event_id, now):
        if not light_id or str(state or '').lower() not in {'on','off'}:
            return
        state = str(state).lower()
        existing = c.execute("SELECT * FROM lca_circuit_state WHERE light_id=?", (light_id,)).fetchone()
        if existing:
            try:
                if self._parse_time(changed_at) < self._parse_time(existing["last_changed_at"]):
                    return
            except Exception:
                pass
            previous_state = str(existing["state"] or "").lower()
            if previous_state == state:
                # Duplicate evidence may enrich provenance, but it must not
                # create a new usage session or reset its start time.
                c.execute("""UPDATE lca_circuit_state SET source_type=?,source_event_id=?,updated_at=?
                             WHERE light_id=?""", (source_type,source_event_id,now,light_id))
                return
            c.execute("""UPDATE lca_circuit_state SET state=?,last_changed_at=?,source_type=?,source_event_id=?,updated_at=?
                         WHERE light_id=?""",
                      (state,changed_at,source_type,source_event_id,now,light_id))
        else:
            previous_state = None
            c.execute("""INSERT INTO lca_circuit_state
                (light_id,state,first_observed_at,last_changed_at,source_type,source_event_id,updated_at)
                VALUES(?,?,?,?,?,?,?)""",
                (light_id,state,changed_at,changed_at,source_type,source_event_id,now))

        # Circuit-level sessions are the analytical source for time-in-use.
        # They are driven only by canonical state transitions, never by the
        # individual physical/virtual point state.
        if state == 'on':
            open_row = c.execute("""SELECT session_id FROM lca_circuit_sessions
                WHERE light_id=? AND status='open' ORDER BY started_at DESC LIMIT 1""", (light_id,)).fetchone()
            if not open_row:
                sid = f"{light_id}:circuit:{changed_at}"
                c.execute("""INSERT OR IGNORE INTO lca_circuit_sessions
                    (session_id,light_id,started_at,start_event_id,status,source_type,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?)""",
                    (sid,light_id,changed_at,source_event_id,"open",source_type,now,now))
        elif state == 'off':
            open_row = c.execute("""SELECT session_id,started_at FROM lca_circuit_sessions
                WHERE light_id=? AND status='open' ORDER BY started_at DESC LIMIT 1""", (light_id,)).fetchone()
            if open_row:
                duration = max(0, int((self._parse_time(changed_at)-self._parse_time(open_row["started_at"])).total_seconds()))
                c.execute("""UPDATE lca_circuit_sessions SET ended_at=?,duration_seconds=?,end_event_id=?,status='closed',updated_at=?
                    WHERE session_id=?""", (changed_at,duration,source_event_id,now,open_row["session_id"]))

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
                WHERE e.kind='state_change' AND e.state=? AND julianday(e.occurred_at) BETWEEN julianday(?) AND julianday(?)
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
        rows=c.execute("""SELECT * FROM lca_pending_interactions WHERE requested_state=? AND julianday(occurred_at) BETWEEN julianday(?) AND julianday(?) ORDER BY julianday(occurred_at)""",
                       (state_item["state"],lo,hi)).fetchall()
        for row in rows:
            pending_circuit=self._normalize_identifier(row["circuit_id"])
            if not pending_circuit or not (pending_circuit==circuit or pending_circuit.endswith("_"+circuit) or circuit.endswith("_"+pending_circuit)):
                continue
            item=json.loads(row["item_json"])
            resolved_source=self._resolve_interaction_source(c,item)
            if resolved_source:
                item["device_id"]=resolved_source["device_id"]
                item["device_name"]=resolved_source["name"]
                item["channel"]=resolved_source["resolved_channel_key"] or item.get("source_channel") or item.get("channel")
                interaction_cfg=c.execute(
                    "SELECT * FROM lca_channels WHERE device_id=? AND channel_key=?",
                    (item["device_id"],item.get("channel"))
                ).fetchone()
            else:
                # Compatibility fallback. Keep source_device/source_channel metadata;
                # direct transition identifies the circuit, not necessarily the origin.
                item["device_id"]=state_item["device_id"]
                dev=c.execute("SELECT name FROM lca_devices WHERE device_id=?",(state_item["device_id"],)).fetchone()
                item["device_name"]=dev["name"] if dev else state_item.get("device_name")
                item["channel"]=state_item.get("channel")
                interaction_cfg=cfg
            self._record_message(c,item,now)
            self._process_interaction(c,item,interaction_cfg,now)
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

        # Raw MQTT observations need a baseline before we can infer a change.
        # Bridge State Driver events are different: the Bridge already observed
        # the previous state and sends an explicit previous -> current transition.
        # Reconstruct that baseline so the first transition seen by Flow is not
        # lost after an LCA restart or when a device is first discovered.
        if previous is None:
            explicit_previous = str(item.get("previous_state") or "").lower() if item.get("explicit_transition") else ""
            if explicit_previous in {"on", "off"} and explicit_previous != new_state:
                c.execute(
                    """INSERT INTO lca_channel_state(device_id,channel_key,state,brightness,first_observed_at,last_observed_at,last_changed_at,updated_at)
                       VALUES(?,?,?,?,?,?,NULL,?)""",
                    (did, ch, explicit_previous, item.get("brightness"), item["occurred_at"], item["occurred_at"], now),
                )
                previous = c.execute(
                    "SELECT * FROM lca_channel_state WHERE device_id=? AND channel_key=?",
                    (did, ch),
                ).fetchone()
            else:
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

        direct_light_id = (
            cfg["light_asset_id"]
            if cfg is not None
            and cfg["relationship_type"] == "direct"
            and cfg["light_asset_id"]
            else None
        )
        has_parallel = self._circuit_has_parallel(c, direct_light_id) if direct_light_id else False

        # Standalone direct circuit: the observed direct transition is enough.
        # This covers MQTT/Zigbee2MQTT and Home Assistant sources equally.
        if direct_light_id and not has_parallel:
            self._set_circuit_state(
                c, direct_light_id, new_state, item["occurred_at"],
                "standalone_direct_state_transition", event["lca_event_id"], now,
            )

        if not event.get("cause_type"):
            self._correlate_pending_interaction(c,event,cfg,now)

        # Only standalone direct circuits create a synthetic comprehended action.
        # Circuits with a virtual parallel wait for the real lighting_interaction,
        # avoiding the race/double-count introduced after 0.15.9.3.
        if item.get("explicit_transition") and direct_light_id and not has_parallel:
            persisted = c.execute(
                "SELECT cause_type FROM lca_events WHERE lca_event_id=?",
                (event["lca_event_id"],),
            ).fetchone()
            if persisted and not persisted["cause_type"]:
                self._record_direct_transition_action(c, event, cfg, now)

        if event.get("cause_type") == "scene" and cfg and cfg["light_asset_id"]:
            self._learn_scene_effect(c,event["cause_id"],cfg["light_asset_id"],new_state,item["occurred_at"],now)
        return True

    def _record_direct_transition_action(self, c, state_event, cfg, now):
        """Represent an un-attributed direct state transition as one LCA action.

        This is used only for explicit Bridge State Driver transitions on a
        configured direct point and only when no explicit interaction already
        explains the effect. It avoids double counting virtual parallels.
        """
        action = dict(state_event)
        action_id = state_event["lca_event_id"] + ":direct_action"
        action.update({
            "lca_event_id": action_id,
            "kind": "interaction",
            "state": None,
            "action": state_event.get("state"),
            "requested_state": state_event.get("state"),
            "interaction_kind": "direct_state_transition",
            "origin_mode": "unknown",
            "interaction_status": "confirmed",
            "effect_event_id": state_event["lca_event_id"],
            "effect_confirmed_at": state_event["occurred_at"],
            "confirmation_latency_ms": 0,
            "point_role": "direct",
        })
        if not self._insert_event(c, action, cfg, now):
            return False
        c.execute(
            "UPDATE lca_events SET cause_type='interaction',cause_id=?,causal_confidence=1.0 WHERE lca_event_id=? AND cause_type IS NULL",
            (action_id, state_event["lca_event_id"]),
        )
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

        # A virtual-parallel synchronization can produce state changes on other
        # points of the same logical circuit. Node-RED may publish those echoes
        # as additional lighting_interaction messages. They are evidence of the
        # same operation, not new human actions.
        #
        # Keep the FIRST analytical interaction for a circuit/requested_state
        # and suppress later interactions from OTHER points inside a short causal
        # window. The raw MQTT message is still preserved in lca_messages.
        light_id = None
        if cfg is not None:
            light_id = cfg["light_asset_id"] or cfg["related_light_id"]

        if light_id and item.get("requested_state") in {"on", "off"}:
            echo_cutoff = (
                self._parse_time(item["occurred_at"]) - timedelta(seconds=4.5)
            ).isoformat()
            prior = c.execute("""
                SELECT e.lca_event_id,e.device_id,e.channel_key,e.occurred_at
                FROM lca_events e
                LEFT JOIN lca_channels ch
                  ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                WHERE e.kind='interaction'
                  AND e.requested_state=?
                  AND (ch.light_asset_id=? OR ch.related_light_id=?)
                  AND julianday(e.occurred_at) BETWEEN julianday(?) AND julianday(?)
                ORDER BY julianday(e.occurred_at) DESC
                LIMIT 1
            """, (
                item["requested_state"], light_id, light_id,
                echo_cutoff, item["occurred_at"],
            )).fetchone()

            if prior and (
                prior["device_id"] != item["device_id"]
                or (prior["channel_key"] or "") != (item.get("channel") or "")
            ):
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
        if inserted and event.get("interaction_status") == "confirmed" and cfg is not None:
            self._set_circuit_state(c, cfg["light_asset_id"], item.get("requested_state"),
                                    event.get("effect_confirmed_at") or item["occurred_at"],
                                    "confirmed_interaction", item["lca_event_id"], now)
        elif inserted:
            self._correlate_existing_effect(c,event,cfg,now)
        return inserted

    def _correlate_existing_effect(self,c,item,cfg,now):
        if not cfg or not cfg["light_asset_id"] or item.get("requested_state") not in {"on","off"}:return
        t=self._parse_time(item["occurred_at"])
        lo=(t-timedelta(seconds=2)).isoformat(); hi=(t+timedelta(seconds=1)).isoformat()
        effect=c.execute("""SELECT e.lca_event_id,e.occurred_at FROM lca_events e
            LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
            WHERE e.kind='state_change' AND ch.light_asset_id=? AND e.state=? AND julianday(e.occurred_at) BETWEEN julianday(?) AND julianday(?)
            ORDER BY ABS(julianday(e.occurred_at)-julianday(?)) LIMIT 1""",
            (cfg["light_asset_id"],item["requested_state"],lo,hi,item["occurred_at"])).fetchone()
        if effect:self._confirm_interaction(c,item["lca_event_id"],effect["lca_event_id"],effect["occurred_at"],item["occurred_at"],now)

    def _correlate_pending_interaction(self,c,event,cfg,now):
        if not cfg or not cfg["light_asset_id"]:return
        t=self._parse_time(event["occurred_at"]); lo=(t-timedelta(seconds=3)).isoformat()
        interaction=c.execute("""SELECT e.lca_event_id,e.occurred_at FROM lca_events e
            LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
            WHERE e.kind='interaction' AND ch.light_asset_id=? AND e.requested_state=?
              AND julianday(e.occurred_at) BETWEEN julianday(?) AND julianday(?) AND COALESCE(e.interaction_status,'pending_confirmation')='pending_confirmation'
            ORDER BY julianday(e.occurred_at) DESC LIMIT 1""",
            (cfg["light_asset_id"],event["state"],lo,event["occurred_at"])).fetchone()
        if interaction:self._confirm_interaction(c,interaction["lca_event_id"],event["lca_event_id"],event["occurred_at"],interaction["occurred_at"],now)

    def _confirm_interaction(self,c,interaction_id,effect_id,effect_at,interaction_at,now):
        latency=max(0,int((self._parse_time(effect_at)-self._parse_time(interaction_at)).total_seconds()*1000))
        c.execute("""UPDATE lca_events SET effect_event_id=?,effect_confirmed_at=?,confirmation_latency_ms=?,interaction_status='confirmed'
            WHERE lca_event_id=?""",(effect_id,effect_at,latency,interaction_id))
        c.execute("""UPDATE lca_events SET cause_type='interaction',cause_id=?,causal_confidence=1.0 WHERE lca_event_id=? AND cause_type IS NULL""",(interaction_id,effect_id))
        resolved=c.execute("""SELECT e.requested_state,ch.light_asset_id
            FROM lca_events e LEFT JOIN lca_channels ch ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
            WHERE e.lca_event_id=?""",(interaction_id,)).fetchone()
        if resolved:
            self._set_circuit_state(c,resolved["light_asset_id"],resolved["requested_state"],effect_at,
                                    "confirmed_interaction",interaction_id,now)

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
            for channel in out["channels"]:
                source_row = c.execute(
                    """SELECT source_entity FROM lca_events
                       WHERE device_id=? AND channel_key=? AND source_entity IS NOT NULL
                       ORDER BY occurred_at DESC LIMIT 1""",
                    (did, channel.get("channel_key")),
                ).fetchone()
                channel["sample_source_entity"] = source_row["source_entity"] if source_row else None
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

            # When an already discovered channel is classified as the direct
            # point, initialize the logical circuit from its last known state.
            # This makes the circuit immediately coherent without waiting for
            # another physical transition after configuration.
            if role == "direct" and light_id:
                observed=c.execute("SELECT state,COALESCE(last_changed_at,last_observed_at) changed_at FROM lca_channel_state WHERE device_id=? AND channel_key=?",(did,ch)).fetchone()
                if observed and str(observed["state"] or "").lower() in {"on","off"}:
                    self._set_circuit_state(c,light_id,observed["state"],observed["changed_at"] or now,"direct_configuration_baseline",None,now)
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

    @staticmethod
    def _typical_hour_window(hour_seconds, coverage=0.70):
        """Shortest circular hour window covering the requested usage share."""
        values = [max(0, int(x or 0)) for x in (hour_seconds or [0] * 24)]
        if len(values) != 24:
            values = (values + [0] * 24)[:24]
        total = sum(values)
        if total <= 0:
            return None, None, 0.0

        target = total * float(coverage)
        doubled = values + values
        best = None
        for start in range(24):
            acc = 0
            for length in range(1, 25):
                acc += doubled[start + length - 1]
                if acc >= target:
                    candidate = (length, -acc, start)
                    if best is None or candidate < best:
                        best = candidate
                    break

        if best is None:
            return None, None, 0.0
        length, neg_acc, start = best
        end = (start + length) % 24
        covered = (-neg_acc) * 100.0 / total
        return start, end, round(covered, 1)

    def _split_interval_into_local_hours(self, start_utc, end_utc):
        """Yield (weekday, hour, seconds) slices in configured local timezone."""
        cursor = start_utc
        while cursor < end_utc:
            local = cursor.astimezone(self.local_timezone)
            local_hour_start = local.replace(minute=0, second=0, microsecond=0)
            next_local = local_hour_start + timedelta(hours=1)
            boundary = next_local.astimezone(timezone.utc)
            if boundary <= cursor:
                boundary = cursor + timedelta(hours=1)
            segment_end = min(end_utc, boundary)
            seconds = max(0, int((segment_end - cursor).total_seconds()))
            if seconds:
                yield local.weekday(), local.hour, seconds
            cursor = segment_end

    def time_patterns(self, hours=168, location_name=None, light_id=None):
        """LCA 0.4.1 Time Patterns derived only from canonical circuit sessions."""
        hours = max(1, min(720, int(hours or 168)))
        period_end = datetime.now(timezone.utc)
        period_start = period_end - timedelta(hours=hours)
        location_filter = str(location_name or "").strip() or None
        light_filter = str(light_id or "").strip() or None

        hour_seconds = [0] * 24
        weekday_seconds = [0] * 7
        weekday_sessions = [0] * 7
        heatmap_seconds = [[0] * 24 for _ in range(7)]
        location_map = {}
        circuit_map = {}

        with self.db.connect() as c:
            lights = [dict(r) for r in c.execute("""
                SELECT light_id,circuit_id,name,COALESCE(location_name,'Ambiente não informado') location_name
                FROM lca_light_assets
                WHERE archived_at IS NULL
                ORDER BY location_name,name
            """).fetchall()]

            filter_options = {
                "locations": sorted(
                    {str(x["location_name"]) for x in lights},
                    key=lambda x: x.casefold(),
                ),
                "circuits": [
                    {
                        "light_id": x["light_id"],
                        "circuit_id": x.get("circuit_id"),
                        "name": x.get("name") or "Circuito",
                        "location_name": x.get("location_name") or "Ambiente não informado",
                    }
                    for x in lights
                ],
            }

            allowed = {
                x["light_id"]
                for x in lights
                if (not location_filter or x["location_name"] == location_filter)
                and (not light_filter or x["light_id"] == light_filter)
            }

            sessions = [dict(r) for r in c.execute("""
                SELECT s.session_id,s.light_id,s.started_at,s.ended_at,s.status,
                       l.circuit_id,l.name,
                       COALESCE(l.location_name,'Ambiente não informado') location_name
                FROM lca_circuit_sessions s
                JOIN lca_light_assets l ON l.light_id=s.light_id
                WHERE l.archived_at IS NULL
                  AND s.started_at<=?
                  AND (s.ended_at IS NULL OR s.ended_at>=?)
                ORDER BY s.started_at
            """, (period_end.isoformat(), period_start.isoformat())).fetchall()]

        observed_sessions = 0
        total_seconds = 0
        longest_seconds = 0

        for session in sessions:
            if session["light_id"] not in allowed:
                continue
            raw_start = self._parse_time(session["started_at"])
            raw_end = self._parse_time(session["ended_at"]) if session.get("ended_at") else period_end
            observed_start = max(period_start, raw_start)
            observed_end = min(period_end, raw_end)
            if observed_end <= observed_start:
                continue

            observed = max(0, int((observed_end - observed_start).total_seconds()))
            if observed <= 0:
                continue

            observed_sessions += 1
            total_seconds += observed
            longest_seconds = max(longest_seconds, observed)

            start_local = observed_start.astimezone(self.local_timezone)
            weekday_sessions[start_local.weekday()] += 1

            location = session.get("location_name") or "Ambiente não informado"
            loc = location_map.setdefault(location, {
                "location_name": location,
                "total_on_seconds": 0,
                "session_count": 0,
                "longest_session_seconds": 0,
                "circuits": set(),
            })
            loc["total_on_seconds"] += observed
            loc["session_count"] += 1
            loc["longest_session_seconds"] = max(loc["longest_session_seconds"], observed)
            loc["circuits"].add(session["light_id"])

            circuit = circuit_map.setdefault(session["light_id"], {
                "light_id": session["light_id"],
                "circuit_id": session.get("circuit_id"),
                "name": session.get("name") or "Circuito",
                "location_name": location,
                "total_on_seconds": 0,
                "session_count": 0,
            })
            circuit["total_on_seconds"] += observed
            circuit["session_count"] += 1

            for weekday, hour, seconds in self._split_interval_into_local_hours(observed_start, observed_end):
                hour_seconds[hour] += seconds
                weekday_seconds[weekday] += seconds
                heatmap_seconds[weekday][hour] += seconds

        peak_hour = max(range(24), key=lambda h: hour_seconds[h]) if total_seconds else None
        typical_start, typical_end, typical_coverage = self._typical_hour_window(hour_seconds, 0.70)

        weekday_total = sum(weekday_seconds[:5])
        weekend_total = sum(weekday_seconds[5:])
        night_total = sum(hour_seconds[22:]) + sum(hour_seconds[:6])

        by_hour = [
            {
                "hour": h,
                "seconds": hour_seconds[h],
                "minutes": round(hour_seconds[h] / 60.0, 1),
                "share_pct": round(hour_seconds[h] * 100.0 / total_seconds, 1) if total_seconds else 0.0,
            }
            for h in range(24)
        ]
        by_weekday = [
            {
                "weekday": idx,
                "label": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][idx],
                "seconds": weekday_seconds[idx],
                "minutes": round(weekday_seconds[idx] / 60.0, 1),
                "session_count": weekday_sessions[idx],
                "share_pct": round(weekday_seconds[idx] * 100.0 / total_seconds, 1) if total_seconds else 0.0,
            }
            for idx in range(7)
        ]

        heatmap = [
            {
                "weekday": day,
                "label": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][day],
                "hours": [
                    {
                        "hour": hour,
                        "seconds": heatmap_seconds[day][hour],
                        "minutes": round(heatmap_seconds[day][hour] / 60.0, 1),
                    }
                    for hour in range(24)
                ],
            }
            for day in range(7)
        ]

        locations = []
        for item in location_map.values():
            sessions_count = item["session_count"]
            locations.append({
                "location_name": item["location_name"],
                "total_on_seconds": item["total_on_seconds"],
                "session_count": sessions_count,
                "average_session_seconds": int(item["total_on_seconds"] / sessions_count) if sessions_count else 0,
                "longest_session_seconds": item["longest_session_seconds"],
                "circuits_used": len(item["circuits"]),
            })
        locations.sort(key=lambda x: (-x["total_on_seconds"], x["location_name"].casefold()))

        circuits = list(circuit_map.values())
        for item in circuits:
            item["average_session_seconds"] = (
                int(item["total_on_seconds"] / item["session_count"])
                if item["session_count"] else 0
            )
        circuits.sort(key=lambda x: (-x["total_on_seconds"], str(x["name"]).casefold()))

        insights = {
            "typical_window_start_hour": typical_start,
            "typical_window_end_hour": typical_end,
            "typical_window_coverage_pct": typical_coverage,
            "peak_hour": peak_hour,
            "weekday_share_pct": round(weekday_total * 100.0 / total_seconds, 1) if total_seconds else 0.0,
            "weekend_share_pct": round(weekend_total * 100.0 / total_seconds, 1) if total_seconds else 0.0,
            "night_share_pct": round(night_total * 100.0 / total_seconds, 1) if total_seconds else 0.0,
        }

        return {
            "period": {
                "hours": hours,
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
                "timezone": self.timezone_name,
            },
            "filters": {
                "location_name": location_filter,
                "light_id": light_filter,
            },
            "filter_options": filter_options,
            "summary": {
                "total_on_seconds": total_seconds,
                "session_count": observed_sessions,
                "average_session_seconds": int(total_seconds / observed_sessions) if observed_sessions else 0,
                "longest_session_seconds": longest_seconds,
            },
            "insights": insights,
            "by_hour": by_hour,
            "by_weekday": by_weekday,
            "heatmap": heatmap,
            "by_location": locations,
            "by_circuit": circuits,
        }

    @staticmethod
    def _preference_classification(share_pct):
        share = float(share_pct or 0)
        if share >= 75:
            return "strong"
        if share >= 60:
            return "moderate"
        return "balanced"

    @staticmethod
    def _origin_family(origin_mode):
        mode = str(origin_mode or "unknown").strip().lower()
        if mode in {"local", "local_probable"}:
            return "local"
        if mode in {"home_assistant_user", "remote", "app", "user_remote"}:
            return "remote"
        if mode in {"automation", "automation_probable", "scene", "script"}:
            return "automation"
        return "unknown"

    def interaction_preference(self, hours=168, location_name=None, light_id=None):
        """LCA 0.4.2: quantify how each logical circuit is normally operated.

        Read-only analytics over already consolidated interaction events.
        It never changes correlation, canonical state or usage sessions.
        """
        hours = max(1, min(720, int(hours or 168)))
        now = datetime.now(timezone.utc)
        current_start = now - timedelta(hours=hours)
        previous_start = current_start - timedelta(hours=hours)
        location_filter = str(location_name or "").strip() or None
        light_filter = str(light_id or "").strip() or None

        with self.db.connect() as c:
            lights = [dict(r) for r in c.execute("""
                SELECT light_id,circuit_id,name,
                       COALESCE(location_name,'Ambiente não informado') location_name
                FROM lca_light_assets
                WHERE archived_at IS NULL
                ORDER BY location_name,name
            """).fetchall()]

            filter_options = {
                "locations": sorted(
                    {str(x["location_name"]) for x in lights},
                    key=lambda x: x.casefold(),
                ),
                "circuits": [
                    {
                        "light_id": x["light_id"],
                        "circuit_id": x.get("circuit_id"),
                        "name": x.get("name") or "Circuito",
                        "location_name": x.get("location_name") or "Ambiente não informado",
                    }
                    for x in lights
                ],
            }

            allowed = {
                x["light_id"]
                for x in lights
                if (not location_filter or x["location_name"] == location_filter)
                and (not light_filter or x["light_id"] == light_filter)
            }

            rows = [dict(r) for r in c.execute("""
                SELECT
                    e.lca_event_id,e.device_id,e.channel_key,e.occurred_at,
                    e.origin_mode,e.interaction_kind,e.source_entity,
                    e.source_device_ref,e.source_channel_ref,
                    d.name device_name,d.position_label device_position,
                    ch.relationship_type,
                    COALESCE(ch.light_asset_id,ch.related_light_id) light_id,
                    l.circuit_id,l.name circuit_name,
                    COALESCE(l.location_name,'Ambiente não informado') location_name,
                    COALESCE(ch.name,ch.channel_key,e.source_channel_ref,'Estado') channel_name
                FROM lca_events e
                JOIN lca_devices d ON d.device_id=e.device_id
                LEFT JOIN lca_channels ch
                  ON ch.device_id=e.device_id AND ch.channel_key=e.channel_key
                LEFT JOIN lca_light_assets l
                  ON l.light_id=COALESCE(ch.light_asset_id,ch.related_light_id)
                WHERE e.kind='interaction'
                  AND e.occurred_at>=?
                  AND e.occurred_at<=?
                  AND d.status<>'ignored'
                  AND (e.channel_key IS NULL OR ch.enabled=1)
                  AND l.archived_at IS NULL
                ORDER BY e.occurred_at
            """, (previous_start.isoformat(), now.isoformat())).fetchall()]

        def point_key(row):
            return (
                str(row.get("device_id") or ""),
                str(row.get("channel_key") or row.get("source_channel_ref") or "main"),
            )

        def point_label(row):
            position = str(row.get("device_position") or "").strip()
            device = str(
                row.get("device_name")
                or row.get("source_device_ref")
                or row.get("device_id")
                or "Ponto"
            ).strip()
            channel = str(
                row.get("channel_name")
                or row.get("channel_key")
                or ""
            ).strip()
            base = position or device
            lower = channel.lower()
            if channel and lower not in {"main", "estado"}:
                display_channel = (
                    channel.upper()
                    if lower.startswith("l") and lower[1:].isdigit()
                    else channel
                )
                return f"{base} · {display_channel}"
            return base

        def aggregate(period_rows):
            total = 0
            role_counts = {}
            origin_counts = {}
            point_map = {}
            circuit_map = {}

            for row in period_rows:
                lid = row.get("light_id")
                if not lid or lid not in allowed:
                    continue

                total += 1
                role = str(row.get("relationship_type") or "unassigned").lower()
                if role not in {"direct", "parallel", "scene"}:
                    role = "other"
                role_counts[role] = role_counts.get(role, 0) + 1

                origin = self._origin_family(row.get("origin_mode"))
                origin_counts[origin] = origin_counts.get(origin, 0) + 1

                pkey = point_key(row)
                p = point_map.setdefault(pkey, {
                    "device_id": pkey[0],
                    "channel_key": pkey[1],
                    "label": point_label(row),
                    "role": role,
                    "light_id": lid,
                    "circuit_id": row.get("circuit_id"),
                    "circuit_name": row.get("circuit_name") or "Circuito",
                    "location_name": row.get("location_name") or "Ambiente não informado",
                    "interactions": 0,
                    "origin_counts": {
                        "local": 0, "remote": 0,
                        "automation": 0, "unknown": 0
                    },
                })
                p["interactions"] += 1
                p["origin_counts"][origin] += 1

                circuit = circuit_map.setdefault(lid, {
                    "light_id": lid,
                    "circuit_id": row.get("circuit_id"),
                    "name": row.get("circuit_name") or "Circuito",
                    "location_name": row.get("location_name") or "Ambiente não informado",
                    "interactions": 0,
                    "points": {},
                })
                circuit["interactions"] += 1
                cp = circuit["points"].setdefault(pkey, {
                    "label": p["label"],
                    "role": role,
                    "interactions": 0,
                })
                cp["interactions"] += 1

            points = []
            for p in point_map.values():
                circuit_total = circuit_map.get(
                    p["light_id"], {}
                ).get("interactions", 0)
                p["share_in_circuit_pct"] = round(
                    p["interactions"] * 100.0 / circuit_total, 1
                ) if circuit_total else 0.0
                p["share_overall_pct"] = round(
                    p["interactions"] * 100.0 / total, 1
                ) if total else 0.0
                points.append(p)
            points.sort(
                key=lambda x: (-x["interactions"], x["label"].casefold())
            )

            circuits = []
            for circuit in circuit_map.values():
                point_values = list(circuit["points"].values())
                point_values.sort(
                    key=lambda x: (-x["interactions"], x["label"].casefold())
                )
                dominant = point_values[0] if point_values else None
                dominant_share = round(
                    dominant["interactions"] * 100.0 / circuit["interactions"], 1
                ) if dominant and circuit["interactions"] else 0.0
                circuits.append({
                    "light_id": circuit["light_id"],
                    "circuit_id": circuit["circuit_id"],
                    "name": circuit["name"],
                    "location_name": circuit["location_name"],
                    "interactions": circuit["interactions"],
                    "point_count": len(point_values),
                    "dominant_point": dominant["label"] if dominant else None,
                    "dominant_role": dominant["role"] if dominant else None,
                    "dominant_share_pct": dominant_share,
                    "classification": self._preference_classification(
                        dominant_share
                    ),
                    "points": point_values,
                })
            circuits.sort(
                key=lambda x: (
                    -x["interactions"],
                    x["location_name"].casefold(),
                    x["name"].casefold(),
                )
            )

            return {
                "total": total,
                "role_counts": role_counts,
                "origin_counts": origin_counts,
                "points": points,
                "circuits": circuits,
            }

        current_rows = [
            r for r in rows
            if self._parse_time(r["occurred_at"]) >= current_start
        ]
        previous_rows = [
            r for r in rows
            if previous_start
            <= self._parse_time(r["occurred_at"])
            < current_start
        ]

        current = aggregate(current_rows)
        previous = aggregate(previous_rows)

        prev_points = {
            (x["device_id"], x["channel_key"], x["light_id"]): x
            for x in previous["points"]
        }
        point_trends = []
        for point in current["points"]:
            prev = prev_points.get((
                point["device_id"],
                point["channel_key"],
                point["light_id"],
            ))
            previous_share = (
                float(prev["share_in_circuit_pct"]) if prev else 0.0
            )
            delta = round(
                float(point["share_in_circuit_pct"]) - previous_share, 1
            )
            point_trends.append({
                "device_id": point["device_id"],
                "channel_key": point["channel_key"],
                "light_id": point["light_id"],
                "label": point["label"],
                "circuit_name": point["circuit_name"],
                "location_name": point["location_name"],
                "current_share_pct": point["share_in_circuit_pct"],
                "previous_share_pct": previous_share,
                "delta_pct_points": delta,
                "current_interactions": point["interactions"],
                "previous_interactions": prev["interactions"] if prev else 0,
            })
        point_trends.sort(
            key=lambda x: (
                -abs(x["delta_pct_points"]),
                -x["current_interactions"],
            )
        )

        def pct(count):
            return round(
                count * 100.0 / current["total"], 1
            ) if current["total"] else 0.0

        direct = current["role_counts"].get("direct", 0)
        parallel = current["role_counts"].get("parallel", 0)
        scene = current["role_counts"].get("scene", 0)
        role_known = direct + parallel + scene

        origin_breakdown = [
            {
                "key": key,
                "value": current["origin_counts"].get(key, 0),
                "share_pct": pct(current["origin_counts"].get(key, 0)),
            }
            for key in ("local", "remote", "automation", "unknown")
        ]
        role_breakdown = [
            {"key": "direct", "value": direct, "share_pct": pct(direct)},
            {"key": "parallel", "value": parallel, "share_pct": pct(parallel)},
            {"key": "scene", "value": scene, "share_pct": pct(scene)},
            {
                "key": "other",
                "value": current["role_counts"].get("other", 0),
                "share_pct": pct(current["role_counts"].get("other", 0)),
            },
        ]

        dominant_circuits = [
            x for x in current["circuits"]
            if x["classification"] in {"strong", "moderate"}
        ]
        strongest = max(
            current["points"],
            key=lambda x: (
                x["interactions"],
                x["share_in_circuit_pct"],
            ),
            default=None,
        )

        return {
            "period": {
                "hours": hours,
                "start": current_start.isoformat(),
                "end": now.isoformat(),
                "previous_start": previous_start.isoformat(),
                "previous_end": current_start.isoformat(),
            },
            "filters": {
                "location_name": location_filter,
                "light_id": light_filter,
            },
            "filter_options": filter_options,
            "summary": {
                "interactions": current["total"],
                "points_used": len(current["points"]),
                "circuits_observed": len(current["circuits"]),
                "dominant_circuits": len(dominant_circuits),
                "strongest_point": (
                    strongest["label"] if strongest else None
                ),
                "strongest_point_interactions": (
                    strongest["interactions"] if strongest else 0
                ),
                "direct_share_pct": round(
                    direct * 100.0 / role_known, 1
                ) if role_known else 0.0,
                "parallel_share_pct": round(
                    parallel * 100.0 / role_known, 1
                ) if role_known else 0.0,
            },
            "origin_breakdown": origin_breakdown,
            "role_breakdown": role_breakdown,
            "points": current["points"],
            "circuits": current["circuits"],
            "trends": point_trends,
        }

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
                       cst.state state,
                       cst.last_changed_at last_updated_at
                FROM lca_light_assets l
                LEFT JOIN lca_circuit_state cst ON cst.light_id=l.light_id
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

            # LCA 0.4.0 — Circuit Usage Analytics. Sessions are clipped to the
            # selected dashboard period, so a circuit that was already ON at
            # the period boundary contributes only the observed interval.
            period_start = self._parse_time(since)
            period_end = datetime.now(timezone.utc)
            period_seconds = max(1, int((period_end - period_start).total_seconds()))
            usage_map = {light["light_id"]: {
                "light_id": light["light_id"],
                "circuit_id": light.get("circuit_id"),
                "name": light.get("name"),
                "location_name": light.get("location_name"),
                "state": light.get("state"),
                "total_on_seconds": 0,
                "session_count": 0,
                "average_session_seconds": 0,
                "longest_session_seconds": 0,
                "utilization_pct": 0.0,
                "current_session_seconds": 0,
                "current_session_started_at": None,
            } for light in current_lights}
            usage_sessions = [dict(r) for r in c.execute("""
                SELECT s.*,l.circuit_id,l.name,l.location_name
                FROM lca_circuit_sessions s
                JOIN lca_light_assets l ON l.light_id=s.light_id
                WHERE l.archived_at IS NULL AND s.started_at<=?
                  AND (s.ended_at IS NULL OR s.ended_at>=?)
                ORDER BY s.started_at
            """, (period_end.isoformat(), since)).fetchall()]
            for session in usage_sessions:
                item = usage_map.get(session["light_id"])
                if not item:
                    continue
                session_start = self._parse_time(session["started_at"])
                session_end = self._parse_time(session["ended_at"]) if session.get("ended_at") else period_end
                observed_start = max(period_start, session_start)
                observed_end = min(period_end, session_end)
                observed_seconds = max(0, int((observed_end-observed_start).total_seconds()))
                if observed_seconds <= 0:
                    continue
                item["total_on_seconds"] += observed_seconds
                item["session_count"] += 1
                item["longest_session_seconds"] = max(item["longest_session_seconds"], observed_seconds)
                if not session.get("ended_at"):
                    item["current_session_seconds"] = max(0, int((period_end-session_start).total_seconds()))
                    item["current_session_started_at"] = session["started_at"]
            usage_by_circuit = []
            for item in usage_map.values():
                if item["session_count"]:
                    item["average_session_seconds"] = int(item["total_on_seconds"] / item["session_count"])
                item["utilization_pct"] = round(min(100.0, item["total_on_seconds"] * 100.0 / period_seconds), 1)
                usage_by_circuit.append(item)
            usage_by_circuit.sort(key=lambda x: (-x["total_on_seconds"], str(x.get("location_name") or ""), str(x.get("name") or "")))
            usage_total_seconds = sum(x["total_on_seconds"] for x in usage_by_circuit)
            usage_session_count = sum(x["session_count"] for x in usage_by_circuit)
            usage_summary = {
                "total_on_seconds": usage_total_seconds,
                "session_count": usage_session_count,
                "average_session_seconds": int(usage_total_seconds / usage_session_count) if usage_session_count else 0,
                "longest_session_seconds": max((x["longest_session_seconds"] for x in usage_by_circuit), default=0),
                "circuits_used": sum(1 for x in usage_by_circuit if x["total_on_seconds"] > 0),
                "period_seconds": period_seconds,
            }
            totals["usage_total_on_seconds"] = usage_summary["total_on_seconds"]
            totals["usage_session_count"] = usage_summary["session_count"]
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
                "role_breakdown": role_breakdown, "usage_summary": usage_summary, "usage_by_circuit": usage_by_circuit,
                "configuration_quality": configuration_quality, "recent_events": recent[:30],
                "action_pagination": {
                    "page": action_page,
                    "page_size": action_page_size,
                    "total": action_total,
                    "total_pages": max(1, (action_total + action_page_size - 1) // action_page_size)
                },
                "updated_at": datetime.now(timezone.utc).isoformat()}
