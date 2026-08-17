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

    @staticmethod
    def _software_severity(item):
        """Guardrails genéricos quando a fonte não fornece thresholds nativos.

        Aplicados somente a métricas percentuais amplamente interpretáveis.
        Thresholds nativos, quando presentes, continuam tendo precedência e
        são sempre preservados como evidência.
        """
        kind = str(item.get('metric_kind') or '')
        try:
            reading = float(item.get('reading'))
        except (TypeError, ValueError):
            return 'normal'
        limits = {
            'memory_used_pct': (80.0, 95.0),
            'swap_used_pct': (60.0, 85.0),
            'storage_used_pct': (80.0, 90.0),
            'cpu_used_pct': (85.0, 95.0),
        }
        if kind not in limits:
            return 'normal'
        attention, critical = limits[kind]
        if reading >= critical:
            return 'critical'
        if reading >= attention:
            return 'attention'
        return 'normal'

    @classmethod
    def _item_severity(cls, item):
        native = cls._severity(item.get('health'), float(item.get('reading')), item.get('thresholds') or {})
        software = cls._software_severity(item)
        rank = {'normal': 0, 'attention': 1, 'critical': 2}
        return native if rank.get(native, 0) >= rank.get(software, 0) else software

    def _previous_sensor_state(self, c, system_id, sensor_id):
        r = c.execute('''SELECT sensor_id,sensor_name,physical_context,metric_kind,reading,units,health,thresholds_json FROM ita_measurements
          WHERE system_id=? AND sensor_id=? ORDER BY occurred_at DESC LIMIT 1''', (system_id, sensor_id)).fetchone()
        if not r:
            return None
        d = dict(r)
        d['thresholds'] = json.loads(d.pop('thresholds_json') or '{}')
        return self._item_severity(d)

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

    def delete_asset(self, system_id):
        """Permanently remove one local/Bridge ITA asset and its ITA history.

        This intentionally deletes only ITA domain tables. Raw platform events are
        preserved; if the source starts publishing again, normal ingestion can
        recreate the asset from new telemetry.
        """
        system_id = str(system_id or '').strip()
        if not system_id:
            raise ValueError('invalid_system_id')
        tables = ('ita_measurements', 'ita_events', 'ita_snapshots', 'ita_assets')
        with self.db.connect() as c:
            exists = c.execute(
                '''SELECT 1 FROM ita_snapshots WHERE system_id=? LIMIT 1''',
                (system_id,),
            ).fetchone() or c.execute(
                '''SELECT 1 FROM ita_assets WHERE system_id=? LIMIT 1''',
                (system_id,),
            ).fetchone()
            if not exists:
                return None
            deleted = {}
            for table in tables:
                row = c.execute(
                    f'''SELECT COUNT(*) AS n FROM {table} WHERE system_id=?''',
                    (system_id,),
                ).fetchone()
                deleted[table] = int(row['n'] if row else 0)
                c.execute(f'''DELETE FROM {table} WHERE system_id=?''', (system_id,))
        return {'system_id': system_id, 'deleted': deleted, 'status': 'deleted'}

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
                current = self._item_severity(m)
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
            d['severity'] = self._item_severity(d)
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

    def _telemetry_freshness(self, system_id, occurred_at, connector=None):
        last = self._parse_dt(occurred_at)
        if not last:
            return {'stale': True, 'age_seconds': None, 'expected_interval_seconds': None, 'stale_after_seconds': 1800 if str(connector).lower()=='linux' else 180}
        cadence = self._cadence_seconds(system_id)
        default_cadence = 900 if str(connector).lower() == 'linux' else 60
        stale_after = max(90, int((cadence or default_cadence) * 3))
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

    @staticmethod
    def _find_kind(items, kind):
        vals = [x for x in items if x.get('metric_kind') == kind]
        return vals[0] if vals else None

    @staticmethod
    def _measurement_value(items, kind):
        item = ITARepository._find_kind(items, kind)
        return float(item['reading']) if item else None

    @staticmethod
    def _capabilities(items):
        kinds = {x.get('metric_kind') for x in items}
        return {
            'thermal': 'temperature' in kinds,
            'power': 'power' in kinds,
            'cooling': 'fan_speed' in kinds,
            'compute': bool(kinds & {'load','cpu_used_pct','process_count'}),
            'memory': bool(kinds & {'memory_used_pct','memory_available_bytes','swap_used_pct'}),
            'storage': bool(kinds & {'storage_used_pct','storage_available_bytes'}),
            'network': bool(kinds & {'network_rx_bytes','network_tx_bytes'}),
            'availability': bool(kinds & {'uptime_seconds'}),
        }

    @staticmethod
    def _primary_cards(capabilities, values, thermal_headroom):
        cards = []
        if capabilities.get('thermal'):
            if values.get('intake_c') is not None: cards.append({'key':'intake','value':values['intake_c'],'format':'temperature'})
            if values.get('cpu_c') is not None: cards.append({'key':'hottest_cpu','value':values['cpu_c'],'format':'temperature'})
            if thermal_headroom: cards.append({'key':'thermal_headroom','value':thermal_headroom.get('headroom'),'format':'temperature_delta','note_key':thermal_headroom.get('label')})
            if values.get('power_w') is not None: cards.append({'key':'power','value':values['power_w'],'format':'power'})
            if len(cards) < 4 and values.get('fan_avg_pct') is not None: cards.append({'key':'fan_avg','value':values['fan_avg_pct'],'format':'percent'})
        else:
            priorities = [
                ('memory_used','memory_used_pct','percent'),('swap_used','swap_used_pct','percent'),
                ('storage_used','storage_used_pct','percent'),('cpu_usage','cpu_used_pct','percent'),
                ('load_1m','load_1m','number'),('uptime','uptime_seconds','duration'),
                ('processes','process_count','integer')]
            for label, key, fmt in priorities:
                if values.get(key) is not None:
                    cards.append({'key':label,'value':values[key],'format':fmt})
                if len(cards) >= 4: break
        return cards[:4]

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
        state = max((x['severity'] for x in items), key=lambda v: rank.get(v, 0), default='normal')
        if any(str(x['state']).lower() not in {'enabled', 'unknown'} for x in items):
            state = 'attention' if state == 'normal' else state
        freshness = self._telemetry_freshness(system_id, snap['occurred_at'], snap.get('connector'))
        if freshness['stale']:
            state = 'stale'

        def delta(a, b):
            return round(a - b, 2) if a is not None and b is not None else None
        def value(kind):
            x = self._find_kind(items, kind)
            return float(x['reading']) if x else None
        def find_load(token):
            candidates=[x for x in items if x.get('metric_kind')=='load' and token in (str(x.get('sensor_id',''))+' '+str(x.get('sensor_name',''))).lower()]
            return float(candidates[0]['reading']) if candidates else None

        fan_spread = round(max(fans) - min(fans), 1) if len(fans) >= 2 else None
        capabilities = self._capabilities(items)
        thermal_headroom = self._next_upper_threshold(hottest_cpu)
        values = {
            'ambient_c': ambient, 'intake_c': intake, 'cpu_c': cpu, 'exhaust_c': exhaust,
            'power_w': power, 'power_utilization_pct': power_util,
            'fan_avg_pct': round(sum(fans) / len(fans), 1) if fans else None,
            'fan_spread_pct': fan_spread, 'fan_min_pct': min(fans) if fans else None, 'fan_max_pct': max(fans) if fans else None,
            'memory_used_pct': value('memory_used_pct'), 'memory_available_bytes': value('memory_available_bytes'),
            'swap_used_pct': value('swap_used_pct'), 'storage_used_pct': value('storage_used_pct'),
            'storage_available_bytes': value('storage_available_bytes'), 'cpu_used_pct': value('cpu_used_pct'),
            'uptime_seconds': value('uptime_seconds'), 'process_count': value('process_count'),
            'network_rx_bytes': value('network_rx_bytes'), 'network_tx_bytes': value('network_tx_bytes'),
            'load_1m': find_load('1m') or find_load('load1'), 'load_5m': find_load('5m') or find_load('load5'),
            'load_15m': find_load('15m') or find_load('load15'),
        }
        values['primary_cards'] = self._primary_cards(capabilities, values, thermal_headroom)

        return {
            'system': {'system_id': snap['system_id'], 'system_name': snap['system_name'], 'connection_id': snap['connection_id'], 'connection_name': snap['connection_name'], 'connector': snap['connector'], 'last_seen': snap['occurred_at'], **self.asset_status(system_id)},
            'state': state, 'freshness': freshness, 'capabilities': capabilities,
            **values,
            'thermal_headroom': thermal_headroom,
            'deltas': {'ambient_to_intake_c': delta(intake, ambient),'intake_to_cpu_c': delta(cpu, intake),'intake_to_exhaust_c': delta(exhaust, intake)},
            'trends': {'cpu': self._trend(system_id, 'CPU'),'intake': self._trend(system_id, 'Intake'),'exhaust': self._trend(system_id, 'Exhaust'),'ambient': self._trend(system_id, 'Room')},
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
