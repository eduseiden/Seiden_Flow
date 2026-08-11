from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from statistics import median


class ITARepository:
    def __init__(self, db, timezone_name='America/Sao_Paulo'):
        self.db = db
        self.timezone_name = timezone_name
        self._init_schema()

    def _init_schema(self):
        with self.db.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS ita_snapshots(
              id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL UNIQUE,occurred_at TEXT NOT NULL,
              connection_id TEXT NOT NULL,connection_name TEXT,connector TEXT,system_id TEXT NOT NULL,system_name TEXT,
              chassis_ids_json TEXT NOT NULL DEFAULT '[]',created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_ita_snapshots_system_time ON ita_snapshots(system_id,occurred_at DESC);
            CREATE TABLE IF NOT EXISTS ita_measurements(
              id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL,occurred_at TEXT NOT NULL,system_id TEXT NOT NULL,
              sensor_id TEXT NOT NULL,sensor_name TEXT,physical_context TEXT,metric_kind TEXT NOT NULL,reading REAL NOT NULL,
              units TEXT,health TEXT,state TEXT,range_min REAL,range_max REAL,thresholds_json TEXT NOT NULL DEFAULT '{}',
              related_items_json TEXT NOT NULL DEFAULT '[]',odata_id TEXT,
              UNIQUE(event_id,sensor_id));
            CREATE INDEX IF NOT EXISTS idx_ita_measurements_system_time ON ita_measurements(system_id,occurred_at DESC);
            CREATE INDEX IF NOT EXISTS idx_ita_measurements_sensor_time ON ita_measurements(system_id,sensor_id,occurred_at DESC);
            CREATE TABLE IF NOT EXISTS ita_events(
              id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL, system_id TEXT NOT NULL,
              event_type TEXT NOT NULL, severity TEXT NOT NULL, sensor_id TEXT, sensor_name TEXT,
              previous_state TEXT, current_state TEXT, details_json TEXT NOT NULL DEFAULT '{}', source_event_id TEXT,
              UNIQUE(source_event_id,event_type,sensor_id,current_state));
            CREATE INDEX IF NOT EXISTS idx_ita_events_system_time ON ita_events(system_id,occurred_at DESC);
            CREATE TABLE IF NOT EXISTS ita_assets(
              system_id TEXT PRIMARY KEY,status TEXT NOT NULL DEFAULT 'active',
              status_changed_at TEXT NOT NULL,status_reason TEXT NOT NULL DEFAULT '',
              updated_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_ita_assets_status ON ita_assets(status);
            ''')

    @staticmethod
    def _parse_dt(value):
        if not value:
            return None
        try:
            s = str(value).replace('Z', '+00:00')
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _threshold_value(thresholds, name):
        x = thresholds.get(name) if isinstance(thresholds, dict) else None
        try:
            return float(x.get('reading')) if isinstance(x, dict) and x.get('reading') is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _severity(health, reading, thresholds):
        h = str(health or '').lower()
        if h in {'critical', 'fatal'}:
            return 'critical'
        fatal = ITARepository._threshold_value(thresholds, 'UpperFatal')
        critical = ITARepository._threshold_value(thresholds, 'UpperCritical')
        caution = ITARepository._threshold_value(thresholds, 'UpperCaution')
        lower_critical = ITARepository._threshold_value(thresholds, 'LowerCritical')
        lower_caution = ITARepository._threshold_value(thresholds, 'LowerCaution')
        if fatal is not None and reading >= fatal:
            return 'critical'
        if critical is not None and reading >= critical:
            return 'critical'
        if lower_critical is not None and reading <= lower_critical:
            return 'critical'
        if h in {'warning', 'caution'}:
            return 'attention'
        if caution is not None and reading >= caution:
            return 'attention'
        if lower_caution is not None and reading <= lower_caution:
            return 'attention'
        return 'normal'

    def _previous_sensor_state(self, c, system_id, sensor_id):
        r = c.execute('''SELECT reading,health,thresholds_json FROM ita_measurements
          WHERE system_id=? AND sensor_id=? ORDER BY occurred_at DESC LIMIT 1''', (system_id, sensor_id)).fetchone()
        if not r:
            return None
        d = dict(r)
        thresholds = json.loads(d.get('thresholds_json') or '{}')
        return self._severity(d.get('health'), float(d.get('reading')), thresholds)

    def _previous_snapshot_time(self, c, system_id):
        r = c.execute('SELECT occurred_at FROM ita_snapshots WHERE system_id=? ORDER BY occurred_at DESC LIMIT 1', (system_id,)).fetchone()
        return self._parse_dt(r['occurred_at']) if r else None

    @staticmethod
    def _normalize_asset_status(value):
        status = str(value or 'active').strip().lower()
        if status not in {'active', 'hidden', 'decommissioned'}:
            raise ValueError('invalid_asset_status')
        return status

    def _ensure_asset(self, c, system_id):
        now = datetime.now(timezone.utc).isoformat()
        c.execute('''INSERT OR IGNORE INTO ita_assets(system_id,status,status_changed_at,status_reason,updated_at)
          VALUES(?,?,?,?,?)''', (system_id, 'active', now, '', now))

    def asset_status(self, system_id):
        with self.db.connect() as c:
            r = c.execute('SELECT system_id,status,status_changed_at,status_reason,updated_at FROM ita_assets WHERE system_id=?', (system_id,)).fetchone()
        if not r:
            return {'system_id': system_id, 'status': 'active', 'status_changed_at': None, 'status_reason': '', 'updated_at': None}
        return dict(r)

    def set_asset_status(self, system_id, status, reason=''):
        status = self._normalize_asset_status(status)
        reason = str(reason or '').strip()[:500]
        now = datetime.now(timezone.utc).isoformat()
        with self.db.connect() as c:
            self._ensure_asset(c, system_id)
            previous_row = c.execute('SELECT status FROM ita_assets WHERE system_id=?', (system_id,)).fetchone()
            previous = previous_row['status'] if previous_row else 'active'
            c.execute('''UPDATE ita_assets SET status=?,status_changed_at=?,status_reason=?,updated_at=? WHERE system_id=?''',
                      (status, now, reason, now, system_id))
            if previous != status:
                c.execute('''INSERT INTO ita_events(occurred_at,system_id,event_type,severity,sensor_id,sensor_name,previous_state,current_state,details_json,source_event_id)
                  VALUES(?,?,?,?,?,?,?,?,?,?)''',
                  (now, system_id, 'asset_status_changed', 'normal', None, None, previous, status,
                   json.dumps({'reason': reason}), None))
        return self.asset_status(system_id)

    def ingest(self, snapshot: dict) -> int:
        now = datetime.now(timezone.utc).isoformat()
        eid = snapshot.get('event_id')
        if not eid:
            return 0
        with self.db.connect() as c:
            self._ensure_asset(c, snapshot['system_id'])
            previous_time = self._previous_snapshot_time(c, snapshot['system_id'])
            previous_states = {
                m['sensor_id']: self._previous_sensor_state(c, snapshot['system_id'], m['sensor_id'])
                for m in snapshot['measurements']
            }
            try:
                c.execute('INSERT INTO ita_snapshots(event_id,occurred_at,connection_id,connection_name,connector,system_id,system_name,chassis_ids_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)', (
                    eid, snapshot['occurred_at'], snapshot['connection_id'], snapshot['connection_name'], snapshot['connector'], snapshot['system_id'], snapshot['system_name'], json.dumps(snapshot.get('chassis_ids', [])), now))
            except Exception as exc:
                if 'UNIQUE constraint failed' in str(exc):
                    return 0
                raise
            for m in snapshot['measurements']:
                c.execute('INSERT OR IGNORE INTO ita_measurements(event_id,occurred_at,system_id,sensor_id,sensor_name,physical_context,metric_kind,reading,units,health,state,range_min,range_max,thresholds_json,related_items_json,odata_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
                    eid, snapshot['occurred_at'], snapshot['system_id'], m['sensor_id'], m['sensor_name'], m['physical_context'], m['metric_kind'], m['reading'], m['units'], m['health'], m['state'], m.get('range_min'), m.get('range_max'), json.dumps(m.get('thresholds', {})), json.dumps(m.get('related_items', [])), m.get('odata_id')))
                current = self._severity(m['health'], m['reading'], m.get('thresholds', {}))
                previous = previous_states.get(m['sensor_id'])
                if previous is not None and previous != current:
                    c.execute('''INSERT OR IGNORE INTO ita_events(occurred_at,system_id,event_type,severity,sensor_id,sensor_name,previous_state,current_state,details_json,source_event_id)
                      VALUES(?,?,?,?,?,?,?,?,?,?)''', (
                        snapshot['occurred_at'], snapshot['system_id'], 'sensor_state_changed', current,
                        m['sensor_id'], m['sensor_name'], previous, current,
                        json.dumps({'reading': m['reading'], 'units': m['units'], 'health': m['health']}), eid))
            current_time = self._parse_dt(snapshot.get('occurred_at'))
            if previous_time and current_time and (current_time - previous_time).total_seconds() >= 180:
                c.execute('''INSERT OR IGNORE INTO ita_events(occurred_at,system_id,event_type,severity,sensor_id,sensor_name,previous_state,current_state,details_json,source_event_id)
                  VALUES(?,?,?,?,?,?,?,?,?,?)''', (
                    snapshot['occurred_at'], snapshot['system_id'], 'telemetry_recovered', 'normal', None, None,
                    'stale', 'normal', json.dumps({'gap_seconds': round((current_time - previous_time).total_seconds())}), eid))
        return len(snapshot['measurements'])

    def systems(self, view='active'):
        view = str(view or 'active').strip().lower()
        if view not in {'active', 'all', 'hidden', 'decommissioned'}:
            view = 'active'
        where = ''
        params = ()
        if view != 'all':
            where = " WHERE COALESCE(a.status,'active')=?"
            params = (view,)
        with self.db.connect() as c:
            rows = c.execute(f'''SELECT s.system_id,s.system_name,s.connection_id,s.connection_name,s.connector,s.occurred_at,
              COALESCE(a.status,'active') asset_status,a.status_changed_at,a.status_reason
              FROM ita_snapshots s
              JOIN (SELECT system_id,MAX(occurred_at) mx FROM ita_snapshots GROUP BY system_id) x
              ON s.system_id=x.system_id AND s.occurred_at=x.mx
              LEFT JOIN ita_assets a ON a.system_id=s.system_id
              {where}
              ORDER BY s.system_name''', params).fetchall()
        return [dict(r) for r in rows]

    def _latest_measurements(self, system_id):
        with self.db.connect() as c:
            snap = c.execute('SELECT * FROM ita_snapshots WHERE system_id=? ORDER BY occurred_at DESC LIMIT 1', (system_id,)).fetchone()
            if not snap:
                return None, []
            rows = c.execute('SELECT * FROM ita_measurements WHERE event_id=? ORDER BY physical_context,sensor_name', (snap['event_id'],)).fetchall()
        items = []
        for r in rows:
            d = dict(r)
            d['thresholds'] = json.loads(d.pop('thresholds_json') or '{}')
            d['related_items'] = json.loads(d.pop('related_items_json') or '[]')
            d['severity'] = self._severity(d['health'], d['reading'], d['thresholds'])
            items.append(d)
        return dict(snap), items

    @staticmethod
    def _temp_by_context(items, context):
        vals = [x for x in items if x['metric_kind'] == 'temperature' and str(x['physical_context']).lower() == context.lower()]
        return sum(x['reading'] for x in vals) / len(vals) if vals else None

    def _cadence_seconds(self, system_id):
        with self.db.connect() as c:
            rows = c.execute('SELECT occurred_at FROM ita_snapshots WHERE system_id=? ORDER BY occurred_at DESC LIMIT 8', (system_id,)).fetchall()
        times = [self._parse_dt(r['occurred_at']) for r in rows]
        times = [x for x in times if x]
        diffs = []
        for i in range(len(times) - 1):
            d = (times[i] - times[i + 1]).total_seconds()
            if 1 <= d <= 3600:
                diffs.append(d)
        return median(diffs) if diffs else None

    def _telemetry_freshness(self, system_id, occurred_at):
        last = self._parse_dt(occurred_at)
        if not last:
            return {'stale': True, 'age_seconds': None, 'expected_interval_seconds': None, 'stale_after_seconds': 180}
        cadence = self._cadence_seconds(system_id)
        stale_after = max(90, int((cadence or 60) * 3))
        age = max(0, (datetime.now(timezone.utc) - last).total_seconds())
        return {'stale': age > stale_after, 'age_seconds': round(age), 'expected_interval_seconds': round(cadence) if cadence else None, 'stale_after_seconds': stale_after}

    @staticmethod
    def _next_upper_threshold(item):
        if not item:
            return None
        reading = float(item['reading'])
        labels = [('UpperCaution', 'caution'), ('UpperCritical', 'critical'), ('UpperFatal', 'fatal')]
        candidates = []
        for key, label in labels:
            value = ITARepository._threshold_value(item.get('thresholds', {}), key)
            if value is not None and value > reading:
                candidates.append((value, label, key))
        if not candidates:
            return None
        value, label, key = min(candidates, key=lambda x: x[0])
        return {'label': label, 'threshold_key': key, 'threshold_value': value, 'headroom': round(value - reading, 2), 'units': item.get('units')}

    def _trend(self, system_id, context, hours=1):
        start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self.db.connect() as c:
            rows = c.execute('''SELECT occurred_at,reading FROM ita_measurements
              WHERE system_id=? AND metric_kind='temperature' AND lower(physical_context)=lower(?) AND occurred_at>=?
              ORDER BY occurred_at''', (system_id, context, start)).fetchall()
        if len(rows) < 2:
            return {'direction': 'insufficient', 'delta_c': None}
        first = float(rows[0]['reading'])
        last = float(rows[-1]['reading'])
        delta = round(last - first, 2)
        direction = 'rising' if delta >= 2 else ('falling' if delta <= -2 else 'stable')
        return {'direction': direction, 'delta_c': delta}

    def current(self, system_id):
        snap, items = self._latest_measurements(system_id)
        if not snap:
            return None
        intake = self._temp_by_context(items, 'Intake')
        exhaust = self._temp_by_context(items, 'Exhaust')
        ambient = self._temp_by_context(items, 'Room')
        cpu_items = [x for x in items if x['metric_kind'] == 'temperature' and str(x['physical_context']).lower() == 'cpu']
        hottest_cpu = max(cpu_items, key=lambda x: x['reading']) if cpu_items else None
        cpu = hottest_cpu['reading'] if hottest_cpu else None
        power_items = [x for x in items if x['metric_kind'] == 'power']
        preferred_power = [x for x in power_items if str(x['physical_context']).lower() == 'chassis' or 'total' in str(x['sensor_name']).lower() or 'total' in str(x['sensor_id']).lower()]
        power_item = preferred_power[0] if preferred_power else (power_items[0] if len(power_items) == 1 else None)
        power = power_item['reading'] if power_item else (sum(x['reading'] for x in power_items) if power_items else None)
        power_util = None
        if power_item and power_item.get('range_max') not in (None, 0):
            power_util = round((float(power_item['reading']) / float(power_item['range_max'])) * 100, 1)
        fan_items = [x for x in items if x['metric_kind'] == 'fan_speed']
        fans = [x['reading'] for x in fan_items]
        rank = {'normal': 0, 'attention': 1, 'critical': 2}
        state = max((x['severity'] for x in items), key=lambda v: rank[v], default='normal')
        if any(str(x['state']).lower() not in {'enabled', 'unknown'} for x in items):
            state = 'attention' if state == 'normal' else state
        freshness = self._telemetry_freshness(system_id, snap['occurred_at'])
        if freshness['stale']:
            state = 'stale'

        def delta(a, b):
            return round(a - b, 2) if a is not None and b is not None else None

        fan_spread = round(max(fans) - min(fans), 1) if len(fans) >= 2 else None
        return {
            'system': {'system_id': snap['system_id'], 'system_name': snap['system_name'], 'connection_id': snap['connection_id'], 'connection_name': snap['connection_name'], 'connector': snap['connector'], 'last_seen': snap['occurred_at'], **self.asset_status(system_id)},
            'state': state,
            'freshness': freshness,
            'ambient_c': ambient,
            'intake_c': intake,
            'cpu_c': cpu,
            'exhaust_c': exhaust,
            'power_w': power,
            'power_utilization_pct': power_util,
            'fan_avg_pct': round(sum(fans) / len(fans), 1) if fans else None,
            'fan_spread_pct': fan_spread,
            'fan_min_pct': min(fans) if fans else None,
            'fan_max_pct': max(fans) if fans else None,
            'thermal_headroom': self._next_upper_threshold(hottest_cpu),
            'deltas': {
                'ambient_to_intake_c': delta(intake, ambient),
                'intake_to_cpu_c': delta(cpu, intake),
                'intake_to_exhaust_c': delta(exhaust, intake),
            },
            'trends': {
                'cpu': self._trend(system_id, 'CPU'),
                'intake': self._trend(system_id, 'Intake'),
                'exhaust': self._trend(system_id, 'Exhaust'),
                'ambient': self._trend(system_id, 'Room'),
            },
            'measurements': items,
        }

    def portfolio(self, view='active'):
        out = []
        for s in self.systems(view):
            cur = self.current(s['system_id'])
            if cur:
                out.append(cur)
        counts = {'normal': 0, 'attention': 0, 'critical': 0, 'stale': 0}
        for x in out:
            counts[x['state']] = counts.get(x['state'], 0) + 1
        with self.db.connect() as c:
            asset_rows = c.execute('''SELECT COALESCE(a.status,'active') status,COUNT(*) count
              FROM (SELECT DISTINCT system_id FROM ita_snapshots) s
              LEFT JOIN ita_assets a ON a.system_id=s.system_id GROUP BY COALESCE(a.status,'active')''').fetchall()
        asset_counts = {'active': 0, 'hidden': 0, 'decommissioned': 0}
        for r in asset_rows:
            asset_counts[r['status']] = r['count']
        return {'items': out, 'counts': counts, 'asset_counts': asset_counts, 'view': view, 'total': len(out), 'updated_at': datetime.now(timezone.utc).isoformat()}

    def history(self, system_id, hours=24):
        hours = max(1, min(int(hours), 8760))
        start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self.db.connect() as c:
            rows = c.execute('SELECT occurred_at,sensor_id,sensor_name,physical_context,metric_kind,reading,units FROM ita_measurements WHERE system_id=? AND occurred_at>=? ORDER BY occurred_at', (system_id, start)).fetchall()
        return {'system_id': system_id, 'hours': hours, 'items': [dict(r) for r in rows]}

    def events(self, system_id, limit=100):
        limit = max(1, min(int(limit), 500))
        with self.db.connect() as c:
            rows = c.execute('''SELECT occurred_at,event_type,severity,sensor_id,sensor_name,previous_state,current_state,details_json
              FROM ita_events WHERE system_id=? ORDER BY occurred_at DESC LIMIT ?''', (system_id, limit)).fetchall()
        items = []
        for r in rows:
            d = dict(r)
            d['details'] = json.loads(d.pop('details_json') or '{}')
            items.append(d)
        return {'system_id': system_id, 'items': items}
