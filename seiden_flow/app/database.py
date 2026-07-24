from __future__ import annotations
import json, sqlite3, threading
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Any,Iterator
from version import DATABASE_SCHEMA_VERSION
from experience import calculate_stats, compare_periods

class FlowDatabase:
    def __init__(self,path:str,organization_id="default_organization",organization_name="Organização padrão",site_id="default_site",site_name="Site padrão"):
        self.path=path;self.organization_id=organization_id;self.site_id=site_id;self._lock=threading.RLock();Path(path).parent.mkdir(parents=True,exist_ok=True)
        self._init_schema(organization_name,site_name);self._migrate_legacy();self._reconcile_vision_sources()
    @contextmanager
    def connect(self)->Iterator[sqlite3.Connection]:
        c=sqlite3.connect(self.path,timeout=30);c.row_factory=sqlite3.Row;c.execute("PRAGMA foreign_keys=ON")
        try: yield c;c.commit()
        finally:c.close()
    def _init_schema(self,org_name,site_name):
        with self.connect() as c:
            c.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL UNIQUE,schema_version TEXT NOT NULL,event_type TEXT NOT NULL,source TEXT NOT NULL,source_event_id TEXT,occurred_at TEXT NOT NULL,received_at TEXT NOT NULL,reader_id TEXT,reader_name TEXT,location_id TEXT,person_id TEXT,person_name TEXT,action TEXT,payload_json TEXT NOT NULL,organization_id TEXT,site_id TEXT,source_id TEXT,domain_person_id TEXT);
            CREATE INDEX IF NOT EXISTS idx_events_occurred ON events(occurred_at DESC);CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);CREATE INDEX IF NOT EXISTS idx_events_person ON events(person_id,occurred_at DESC);CREATE INDEX IF NOT EXISTS idx_events_reader ON events(reader_id,occurred_at DESC);
            CREATE TABLE IF NOT EXISTS persons_state(person_key TEXT PRIMARY KEY,person_id TEXT,person_name TEXT NOT NULL,presence_status TEXT NOT NULL,current_location_id TEXT,current_reader_id TEXT,entered_at TEXT,last_event_id TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sources_state(source_key TEXT PRIMARY KEY,source_type TEXT NOT NULL,source_id TEXT NOT NULL,source_name TEXT,status TEXT NOT NULL,last_event_id TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS organizations(id TEXT PRIMARY KEY,name TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sites(id TEXT PRIMARY KEY,organization_id TEXT NOT NULL,name TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(organization_id) REFERENCES organizations(id));
            CREATE TABLE IF NOT EXISTS locations(id TEXT PRIMARY KEY,site_id TEXT NOT NULL,parent_location_id TEXT,name TEXT NOT NULL,location_type TEXT NOT NULL DEFAULT 'area',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(site_id) REFERENCES sites(id));
            CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,site_id TEXT NOT NULL,location_id TEXT,source_type TEXT NOT NULL,provider TEXT NOT NULL,driver TEXT,name TEXT,status TEXT NOT NULL DEFAULT 'unknown',last_event_id TEXT,last_seen_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(site_id) REFERENCES sites(id));
            CREATE TABLE IF NOT EXISTS persons(id TEXT PRIMARY KEY,organization_id TEXT NOT NULL,external_id TEXT,display_name TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(organization_id) REFERENCES organizations(id));
            CREATE UNIQUE INDEX IF NOT EXISTS idx_person_external ON persons(organization_id,external_id) WHERE external_id IS NOT NULL;
            CREATE TABLE IF NOT EXISTS presences(person_id TEXT NOT NULL,site_id TEXT NOT NULL,presence_status TEXT NOT NULL,current_location_id TEXT,entered_at TEXT,last_event_id TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(person_id,site_id),FOREIGN KEY(person_id) REFERENCES persons(id),FOREIGN KEY(site_id) REFERENCES sites(id));
            CREATE TABLE IF NOT EXISTS observations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observation_id TEXT NOT NULL UNIQUE,
                metric_type TEXT NOT NULL,
                provider TEXT NOT NULL,
                organization_id TEXT NOT NULL,
                site_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_name TEXT,
                location_id TEXT,
                occurred_at TEXT NOT NULL,
                value TEXT NOT NULL,
                raw_value TEXT,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_observations_metric_time ON observations(metric_type,occurred_at);
            CREATE INDEX IF NOT EXISTS idx_observations_source_time ON observations(source_id,occurred_at);
            CREATE TABLE IF NOT EXISTS observation_aggregates(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aggregate_key TEXT NOT NULL UNIQUE,
                metric_type TEXT NOT NULL,
                organization_id TEXT NOT NULL,
                site_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_name TEXT,
                location_id TEXT,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                window_minutes INTEGER NOT NULL,
                sample_count INTEGER NOT NULL,
                positive_count INTEGER NOT NULL DEFAULT 0,
                neutral_count INTEGER NOT NULL DEFAULT 0,
                negative_count INTEGER NOT NULL DEFAULT 0,
                uncertain_count INTEGER NOT NULL DEFAULT 0,
                average_confidence REAL NOT NULL,
                dominant_value TEXT,
                experience_index REAL,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_aggregates_metric_period ON observation_aggregates(metric_type,period_start DESC);
            CREATE INDEX IF NOT EXISTS idx_aggregates_source_period ON observation_aggregates(source_id,period_start DESC);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            """)
            cols={r['name'] for r in c.execute("PRAGMA table_info(events)")}
            for col in ('organization_id','site_id','source_id','domain_person_id'):
                if col not in cols:c.execute(f"ALTER TABLE events ADD COLUMN {col} TEXT")
            now=datetime.now(timezone.utc).isoformat()
            c.execute("INSERT INTO organizations(id,name,created_at,updated_at) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,updated_at=excluded.updated_at",(self.organization_id,org_name,now,now))
            c.execute("INSERT INTO sites(id,organization_id,name,created_at,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET organization_id=excluded.organization_id,name=excluded.name,updated_at=excluded.updated_at",(self.site_id,self.organization_id,site_name,now,now))
            c.execute("INSERT INTO meta(key,value) VALUES('database_schema_version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(DATABASE_SCHEMA_VERSION),))
    @staticmethod
    def _slug(v):
        import re,unicodedata
        s=unicodedata.normalize('NFKD',str(v or '')).encode('ascii','ignore').decode().lower();return re.sub(r'[^a-z0-9]+','_',s).strip('_') or 'unknown'
    def _migrate_legacy(self):
        with self._lock,self.connect() as c:
            rows=c.execute("SELECT * FROM events ORDER BY occurred_at").fetchall()
            for r in rows:
                payload=json.loads(r['payload_json']);flat={'reader_id':r['reader_id'],'reader_name':r['reader_name'],'location_id':r['location_id'],'person_id':r['person_id'],'person_name':r['person_name'],'action':r['action']}
                ids=self._upsert_domain(c,payload,flat,r['event_id'],r['occurred_at'])
                c.execute("UPDATE events SET organization_id=?,site_id=?,source_id=?,domain_person_id=? WHERE id=?",(self.organization_id,self.site_id,ids[0],ids[1],r['id']))
            # reconstruct current presence from legacy state
            for p in c.execute("SELECT * FROM persons_state").fetchall():
                pid=self._person_id(p['person_id'],p['person_name']);self._ensure_person(c,pid,p['person_id'],p['person_name'],p['updated_at'])
                c.execute("INSERT INTO presences(person_id,site_id,presence_status,current_location_id,entered_at,last_event_id,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(person_id,site_id) DO UPDATE SET presence_status=excluded.presence_status,current_location_id=excluded.current_location_id,entered_at=excluded.entered_at,last_event_id=excluded.last_event_id,updated_at=excluded.updated_at",(pid,self.site_id,p['presence_status'],p['current_location_id'],p['entered_at'],p['last_event_id'],p['updated_at']))

    def _reconcile_vision_sources(self):
        """Unifica fontes antigas do Vision com o leitor operacional correspondente."""
        with self._lock,self.connect() as c:
            rows=c.execute("SELECT DISTINCT source_id,source_name FROM observations WHERE source_id LIKE 'sensor.%' OR source_id LIKE 'binary_sensor.%' OR source_id LIKE 'event.%'").fetchall()
            for r in rows:
                name=r['source_name'] or r['source_id'];canonical=self._slug(name)
                match=c.execute("SELECT id,location_id,name FROM sources WHERE source_type='reader' AND lower(name)=lower(?) ORDER BY CASE WHEN provider='seiden_bridge' THEN 0 ELSE 1 END LIMIT 1",(name,)).fetchone()
                location=match['location_id'] if match else None
                c.execute("UPDATE observations SET source_id=?,source_name=?,location_id=COALESCE(location_id,?) WHERE source_id=?",(canonical,name,location,r['source_id']))
                c.execute("UPDATE observation_aggregates SET source_id=?,source_name=?,location_id=COALESCE(location_id,?) WHERE source_id=?",(canonical,name,location,r['source_id']))
            # Remove fontes técnicas criadas a partir de entidades sensor.* quando
            # já existe um leitor operacional de mesmo nome.
            technical=c.execute("SELECT id,name,location_id FROM sources WHERE id LIKE 'reader_sensor_%' OR id LIKE 'reader_binary_sensor_%' OR id LIKE 'reader_event_%'").fetchall()
            for r in technical:
                exists=c.execute("SELECT 1 FROM sources WHERE id<>? AND source_type='reader' AND lower(name)=lower(?) LIMIT 1",(r['id'],r['name'])).fetchone()
                if exists:
                    c.execute("DELETE FROM sources WHERE id=?",(r['id'],))
                    if r['location_id']:
                        used=c.execute("SELECT 1 FROM sources WHERE location_id=? UNION SELECT 1 FROM presences WHERE current_location_id=? LIMIT 1",(r['location_id'],r['location_id'])).fetchone()
                        if not used:c.execute("DELETE FROM locations WHERE id=?",(r['location_id'],))

    def _person_id(self,external,name): return f"person_{self._slug(external or name)}"
    def _ensure_person(self,c,pid,external,name,ts):
        c.execute("INSERT INTO persons(id,organization_id,external_id,display_name,created_at,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET external_id=COALESCE(excluded.external_id,persons.external_id),display_name=excluded.display_name,updated_at=excluded.updated_at",(pid,self.organization_id,str(external) if external else None,name or pid,ts,ts))
    def _upsert_domain(self,c,event,flat,event_id,ts):
        rid=flat.get('reader_id');rname=flat.get('reader_name');loc=flat.get('location_id')
        if not loc and rid:loc=f"location_{self._slug(rid)}"
        if loc:c.execute("INSERT INTO locations(id,site_id,name,location_type,created_at,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,updated_at=excluded.updated_at",(str(loc),self.site_id,rname or str(loc),'access_point',ts,ts))
        source_id=None
        if rid:
            source_id=f"reader_{self._slug(rid)}";driver=(event.get('reader') or {}).get('driver')
            c.execute("INSERT INTO sources(id,site_id,location_id,source_type,provider,driver,name,status,last_event_id,last_seen_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET location_id=COALESCE(excluded.location_id,sources.location_id),driver=COALESCE(excluded.driver,sources.driver),name=COALESCE(excluded.name,sources.name),last_event_id=excluded.last_event_id,last_seen_at=excluded.last_seen_at,updated_at=excluded.updated_at",(source_id,self.site_id,loc,'reader',event.get('source','external'),driver,rname or rid,'unknown',event_id,ts,ts,ts))
        person_domain=None
        if flat.get('person_name'):
            person_domain=self._person_id(flat.get('person_id'),flat.get('person_name'));self._ensure_person(c,person_domain,flat.get('person_id'),flat.get('person_name'),ts)
        return source_id,person_domain
    def insert_event(self,event):
        f=event.get('_flat',{})
        with self._lock,self.connect() as c:
            try:
                source_id,pid=self._upsert_domain(c,event,f,event['event_id'],event['timestamp'])
                c.execute("INSERT INTO events(event_id,schema_version,event_type,source,source_event_id,occurred_at,received_at,reader_id,reader_name,location_id,person_id,person_name,action,payload_json,organization_id,site_id,source_id,domain_person_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(event['event_id'],event['schema_version'],event['event_type'],event['source'],event.get('correlation',{}).get('source_event_id'),event['timestamp'],event['received_at'],f.get('reader_id'),f.get('reader_name'),f.get('location_id'),f.get('person_id'),f.get('person_name'),f.get('action'),json.dumps({k:v for k,v in event.items() if k!='_flat'},ensure_ascii=False),self.organization_id,self.site_id,source_id,pid));return True
            except sqlite3.IntegrityError:return False
    def apply_state(self,event):
        f=event.get('_flat',{});now=event['received_at'];action=f.get('action');name=f.get('person_name')
        with self._lock,self.connect() as c:
            if name and action in {'entered','entry','in','exited','exit','out'}:
                inside=action in {'entered','entry','in'};key=f.get('person_id') or name.strip().lower();pid=self._person_id(f.get('person_id'),name);self._ensure_person(c,pid,f.get('person_id'),name,now)
                c.execute("INSERT INTO persons_state(person_key,person_id,person_name,presence_status,current_location_id,current_reader_id,entered_at,last_event_id,updated_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(person_key) DO UPDATE SET person_id=excluded.person_id,person_name=excluded.person_name,presence_status=excluded.presence_status,current_location_id=excluded.current_location_id,current_reader_id=excluded.current_reader_id,entered_at=excluded.entered_at,last_event_id=excluded.last_event_id,updated_at=excluded.updated_at",(key,f.get('person_id'),name,'inside' if inside else 'outside',f.get('location_id'),f.get('reader_id'),event['timestamp'] if inside else None,event['event_id'],now))
                c.execute("INSERT INTO presences(person_id,site_id,presence_status,current_location_id,entered_at,last_event_id,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(person_id,site_id) DO UPDATE SET presence_status=excluded.presence_status,current_location_id=excluded.current_location_id,entered_at=excluded.entered_at,last_event_id=excluded.last_event_id,updated_at=excluded.updated_at",(pid,self.site_id,'inside' if inside else 'outside',f.get('location_id'),event['timestamp'] if inside else None,event['event_id'],now))
            et=event['event_type']
            if et in {'reader.online','reader.offline'} or et.endswith('reader_online') or et.endswith('reader_offline'):
                rid=f.get('reader_id') or f.get('reader_name') or 'unknown';status='online' if 'online' in et and 'offline' not in et else 'offline';sid=f"reader_{self._slug(rid)}"
                c.execute("INSERT INTO sources_state(source_key,source_type,source_id,source_name,status,last_event_id,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(source_key) DO UPDATE SET source_id=excluded.source_id,source_name=excluded.source_name,status=excluded.status,last_event_id=excluded.last_event_id,updated_at=excluded.updated_at",(f"reader:{self._slug(rid)}",'reader',rid,f.get('reader_name'),status,event['event_id'],now))
                updated=c.execute("UPDATE sources SET status=?,last_event_id=?,last_seen_at=?,updated_at=? WHERE id=?",(status,event['event_id'],event['timestamp'],now,sid)).rowcount
                if not updated and f.get('reader_name'):
                    c.execute("UPDATE sources SET status=?,last_event_id=?,last_seen_at=?,updated_at=? WHERE source_type='reader' AND lower(name)=lower(?)",(status,event['event_id'],event['timestamp'],now,f.get('reader_name')))
    def _rows(self,sql,p=()):
        with self.connect() as c:return [dict(r) for r in c.execute(sql,p).fetchall()]
    def list_events(self,limit=100,event_type=None,person=None):
        cl=[];p=[]
        if event_type:cl.append('event_type=?');p.append(event_type)
        if person:cl.append('(person_name LIKE ? OR person_id=?)');p += [f'%{person}%',person]
        w=' WHERE '+' AND '.join(cl) if cl else ''
        with self.connect() as c:rows=c.execute(f"SELECT payload_json FROM events{w} ORDER BY occurred_at DESC LIMIT ?",(*p,min(limit,5000))).fetchall()
        return [json.loads(r['payload_json']) for r in rows]
    def people_inside(self):return self._rows("SELECT * FROM persons_state WHERE presence_status='inside' ORDER BY entered_at")
    def people_state(self):return self._rows("SELECT * FROM persons_state ORDER BY updated_at DESC")
    def sources_state(self):return self._rows("SELECT * FROM sources_state ORDER BY source_type,source_name,source_id")
    def organizations(self):return self._rows("SELECT * FROM organizations ORDER BY name")
    def sites(self):return self._rows("SELECT * FROM sites ORDER BY name")
    def locations(self):return self._rows("SELECT * FROM locations ORDER BY name")
    def sources(self):return self._rows("SELECT * FROM sources ORDER BY source_type,name,id")
    def persons(self):return self._rows("SELECT * FROM persons ORDER BY display_name")
    def presences(self):return self._rows("SELECT p.*,x.display_name FROM presences p JOIN persons x ON x.id=p.person_id ORDER BY x.display_name")
    def summary(self):
        with self.connect() as c:
            q=lambda s:c.execute(s).fetchone()['c'];last=c.execute("SELECT occurred_at,event_type,person_name,reader_name FROM events ORDER BY occurred_at DESC LIMIT 1").fetchone()
            return {'events_total':q('SELECT COUNT(*) c FROM events'),'events_today':q("SELECT COUNT(*) c FROM events WHERE occurred_at >= date('now')"),'people_inside':q("SELECT COUNT(*) c FROM presences WHERE presence_status='inside'"),'sources_offline':q("SELECT COUNT(*) c FROM sources WHERE status='offline'"),'organizations':q('SELECT COUNT(*) c FROM organizations'),'sites':q('SELECT COUNT(*) c FROM sites'),'locations':q('SELECT COUNT(*) c FROM locations'),'sources':q('SELECT COUNT(*) c FROM sources'),'persons':q('SELECT COUNT(*) c FROM persons'),'last_event':dict(last) if last else None}

    def insert_observation(self, observation):
        with self._lock,self.connect() as c:
            try:
                location_id=observation.get('location_id')
                if not location_id and observation.get('source_name'):
                    match=c.execute("SELECT location_id FROM sources WHERE source_type='reader' AND lower(name)=lower(?) ORDER BY CASE WHEN provider='seiden_bridge' THEN 0 ELSE 1 END LIMIT 1",(observation.get('source_name'),)).fetchone()
                    if match:location_id=match['location_id']
                observation['location_id']=location_id
                c.execute("""INSERT INTO observations(observation_id,metric_type,provider,organization_id,site_id,source_id,source_name,location_id,occurred_at,value,raw_value,confidence,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                          (observation['observation_id'],observation['metric_type'],observation.get('provider','external'),self.organization_id,self.site_id,observation['source_id'],observation.get('source_name'),location_id,observation['occurred_at'],observation['value'],observation.get('raw_value'),float(observation.get('confidence',0)),datetime.now(timezone.utc).isoformat()))
                return True
            except sqlite3.IntegrityError:
                return False

    @staticmethod
    def _parse_dt(value):
        text=str(value).replace('Z','+00:00')
        dt=datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    def aggregate_observation_window(self, observation, window_minutes, minimum_samples, weights):
        occurred=self._parse_dt(observation['occurred_at']).astimezone(timezone.utc)
        minute=(occurred.minute // window_minutes) * window_minutes
        start=occurred.replace(minute=minute,second=0,microsecond=0)
        end=start+timedelta(minutes=window_minutes)
        start_iso=start.isoformat(); end_iso=end.isoformat(); source_id=observation['source_id']
        with self._lock,self.connect() as c:
            rows=c.execute("""SELECT value,confidence,source_name,location_id FROM observations WHERE metric_type='facial_expression' AND source_id=? AND occurred_at>=? AND occurred_at<? ORDER BY occurred_at""",(source_id,start_iso,end_iso)).fetchall()
            count=len(rows)
            key=f"facial_expression:{self.site_id}:{source_id}:{start_iso}:{window_minutes}"
            if count < minimum_samples:
                c.execute("DELETE FROM observation_aggregates WHERE aggregate_key=?",(key,))
                return {'status':'insufficient_data','sample_count':count,'minimum_samples':minimum_samples,'period_start':start_iso,'period_end':end_iso,'source_id':source_id}
            stats=calculate_stats(rows,minimum_samples,weights)
            counts=stats['distribution']
            avg=stats['average_confidence']
            index=stats['experience_index']
            dominant=stats['dominant_expression']
            source_name=rows[-1]['source_name']; location_id=rows[-1]['location_id']; now=datetime.now(timezone.utc).isoformat()
            c.execute("""INSERT INTO observation_aggregates(aggregate_key,metric_type,organization_id,site_id,source_id,source_name,location_id,period_start,period_end,window_minutes,sample_count,positive_count,neutral_count,negative_count,uncertain_count,average_confidence,dominant_value,experience_index,status,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(aggregate_key) DO UPDATE SET source_name=excluded.source_name,location_id=excluded.location_id,sample_count=excluded.sample_count,positive_count=excluded.positive_count,neutral_count=excluded.neutral_count,negative_count=excluded.negative_count,uncertain_count=excluded.uncertain_count,average_confidence=excluded.average_confidence,dominant_value=excluded.dominant_value,experience_index=excluded.experience_index,status=excluded.status,updated_at=excluded.updated_at""",
                      (key,'facial_expression',self.organization_id,self.site_id,source_id,source_name,location_id,start_iso,end_iso,window_minutes,count,counts['positive'],counts['neutral'],counts['negative'],counts['uncertain'],avg,dominant,index,'available',now))
            return {'status':'available','sample_count':count,'minimum_samples':minimum_samples,'period_start':start_iso,'period_end':end_iso,'source_id':source_id,'experience_index':round(index,1),'dominant_value':dominant,'distribution':counts,'average_confidence':round(avg,4)}

    def cleanup_raw_observations(self, days):
        cutoff=(datetime.now(timezone.utc)-timedelta(days=max(1,days))).isoformat()
        with self._lock,self.connect() as c:
            return c.execute('DELETE FROM observations WHERE occurred_at < ?',(cutoff,)).rowcount

    def observation_count(self):
        with self.connect() as c:return c.execute('SELECT COUNT(*) c FROM observations').fetchone()['c']

    @staticmethod
    def _hea_stats(rows, minimum_samples, weights=None):
        return calculate_stats(rows, minimum_samples, weights)

    def _hea_observations(self,start_at,end_at,source_id=None,location_id=None):
        clauses=["o.metric_type='facial_expression'","o.occurred_at>=?","o.occurred_at<=?"]
        params=[start_at,end_at]
        if source_id: clauses.append('o.source_id=?');params.append(source_id)
        if location_id: clauses.append('COALESCE(o.location_id,s.location_id)=?');params.append(location_id)
        sql=("SELECT o.*,COALESCE(o.location_id,s.location_id) resolved_location_id,"
             "COALESCE(l.name,'') location_name,COALESCE(NULLIF(o.source_name,''),s.name,o.source_id) resolved_source_name "
             "FROM observations o LEFT JOIN sources s ON s.id=o.source_id "
             "LEFT JOIN locations l ON l.id=COALESCE(o.location_id,s.location_id) WHERE " + ' AND '.join(clauses) + " ORDER BY o.occurred_at ASC")
        with self.connect() as c:return c.execute(sql,tuple(params)).fetchall()

    def hea_query(self,start_at,end_at,minimum_samples=10,weights=None,source_id=None,location_id=None,max_history_points=96):
        rows=self._hea_observations(start_at,end_at,source_id,location_id)
        summary=self._hea_stats(rows,minimum_samples,weights)
        summary.update({'period_start':start_at,'period_end':end_at,'sources':len({r['source_id'] for r in rows})})

        start=self._parse_dt(start_at).astimezone(timezone.utc)
        end=self._parse_dt(end_at).astimezone(timezone.utc)
        duration=end-start
        previous_start=start-duration
        previous_rows=self._hea_observations(previous_start.isoformat(),start.isoformat(),source_id,location_id)
        previous=self._hea_stats(previous_rows,minimum_samples,weights)
        summary.update(compare_periods(summary,previous))
        summary['previous_period_start']=previous_start.isoformat()
        summary['previous_period_end']=start.isoformat()

        grouped={}
        for r in rows:
            key=r['source_id'];g=grouped.setdefault(key,{'rows':[],'source_id':key,'source_name':r['resolved_source_name'] or key,'location_id':r['resolved_location_id'],'location_name':r['location_name'] or None})
            g['rows'].append(r)
        sources=[]
        for g in grouped.values():
            stats=self._hea_stats(g.pop('rows'),minimum_samples,weights);sources.append({**g,**stats})
        sources.sort(key=lambda x:(x['experience_index'] is not None,x['experience_index'] if x['experience_index'] is not None else -999),reverse=True)

        total_seconds=max(1,(end-start).total_seconds())
        # Keep enough observations per point for meaningful period highlights.
        target_points=max(1,min(max_history_points,max(1,len(rows)//max(1,minimum_samples))))
        bucket_seconds=max(60,int(total_seconds/target_points))
        buckets={}
        for r in rows:
            t=self._parse_dt(r['occurred_at']).astimezone(timezone.utc);idx=max(0,int((t-start).total_seconds()//bucket_seconds));buckets.setdefault(idx,[]).append(r)
        history=[]
        for idx,brows in sorted(buckets.items()):
            bstart=start+timedelta(seconds=idx*bucket_seconds);bend=min(end,bstart+timedelta(seconds=bucket_seconds));stats=self._hea_stats(brows,minimum_samples,weights)
            history.append({'window_start':bstart.isoformat(),'window_end':bend.isoformat(),**stats})
        available_windows=[item for item in history if item.get('experience_index') is not None]
        # A single analytical window cannot establish a meaningful best/worst period or trend.
        # Require at least two valid windows for highlights and three for a trend chart.
        summary['best_period']=max(available_windows,key=lambda item:item['experience_index']) if len(available_windows)>=2 else None
        summary['worst_period']=min(available_windows,key=lambda item:item['experience_index']) if len(available_windows)>=2 else None
        summary['history_points']=len(available_windows)
        summary['trend_chart_available']=len(available_windows)>=3
        if len(available_windows)>=3:
            summary['trend_chart_status']='available'
        elif len(rows)<minimum_samples:
            summary['trend_chart_status']='insufficient_samples'
        elif len(available_windows)<2:
            summary['trend_chart_status']='single_period'
        else:
            summary['trend_chart_status']='insufficient_periods'
        summary['aggregation_seconds']=bucket_seconds

        options_sources=[];options_locations=[]
        with self.connect() as c:
            for r in c.execute("SELECT DISTINCT o.source_id,COALESCE(NULLIF(o.source_name,''),s.name,o.source_id) source_name FROM observations o LEFT JOIN sources s ON s.id=o.source_id WHERE o.metric_type='facial_expression' ORDER BY source_name"):
                options_sources.append({'source_id':r['source_id'],'source_name':r['source_name']})
            for r in c.execute("SELECT DISTINCT COALESCE(o.location_id,s.location_id) location_id,l.name location_name FROM observations o LEFT JOIN sources s ON s.id=o.source_id LEFT JOIN locations l ON l.id=COALESCE(o.location_id,s.location_id) WHERE o.metric_type='facial_expression' AND COALESCE(o.location_id,s.location_id) IS NOT NULL ORDER BY l.name"):
                options_locations.append({'location_id':r['location_id'],'location_name':r['location_name'] or r['location_id']})
        return {'summary':summary,'previous_summary':previous,'sources':sources,'history':history,'filters':{'source_id':source_id,'location_id':location_id,'available_sources':options_sources,'available_locations':options_locations}}

    def hea_history(self, hours=24, source_id=None, limit=500):
        end=datetime.now(timezone.utc);start=end-timedelta(hours=max(1,hours));return self.hea_query(start.isoformat(),end.isoformat(),1,source_id=source_id,max_history_points=min(limit,500))['history']

    def hea_summary(self, hours=24, minimum_samples=10):
        end=datetime.now(timezone.utc);start=end-timedelta(hours=max(1,hours));result=self.hea_query(start.isoformat(),end.isoformat(),minimum_samples)['summary'];result['period_hours']=hours;return result

    def hea_sources(self, hours=24):
        end=datetime.now(timezone.utc);start=end-timedelta(hours=max(1,hours));return self.hea_query(start.isoformat(),end.isoformat(),1)['sources']

    def cleanup(self,days):
        cutoff=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
        with self._lock,self.connect() as c:return c.execute('DELETE FROM events WHERE occurred_at < ?',(cutoff,)).rowcount
