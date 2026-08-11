from __future__ import annotations
import json
from datetime import datetime,timezone,timedelta

class ITARepository:
    def __init__(self,db,timezone_name='America/Sao_Paulo'):
        self.db=db;self.timezone_name=timezone_name;self._init_schema()
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
            ''')
    def ingest(self,snapshot:dict)->int:
        now=datetime.now(timezone.utc).isoformat();eid=snapshot['event_id']
        if not eid:return 0
        with self.db.connect() as c:
            try:
                c.execute('INSERT INTO ita_snapshots(event_id,occurred_at,connection_id,connection_name,connector,system_id,system_name,chassis_ids_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(
                    eid,snapshot['occurred_at'],snapshot['connection_id'],snapshot['connection_name'],snapshot['connector'],snapshot['system_id'],snapshot['system_name'],json.dumps(snapshot.get('chassis_ids',[])),now))
            except Exception as exc:
                if 'UNIQUE constraint failed' in str(exc):return 0
                raise
            for m in snapshot['measurements']:
                c.execute('INSERT OR IGNORE INTO ita_measurements(event_id,occurred_at,system_id,sensor_id,sensor_name,physical_context,metric_kind,reading,units,health,state,range_min,range_max,thresholds_json,related_items_json,odata_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
                    eid,snapshot['occurred_at'],snapshot['system_id'],m['sensor_id'],m['sensor_name'],m['physical_context'],m['metric_kind'],m['reading'],m['units'],m['health'],m['state'],m.get('range_min'),m.get('range_max'),json.dumps(m.get('thresholds',{})),json.dumps(m.get('related_items',[])),m.get('odata_id')))
        return len(snapshot['measurements'])
    @staticmethod
    def _row(r):return dict(r) if r else None
    @staticmethod
    def _threshold_value(thresholds,name):
        x=thresholds.get(name) if isinstance(thresholds,dict) else None
        try:return float(x.get('reading')) if isinstance(x,dict) and x.get('reading') is not None else None
        except (TypeError,ValueError):return None
    @staticmethod
    def _severity(health,reading,thresholds):
        h=str(health or '').lower()
        if h in {'critical','fatal'}:return 'critical'
        fatal=ITARepository._threshold_value(thresholds,'UpperFatal');critical=ITARepository._threshold_value(thresholds,'UpperCritical');caution=ITARepository._threshold_value(thresholds,'UpperCaution')
        lower_critical=ITARepository._threshold_value(thresholds,'LowerCritical');lower_caution=ITARepository._threshold_value(thresholds,'LowerCaution')
        if fatal is not None and reading>=fatal:return 'critical'
        if critical is not None and reading>=critical:return 'critical'
        if lower_critical is not None and reading<=lower_critical:return 'critical'
        if h in {'warning','caution'}:return 'attention'
        if caution is not None and reading>=caution:return 'attention'
        if lower_caution is not None and reading<=lower_caution:return 'attention'
        return 'normal'
    def systems(self):
        with self.db.connect() as c:
            rows=c.execute('''SELECT s.system_id,s.system_name,s.connection_id,s.connection_name,s.connector,s.occurred_at
              FROM ita_snapshots s JOIN (SELECT system_id,MAX(occurred_at) mx FROM ita_snapshots GROUP BY system_id) x
              ON s.system_id=x.system_id AND s.occurred_at=x.mx ORDER BY s.system_name''').fetchall()
        return [dict(r) for r in rows]
    def _latest_measurements(self,system_id):
        with self.db.connect() as c:
            snap=c.execute('SELECT * FROM ita_snapshots WHERE system_id=? ORDER BY occurred_at DESC LIMIT 1',(system_id,)).fetchone()
            if not snap:return None,[]
            rows=c.execute('SELECT * FROM ita_measurements WHERE event_id=? ORDER BY physical_context,sensor_name',(snap['event_id'],)).fetchall()
        items=[]
        for r in rows:
            d=dict(r);d['thresholds']=json.loads(d.pop('thresholds_json') or '{}');d['related_items']=json.loads(d.pop('related_items_json') or '[]');d['severity']=self._severity(d['health'],d['reading'],d['thresholds']);items.append(d)
        return dict(snap),items
    @staticmethod
    def _temp_by_context(items,context):
        vals=[x for x in items if x['metric_kind']=='temperature' and str(x['physical_context']).lower()==context.lower()]
        return sum(x['reading'] for x in vals)/len(vals) if vals else None
    def current(self,system_id):
        snap,items=self._latest_measurements(system_id)
        if not snap:return None
        intake=self._temp_by_context(items,'Intake');exhaust=self._temp_by_context(items,'Exhaust');ambient=self._temp_by_context(items,'Room')
        cpu_vals=[x['reading'] for x in items if x['metric_kind']=='temperature' and str(x['physical_context']).lower()=='cpu']
        cpu=max(cpu_vals) if cpu_vals else None
        power_items=[x for x in items if x['metric_kind']=='power']
        preferred_power=[x for x in power_items if str(x['physical_context']).lower()=='chassis' or 'total' in str(x['sensor_name']).lower() or 'total' in str(x['sensor_id']).lower()]
        power=(preferred_power[0]['reading'] if preferred_power else (sum(x['reading'] for x in power_items) if power_items else None))
        fans=[x['reading'] for x in items if x['metric_kind']=='fan_speed']
        rank={'normal':0,'attention':1,'critical':2};state=max((x['severity'] for x in items),key=lambda v:rank[v],default='normal')
        if any(str(x['state']).lower() not in {'enabled','unknown'} for x in items):state='attention' if state=='normal' else state
        def delta(a,b):return round(a-b,2) if a is not None and b is not None else None
        return {'system':{'system_id':snap['system_id'],'system_name':snap['system_name'],'connection_id':snap['connection_id'],'connection_name':snap['connection_name'],'connector':snap['connector'],'last_seen':snap['occurred_at']},
          'state':state,'ambient_c':ambient,'intake_c':intake,'cpu_c':cpu,'exhaust_c':exhaust,'power_w':power,'fan_avg_pct':round(sum(fans)/len(fans),1) if fans else None,
          'deltas':{'ambient_to_intake_c':delta(intake,ambient),'intake_to_cpu_c':delta(cpu,intake),'intake_to_exhaust_c':delta(exhaust,intake)},'measurements':items}
    def portfolio(self):
        out=[]
        for s in self.systems():
            cur=self.current(s['system_id'])
            if cur:out.append(cur)
        counts={'normal':0,'attention':0,'critical':0}
        for x in out:counts[x['state']]=counts.get(x['state'],0)+1
        return {'items':out,'counts':counts,'total':len(out),'updated_at':datetime.now(timezone.utc).isoformat()}
    def history(self,system_id,hours=24):
        hours=max(1,min(int(hours),8760));start=(datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat()
        with self.db.connect() as c:
            rows=c.execute('SELECT occurred_at,sensor_id,sensor_name,physical_context,metric_kind,reading,units FROM ita_measurements WHERE system_id=? AND occurred_at>=? ORDER BY occurred_at',(system_id,start)).fetchall()
        return {'system_id':system_id,'hours':hours,'items':[dict(r) for r in rows]}
