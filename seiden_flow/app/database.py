from __future__ import annotations
import json, sqlite3, threading
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Any,Iterator
from version import DATABASE_SCHEMA_VERSION

class FlowDatabase:
    def __init__(self,path:str,organization_id="default_organization",organization_name="Organização padrão",site_id="default_site",site_name="Site padrão"):
        self.path=path;self.organization_id=organization_id;self.site_id=site_id;self._lock=threading.RLock();Path(path).parent.mkdir(parents=True,exist_ok=True)
        self._init_schema(organization_name,site_name);self._migrate_legacy()
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
                c.execute("""INSERT INTO observations(observation_id,metric_type,provider,organization_id,site_id,source_id,source_name,location_id,occurred_at,value,raw_value,confidence,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                          (observation['observation_id'],observation['metric_type'],observation.get('provider','external'),self.organization_id,self.site_id,observation['source_id'],observation.get('source_name'),observation.get('location_id'),observation['occurred_at'],observation['value'],observation.get('raw_value'),float(observation.get('confidence',0)),datetime.now(timezone.utc).isoformat()))
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
            counts={'positive':0,'neutral':0,'negative':0,'uncertain':0}
            for r in rows: counts[r['value'] if r['value'] in counts else 'uncertain'] += 1
            avg=sum(float(r['confidence']) for r in rows)/count
            scored=counts['positive']*weights['positive']+counts['neutral']*weights['neutral']+counts['negative']*weights['negative']
            denominator=max(1,counts['positive']+counts['neutral']+counts['negative'])
            index=max(-100.0,min(100.0,100.0*scored/denominator))
            dominant=max(('positive','neutral','negative'),key=lambda k:counts[k])
            source_name=rows[-1]['source_name']; location_id=rows[-1]['location_id']; now=datetime.now(timezone.utc).isoformat()
            c.execute("""INSERT INTO observation_aggregates(aggregate_key,metric_type,organization_id,site_id,source_id,source_name,location_id,period_start,period_end,window_minutes,sample_count,positive_count,neutral_count,negative_count,uncertain_count,average_confidence,dominant_value,experience_index,status,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(aggregate_key) DO UPDATE SET source_name=excluded.source_name,location_id=excluded.location_id,sample_count=excluded.sample_count,positive_count=excluded.positive_count,neutral_count=excluded.neutral_count,negative_count=excluded.negative_count,uncertain_count=excluded.uncertain_count,average_confidence=excluded.average_confidence,dominant_value=excluded.dominant_value,experience_index=excluded.experience_index,status=excluded.status,updated_at=excluded.updated_at""",
                      (key,'facial_expression',self.organization_id,self.site_id,source_id,source_name,location_id,start_iso,end_iso,window_minutes,count,counts['positive'],counts['neutral'],counts['negative'],counts['uncertain'],avg,dominant,index,'available',now))
            return {'status':'available','sample_count':count,'minimum_samples':minimum_samples,'period_start':start_iso,'period_end':end_iso,'source_id':source_id,'experience_index':round(index,1),'dominant_value':dominant,'distribution':counts,'average_confidence':round(avg,4)}

    def cleanup_raw_observations(self, minutes):
        cutoff=(datetime.now(timezone.utc)-timedelta(minutes=minutes)).isoformat()
        with self._lock,self.connect() as c:
            return c.execute('DELETE FROM observations WHERE occurred_at < ?',(cutoff,)).rowcount

    def observation_count(self):
        with self.connect() as c:return c.execute('SELECT COUNT(*) c FROM observations').fetchone()['c']

    def hea_history(self, hours=24, source_id=None, limit=500):
        cutoff=(datetime.now(timezone.utc)-timedelta(hours=max(1,hours))).isoformat(); clauses=["metric_type='facial_expression'","period_start>=?","status='available'"]; params=[cutoff]
        if source_id: clauses.append('source_id=?');params.append(source_id)
        params.append(min(limit,5000))
        return self._rows(f"SELECT * FROM observation_aggregates WHERE {' AND '.join(clauses)} ORDER BY period_start DESC LIMIT ?",tuple(params))

    def hea_summary(self, hours=24, minimum_samples=10):
        rows=self.hea_history(hours=hours,limit=5000)
        if not rows:
            return {'status':'insufficient_data','minimum_samples':minimum_samples,'sample_count':0,'experience_index':None,'dominant_expression':None,'distribution':{'positive':0,'neutral':0,'negative':0,'uncertain':0},'average_confidence':None,'sources':0,'period_hours':hours}
        dist={'positive':sum(r['positive_count'] for r in rows),'neutral':sum(r['neutral_count'] for r in rows),'negative':sum(r['negative_count'] for r in rows),'uncertain':sum(r['uncertain_count'] for r in rows)}
        n=sum(r['sample_count'] for r in rows); weighted=sum(float(r['experience_index'])*r['sample_count'] for r in rows)/max(1,n); conf=sum(float(r['average_confidence'])*r['sample_count'] for r in rows)/max(1,n)
        dominant=max(('positive','neutral','negative'),key=lambda k:dist[k])
        return {'status':'available','minimum_samples':minimum_samples,'sample_count':n,'experience_index':round(weighted,1),'dominant_expression':dominant,'distribution':dist,'average_confidence':round(conf,4),'sources':len({r['source_id'] for r in rows}),'period_hours':hours}

    def hea_sources(self, hours=24):
        rows=self.hea_history(hours=hours,limit=5000); grouped={}
        for r in rows:
            g=grouped.setdefault(r['source_id'],{'source_id':r['source_id'],'source_name':r['source_name'] or r['source_id'],'location_id':r['location_id'],'sample_count':0,'weighted_index':0.0,'confidence':0.0,'positive':0,'neutral':0,'negative':0,'uncertain':0})
            n=r['sample_count'];g['sample_count']+=n;g['weighted_index']+=float(r['experience_index'])*n;g['confidence']+=float(r['average_confidence'])*n
            for k in ('positive','neutral','negative','uncertain'):g[k]+=r[f'{k}_count']
        result=[]
        for g in grouped.values():
            n=max(1,g['sample_count']);g['experience_index']=round(g.pop('weighted_index')/n,1);g['average_confidence']=round(g.pop('confidence')/n,4);g['dominant_expression']=max(('positive','neutral','negative'),key=lambda k:g[k]);result.append(g)
        return sorted(result,key=lambda x:x['experience_index'],reverse=True)

    def cleanup(self,days):
        cutoff=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
        with self._lock,self.connect() as c:return c.execute('DELETE FROM events WHERE occurred_at < ?',(cutoff,)).rowcount
