from __future__ import annotations
import json, sqlite3
from datetime import datetime, timedelta, timezone

class LCARepository:
    def __init__(self,db):self.db=db;self.ensure_schema()
    def ensure_schema(self):
        with self.db.connect() as c:
            c.executescript("""
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
            """)
    def ingest(self,items):
        count=0
        with self.db.connect() as c:
            for item in items:
                now=datetime.now(timezone.utc).isoformat(); did=item['device_id']; ch=item.get('channel')
                c.execute("""INSERT INTO lca_devices(device_id,site_id,name,topic,model,manufacturer,first_seen,last_seen,sample_payload_json,updated_at)
                  VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(device_id) DO UPDATE SET name=COALESCE(NULLIF(excluded.name,''),lca_devices.name),topic=COALESCE(excluded.topic,lca_devices.topic),model=COALESCE(excluded.model,lca_devices.model),manufacturer=COALESCE(excluded.manufacturer,lca_devices.manufacturer),last_seen=excluded.last_seen,sample_payload_json=excluded.sample_payload_json,updated_at=excluded.updated_at""",
                  (did,self.db.site_id,item['device_name'],item.get('topic'),item.get('model'),item.get('manufacturer'),item['occurred_at'],item['occurred_at'],json.dumps(item['payload'],ensure_ascii=False),now))
                if ch:
                    cid=f"{did}:{ch}"
                    c.execute("""INSERT INTO lca_channels(channel_id,device_id,channel_key,created_at,updated_at) VALUES(?,?,?,?,?)
                      ON CONFLICT(device_id,channel_key) DO UPDATE SET updated_at=excluded.updated_at""",(cid,did,ch,now,now))
                cfg=c.execute("SELECT * FROM lca_channels WHERE device_id=? AND channel_key=?",(did,ch)).fetchone() if ch else None
                try:
                    c.execute("""INSERT INTO lca_events(lca_event_id,device_id,channel_key,kind,state,action,brightness,occurred_at,origin_location_id,origin_location_name,adjacent_location_id,adjacent_location_name,direction_hint,related_light_id,related_light_name,virtual_parallel_group,payload_json,created_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(item['lca_event_id'],did,ch,item['kind'],item.get('state'),item.get('action'),item.get('brightness'),item['occurred_at'],cfg['location_id'] if cfg else None,cfg['location_name'] if cfg else None,cfg['adjacent_location_id'] if cfg else None,cfg['adjacent_location_name'] if cfg else None,cfg['direction_hint'] if cfg else None,cfg['related_light_id'] if cfg else None,cfg['related_light_name'] if cfg else None,cfg['virtual_parallel_group'] if cfg else None,json.dumps(item['payload'],ensure_ascii=False),now));count+=1
                except sqlite3.IntegrityError:continue
                if item['kind']=='availability':c.execute("UPDATE lca_devices SET availability=?,updated_at=? WHERE device_id=?",(item['state'],now,did))
                if item['kind']=='state':self._update_session(c,item,cfg,now)
        return count
    def _update_session(self,c,item,cfg,now):
        did=item['device_id'];ch=item.get('channel');light=cfg['related_light_id'] if cfg else None
        open_row=c.execute("SELECT * FROM lca_sessions WHERE device_id=? AND channel_key IS ? AND status='open' ORDER BY started_at DESC LIMIT 1",(did,ch)).fetchone()
        if item['state']=='on' and not open_row:
            sid=f"{did}:{ch or 'main'}:{item['occurred_at']}"
            c.execute("INSERT OR IGNORE INTO lca_sessions(session_id,device_id,channel_key,related_light_id,started_at,start_event_id,status,updated_at) VALUES(?,?,?,?,?,?,?,?)",(sid,did,ch,light,item['occurred_at'],item['lca_event_id'],'open',now))
        elif item['state']=='off' and open_row:
            try:
                start=datetime.fromisoformat(open_row['started_at'].replace('Z','+00:00'));end=datetime.fromisoformat(item['occurred_at'].replace('Z','+00:00'));duration=max(0,int((end-start).total_seconds()))
            except ValueError:duration=None
            c.execute("UPDATE lca_sessions SET ended_at=?,duration_seconds=?,end_event_id=?,status='closed',updated_at=? WHERE session_id=?",(item['occurred_at'],duration,item['lca_event_id'],now,open_row['session_id']))
    def devices(self):
        with self.db.connect() as c:
            rows=c.execute("SELECT d.*,(SELECT COUNT(*) FROM lca_channels x WHERE x.device_id=d.device_id) channel_count FROM lca_devices d ORDER BY CASE d.status WHEN 'discovered' THEN 0 WHEN 'incomplete' THEN 1 ELSE 2 END,d.name").fetchall()
            return [dict(r) for r in rows]
    def device(self,did):
        with self.db.connect() as c:
            d=c.execute("SELECT * FROM lca_devices WHERE device_id=?",(did,)).fetchone()
            if not d:return None
            channels=c.execute("SELECT * FROM lca_channels WHERE device_id=? ORDER BY channel_key",(did,)).fetchall()
            out=dict(d);out['channels']=[dict(x) for x in channels];return out
    def update_device(self,did,p):
        allowed=['name','device_type','status','location_id','location_name','adjacent_location_id','adjacent_location_name','position_label','notes']
        fields=[k for k in allowed if k in p]
        if not fields:return self.device(did)
        with self.db.connect() as c:
            vals=[p[k] for k in fields];vals += [datetime.now(timezone.utc).isoformat(),did]
            c.execute(f"UPDATE lca_devices SET {','.join(k+'=?' for k in fields)},updated_at=? WHERE device_id=?",vals)
        return self.device(did)
    def update_channel(self,did,ch,p):
        allowed=['name','interaction_point','location_id','location_name','adjacent_location_id','adjacent_location_name','direction_hint','related_light_id','related_light_name','virtual_parallel_group','enabled']
        fields=[k for k in allowed if k in p]
        with self.db.connect() as c:
            now=datetime.now(timezone.utc).isoformat();cid=f"{did}:{ch}"
            c.execute("INSERT OR IGNORE INTO lca_channels(channel_id,device_id,channel_key,created_at,updated_at) VALUES(?,?,?,?,?)",(cid,did,ch,now,now))
            if fields:
                vals=[1 if p[k] is True else 0 if p[k] is False else p[k] for k in fields]+[now,did,ch]
                c.execute(f"UPDATE lca_channels SET {','.join(k+'=?' for k in fields)},updated_at=? WHERE device_id=? AND channel_key=?",vals)
        return self.device(did)
    def events(self,hours=24,limit=200,device_id=None):
        since=(datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat();where=['occurred_at>=?'];params=[since]
        if device_id:where.append('device_id=?');params.append(device_id)
        params.append(limit)
        with self.db.connect() as c:return [dict(r) for r in c.execute(f"SELECT * FROM lca_events WHERE {' AND '.join(where)} ORDER BY occurred_at DESC LIMIT ?",params).fetchall()]
    def dashboard(self,hours=24):
        since=(datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat()
        with self.db.connect() as c:
            totals=dict(c.execute("SELECT COUNT(*) events,COUNT(DISTINCT device_id) active_devices FROM lca_events WHERE occurred_at>=?",(since,)).fetchone())
            totals['discovered_devices']=c.execute("SELECT COUNT(*) FROM lca_devices").fetchone()[0]
            totals['unconfigured_devices']=c.execute("SELECT COUNT(*) FROM lca_devices WHERE status IN ('discovered','incomplete')").fetchone()[0]
            totals['interactions']=c.execute("SELECT COUNT(*) FROM lca_events WHERE occurred_at>=? AND kind='interaction'",(since,)).fetchone()[0]
            totals['state_changes']=c.execute("SELECT COUNT(*) FROM lca_events WHERE occurred_at>=? AND kind='state'",(since,)).fetchone()[0]
            totals['open_sessions']=c.execute("SELECT COUNT(*) FROM lca_sessions WHERE status='open'").fetchone()[0]
            by_hour=[dict(r) for r in c.execute("SELECT substr(occurred_at,1,13)||':00' bucket,COUNT(*) value FROM lca_events WHERE occurred_at>=? GROUP BY bucket ORDER BY bucket",(since,)).fetchall()]
            top=[dict(r) for r in c.execute("SELECT COALESCE(d.name,e.device_id) name,e.device_id,COUNT(*) events FROM lca_events e LEFT JOIN lca_devices d ON d.device_id=e.device_id WHERE e.occurred_at>=? GROUP BY e.device_id ORDER BY events DESC LIMIT 10",(since,)).fetchall()]
            routes=[dict(r) for r in c.execute("SELECT origin_location_name,adjacent_location_name,direction_hint,COUNT(*) evidence_count,MAX(occurred_at) last_seen FROM lca_events WHERE occurred_at>=? AND kind='interaction' AND (direction_hint IS NOT NULL OR adjacent_location_name IS NOT NULL) GROUP BY origin_location_name,adjacent_location_name,direction_hint ORDER BY evidence_count DESC LIMIT 10",(since,)).fetchall()]
            recent=[dict(r) for r in c.execute("SELECT e.*,d.name device_name FROM lca_events e LEFT JOIN lca_devices d ON d.device_id=e.device_id WHERE e.occurred_at>=? ORDER BY e.occurred_at DESC LIMIT 30",(since,)).fetchall()]
        return {'period_hours':hours,'summary':totals,'by_hour':by_hour,'top_devices':top,'route_evidence':routes,'recent_events':recent,'updated_at':datetime.now(timezone.utc).isoformat()}
