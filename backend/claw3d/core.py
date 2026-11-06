"""Persistent domain primitives for Claw3D Orchestra (stdlib only)."""
from __future__ import annotations
import json, os, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path

STATUSES = {"PENDING", "PLANNED", "RUNNING", "REVIEW", "AWAITING_APPROVAL", "COMPLETED", "FAILED", "SUSPENDED"}
TRANSITIONS = {
    "PENDING": {"PLANNED", "SUSPENDED"}, "PLANNED": {"RUNNING", "SUSPENDED"},
    "RUNNING": {"REVIEW", "FAILED", "SUSPENDED"}, "REVIEW": {"AWAITING_APPROVAL", "COMPLETED", "FAILED", "RUNNING"},
    "AWAITING_APPROVAL": {"COMPLETED", "RUNNING", "SUSPENDED"}, "SUSPENDED": {"PLANNED", "RUNNING", "FAILED"},
    "COMPLETED": set(), "FAILED": set(),
}
PROVIDERS = [("deepseek", "DeepSeek", "DEEPSEEK_API_KEY"), ("grok", "Grok", "GROK_API_KEY"), ("groq", "Groq", "GROQ_API_KEY")]
SKILLS = [
    ("market-research", "Recherche de marché", "1.0.0", "Collecter et organiser les éléments de marché."),
    ("competitive-analysis", "Analyse concurrentielle", "1.0.0", "Comparer les concurrents sur des critères explicites."),
    ("opportunity-analysis", "Analyse d’opportunité", "1.0.0", "Évaluer une opportunité à partir d’hypothèses documentées."),
    ("fact-check", "Vérification d’informations", "1.0.0", "Vérifier des affirmations et consigner leurs sources."),
    ("financial-estimate", "Estimation financière", "1.0.0", "Produire une estimation en rendant les hypothèses visibles."),
    ("decision-synthesis", "Synthèse décisionnelle", "1.0.0", "Synthétiser les éléments pour une décision humaine."),
]
BOTS = [("researcher", "Chercheur", "research", "Recherche et collecte"), ("analyst", "Analyste", "analysis", "Analyse et comparaison"), ("verifier", "Vérificateur", "quality", "Vérification des affirmations"), ("critic", "Critique", "quality", "Contre-arguments et risques"), ("synthesizer", "Synthétiseur", "leadership", "Synthèse des résultats"), ("mission-lead", "Responsable de mission", "leadership", "Coordination des missions"), ("director", "Directeur", "leadership", "Approbations et arbitrages")]

def utcnow() -> str: return datetime.now(timezone.utc).isoformat(timespec="seconds")
def new_id(prefix: str) -> str: return f"{prefix}_{uuid.uuid4().hex[:12]}"

class Store:
    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("CLAW3D_DB_PATH", "data/claw3d.sqlite3")
        if self.path != ":memory:": Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.init()
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db
    def init(self):
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS providers (id TEXT PRIMARY KEY, name TEXT NOT NULL, env_key TEXT NOT NULL, status TEXT NOT NULL, last_error TEXT, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS bots (id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, department TEXT NOT NULL, skills TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'AVAILABLE');
            CREATE TABLE IF NOT EXISTS skills (id TEXT PRIMARY KEY, name TEXT NOT NULL, version TEXT NOT NULL, description TEXT NOT NULL, risk TEXT NOT NULL DEFAULT 'LOW', permissions TEXT NOT NULL DEFAULT '[]');
            CREATE TABLE IF NOT EXISTS missions (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL, priority TEXT NOT NULL, department TEXT NOT NULL, owner TEXT NOT NULL, status TEXT NOT NULL, budget_cents INTEGER NOT NULL, created_at TEXT NOT NULL, result TEXT);
            CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL, resource_type TEXT NOT NULL, resource_id TEXT NOT NULL, result TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS spend (id TEXT PRIMARY KEY, mission_id TEXT, department TEXT NOT NULL, amount_cents INTEGER NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(mission_id) REFERENCES missions(id));
            CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, expires_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS departments (id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PLANNED');
            CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', assigned_bot TEXT, created_at TEXT NOT NULL, FOREIGN KEY(mission_id) REFERENCES missions(id));
            CREATE TABLE IF NOT EXISTS models (id TEXT PRIMARY KEY, provider_id TEXT NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'UNCONFIGURED', FOREIGN KEY(provider_id) REFERENCES providers(id));
            CREATE TABLE IF NOT EXISTS budgets (id TEXT PRIMARY KEY, scope TEXT NOT NULL, scope_id TEXT NOT NULL, limit_cents INTEGER NOT NULL, period TEXT NOT NULL DEFAULT 'DAILY');
            CREATE TABLE IF NOT EXISTS decisions (id TEXT PRIMARY KEY, mission_id TEXT, summary TEXT NOT NULL, decided_by TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(mission_id) REFERENCES missions(id));
            CREATE TABLE IF NOT EXISTS meetings (id TEXT PRIMARY KEY, topic TEXT NOT NULL, participants TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, resource_type TEXT NOT NULL, resource_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', requested_at TEXT NOT NULL, decided_at TEXT);
            ''')
            c.execute("INSERT OR IGNORE INTO settings VALUES ('daily_budget_cents','500')")
            c.execute("INSERT OR IGNORE INTO departments VALUES ('general','Général','ACTIVE')")
            c.execute("INSERT OR IGNORE INTO budgets VALUES ('daily-org','organization','claw3d',500,'DAILY')")
            for pid, name, env in PROVIDERS:
                status = "CONFIGURED" if os.getenv(env, "").strip() else "WAITING_FOR_API_KEY"
                c.execute("INSERT OR IGNORE INTO providers VALUES (?,?,?,?,?,?)", (pid,name,env,status,None,utcnow()))
                c.execute("UPDATE providers SET status=?,updated_at=? WHERE id=?", (status,utcnow(),pid))
            for bid,name,role,dept in BOTS:
                c.execute("INSERT OR IGNORE INTO bots VALUES (?,?,?,?,?,'AVAILABLE')",(bid,name,role,dept,json.dumps([s[0] for s in SKILLS])))
            for sid,name,version,desc in SKILLS:
                c.execute("INSERT OR IGNORE INTO skills VALUES (?,?,?,?, 'LOW','[]')",(sid,name,version,desc))
    def event(self, actor, action, rtype, rid, result="OK", error=None):
        with self.connect() as c: c.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?)",(new_id("evt"),actor,action,rtype,rid,result,error,utcnow()))
    def daily_spend(self):
        day = utcnow()[:10]
        with self.connect() as c: return c.execute("SELECT COALESCE(SUM(amount_cents),0) FROM spend WHERE substr(created_at,1,10)=?",(day,)).fetchone()[0]
    def budget(self):
        with self.connect() as c:
            limit = int(c.execute("SELECT value FROM settings WHERE key='daily_budget_cents'").fetchone()[0])
        return {"daily_limit_cents":limit,"spent_today_cents":self.daily_spend(),"circuit_breaker":self.daily_spend() >= limit}
    def providers(self):
        with self.connect() as c: rows = c.execute("SELECT id,name,env_key,status,last_error,updated_at FROM providers ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    def create_mission(self, payload):
        required = ("title", "description")
        if any(not isinstance(payload.get(k),str) or not payload[k].strip() for k in required): raise ValueError("title and description are required")
        budget = payload.get("budget_cents", 0)
        if not isinstance(budget,int) or isinstance(budget,bool) or budget < 0: raise ValueError("budget_cents must be a non-negative integer")
        bid = new_id("mis"); ts=utcnow()
        with self.connect() as c:
            c.execute("INSERT INTO missions VALUES (?,?,?,?,?,?,?,?,?,NULL)",(bid,payload["title"].strip(),payload["description"].strip(),payload.get("priority","NORMAL"),payload.get("department","general"),payload.get("owner","director"),"PENDING",budget,ts))
            c.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?)",(new_id("evt"),"human","mission.created","mission",bid,"OK",None,ts))
        return self.get_mission(bid)
    def get_mission(self, mid):
        with self.connect() as c:
            row=c.execute("SELECT * FROM missions WHERE id=?",(mid,)).fetchone()
            if not row: return None
            d=dict(row); d["events"]=[dict(r) for r in c.execute("SELECT id,actor,action,result,error,created_at FROM events WHERE resource_type='mission' AND resource_id=? ORDER BY created_at",(mid,))]
            return d
    def transition(self, mid, status, actor="human"):
        if status not in STATUSES: raise ValueError("unknown status")
        if status == "RUNNING": raise ValueError("execution engine is not implemented; mission remains queued")
        with self.connect() as c:
            row=c.execute("SELECT status FROM missions WHERE id=?",(mid,)).fetchone()
            if not row: return None
            old=row[0]
            if status not in TRANSITIONS[old]: raise ValueError(f"transition {old} -> {status} is not allowed")
            c.execute("UPDATE missions SET status=? WHERE id=?",(status,mid))
            c.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?)",(new_id("evt"),actor,"mission.status_changed","mission",mid,status,None,utcnow()))
        return self.get_mission(mid)
    def missions(self):
        with self.connect() as c: return [dict(r) for r in c.execute("SELECT * FROM missions ORDER BY created_at DESC")]
