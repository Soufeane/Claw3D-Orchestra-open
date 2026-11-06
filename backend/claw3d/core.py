"""Persistent domain primitives for Claw3D Orchestra (stdlib only)."""
from __future__ import annotations
import json, os, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from .migrations import migrate

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
    def __init__(self, path: str | None = None, migrations_dir: Path | None = None):
        self.path = path or os.getenv("CLAW3D_DB_PATH", "data/claw3d.sqlite3")
        self.migrations_dir = migrations_dir
        if self.path != ":memory:": Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.init()
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db
    def init(self):
        with self.connect() as c:
            migrate(c, self.path, self.migrations_dir) if self.migrations_dir else migrate(c, self.path)
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
