"""Small same-origin JSON server with server-side authentication."""
from __future__ import annotations
import hashlib, hmac, json, os, re, secrets, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlparse
from .core import Store, utcnow

STORE = None
SESSION_SECONDS = 8 * 60 * 60

def _hash(s): return hashlib.sha256(s.encode()).hexdigest()
def _secure(): return os.getenv("CLAW3D_COOKIE_SECURE", "0").lower() in {"1","true","yes"}

class Handler(BaseHTTPRequestHandler):
    server_version = "Claw3D/0.1"
    def log_message(self, fmt, *args):
        # Do not log request bodies, credentials, cookies or query strings.
        safe_path = self.path.split("?",1)[0]
        safe_args = (safe_path, *args[1:]) if args and isinstance(args[0], str) else args
        super().log_message(fmt, *safe_args)
    def send_json(self, code, value, headers=None):
        body=json.dumps(value,ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store")
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(body)
    def body(self):
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n > 65536: raise ValueError("request body too large")
            obj=json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(obj,dict): raise ValueError("JSON object required")
            return obj
        except (ValueError, json.JSONDecodeError) as e: raise ValueError(str(e))
    def session_hash(self):
        cookie=SimpleCookie()
        try: cookie.load(self.headers.get("Cookie","")); token=cookie.get("claw3d_session").value
        except Exception: return None
        with STORE.connect() as c:
            row=c.execute("SELECT token_hash FROM sessions WHERE token_hash=? AND expires_at>?",(_hash(token),utcnow())).fetchone()
        return row[0] if row else None
    def authorized(self):
        return self.session_hash() is not None
    def route(self):
        p=urlparse(self.path).path
        if p=="/api/health" and self.command=="GET": return self.send_json(200,{"status":"ok","time":utcnow()})
        if p=="/api/ready" and self.command=="GET":
            providers=STORE.providers()
            return self.send_json(200,{"status":"ready","database":"ok","configured_providers":sum(x["status"]=="CONFIGURED" for x in providers),"external_calls_enabled":False})
        if p=="/api/auth/login" and self.command=="POST":
            expected=os.getenv("CLAW3D_ADMIN_PASSWORD","")
            if len(expected)<12: return self.send_json(503,{"error":"Authentication unavailable: configure a 12+ character CLAW3D_ADMIN_PASSWORD in the server environment."})
            password=self.body().get("password","")
            if not isinstance(password,str) or not hmac.compare_digest(_hash(password),_hash(expected)):
                STORE.event("anonymous","auth.login","session","",result="DENIED",error="invalid credentials")
                return self.send_json(401,{"error":"Identifiants invalides."})
            token=secrets.token_urlsafe(32); expiry=int(time.time())+SESSION_SECONDS
            from datetime import datetime, timezone
            expires=datetime.fromtimestamp(expiry,timezone.utc).isoformat(timespec="seconds")
            with STORE.connect() as c: c.execute("INSERT INTO sessions VALUES (?,?)",(_hash(token),expires))
            STORE.event("human","auth.login","session","","OK")
            cookie=f"claw3d_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_SECONDS}" + ("; Secure" if _secure() else "")
            return self.send_json(200,{"authenticated":True},{"Set-Cookie":cookie})
        if p=="/api/auth/logout" and self.command=="POST":
            sh=self.session_hash()
            if sh:
                with STORE.connect() as c: c.execute("DELETE FROM sessions WHERE token_hash=?",(sh,))
            return self.send_json(200,{"authenticated":False},{"Set-Cookie":"claw3d_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0" + ("; Secure" if _secure() else "")})
        if p.startswith("/api/"):
            if not self.authorized(): return self.send_json(401,{"error":"Authentification requise."})
            if self.command not in {"GET","HEAD"} and self.headers.get("X-Claw3D-Request") != "1": return self.send_json(403,{"error":"En-tête anti-CSRF requis."})
            return self.api(p)
        # Static assets are same-origin; no directory traversal.
        filemap={"/":"index.html","/app.js":"app.js","/style.css":"style.css","/manus-routes.json":"manus-routes.json"}
        name=filemap.get(p)
        if not name: return self.send_json(404,{"error":"Not found"})
        path=Path(__file__).resolve().parents[2]/"frontend"/"static"/name
        data=path.read_bytes(); mime="application/json" if name.endswith(".json") else "text/"+ ("html" if name.endswith(".html") else "css" if name.endswith(".css") else "javascript")
        self.send_response(200); self.send_header("Content-Type",mime+"; charset=utf-8"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    def api(self,p):
        if p=="/api/me" and self.command=="GET": return self.send_json(200,{"authenticated":True})
        if p=="/api/summary" and self.command=="GET":
            with STORE.connect() as c:
                return self.send_json(200,{"missions":c.execute("SELECT status,COUNT(*) n FROM missions GROUP BY status").fetchall() and [dict(r) for r in c.execute("SELECT status,COUNT(*) n FROM missions GROUP BY status") ] or [],"bots":c.execute("SELECT COUNT(*) FROM bots").fetchone()[0],"skills":c.execute("SELECT COUNT(*) FROM skills").fetchone()[0],"budget":STORE.budget()})
        if p=="/api/providers" and self.command=="GET": return self.send_json(200,{"items":STORE.providers()})
        if p=="/api/budget" and self.command=="GET": return self.send_json(200,STORE.budget())
        if p=="/api/bots" and self.command=="GET":
            with STORE.connect() as c: return self.send_json(200,{"items":[dict(r) for r in c.execute("SELECT * FROM bots ORDER BY id")]})
        if p=="/api/skills" and self.command=="GET":
            with STORE.connect() as c: return self.send_json(200,{"items":[dict(r) for r in c.execute("SELECT * FROM skills ORDER BY id")]})
        if p=="/api/missions" and self.command=="GET": return self.send_json(200,{"items":STORE.missions()})
        if p=="/api/missions" and self.command=="POST":
            try:
                item=STORE.create_mission(self.body()); return self.send_json(201,item)
            except ValueError as e: return self.send_json(400,{"error":str(e)})
        match=re.fullmatch(r"/api/missions/([A-Za-z0-9_-]+)(?:/status)?",p)
        if match and p.endswith("/status") and self.command=="POST":
            try:
                item=STORE.transition(match.group(1),self.body().get("status",""))
                return self.send_json(404,{"error":"Mission introuvable."}) if item is None else self.send_json(200,item)
            except ValueError as e: return self.send_json(400,{"error":str(e)})
        if p=="/api/events" and self.command=="GET":
            with STORE.connect() as c: return self.send_json(200,{"items":[dict(r) for r in c.execute("SELECT * FROM events ORDER BY created_at DESC LIMIT 100")]})
        if p=="/api/meetings" and self.command=="POST":
            try:
                b=self.body(); topic=b.get("topic","")
                if not isinstance(topic,str) or not topic.strip(): raise ValueError("topic is required")
                mid="mtg_"+__import__("uuid").uuid4().hex[:12]; ts=utcnow()
                with STORE.connect() as c: c.execute("INSERT INTO meetings VALUES (?,?,?,?,?)",(mid,topic.strip(),json.dumps(b.get("participants",[])),"WAITING_FOR_PROVIDER",ts))
                STORE.event("human","meeting.created","meeting",mid,"WAITING_FOR_PROVIDER")
                return self.send_json(201,{"id":mid,"topic":topic.strip(),"status":"WAITING_FOR_PROVIDER","participants":b.get("participants",[]),"created_at":ts})
            except ValueError as e: return self.send_json(400,{"error":str(e)})
        return self.send_json(404,{"error":"Not found"})
    def do_GET(self): self.route()
    def do_POST(self): self.route()

def main():
    global STORE
    STORE = Store()
    host=os.getenv("CLAW3D_HOST","127.0.0.1"); port=int(os.getenv("CLAW3D_PORT","8000"))
    print(f"Claw3D Orchestra local server: http://{host}:{port}")
    ThreadingHTTPServer((host,port),Handler).serve_forever()
if __name__=="__main__": main()
