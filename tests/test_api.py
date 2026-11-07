import json, os, tempfile, threading, unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from backend.claw3d import server
from backend.claw3d.core import Store

class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(); cls.old_store=server.STORE; server.STORE=Store(os.path.join(cls.tmp.name,"http.sqlite3"))
        cls.http=ThreadingHTTPServer(("127.0.0.1",0),server.Handler); cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True); cls.thread.start(); cls.base=f"http://127.0.0.1:{cls.http.server_port}"
        cls.old_password=os.environ.get("CLAW3D_ADMIN_PASSWORD"); os.environ["CLAW3D_ADMIN_PASSWORD"]="test-password-long-enough"
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown(); cls.http.server_close(); cls.thread.join(timeout=2); server.STORE=cls.old_store
        if cls.old_password is None: os.environ.pop("CLAW3D_ADMIN_PASSWORD",None)
        else: os.environ["CLAW3D_ADMIN_PASSWORD"]=cls.old_password
        cls.tmp.cleanup()
    def setUp(self):
        with server._LOGIN_LOCK: server._LOGIN_FAILURES.clear()
    def call(self,path,method="GET",payload=None,cookie=None,csrf=False,raw_body=None,content_type="application/json"):
        headers={"Content-Type":content_type}
        if cookie: headers["Cookie"]=cookie
        if csrf: headers["X-Claw3D-Request"]="1"
        data=raw_body if raw_body is not None else (json.dumps(payload).encode() if payload is not None else None)
        req=Request(self.base+path,data=data,headers=headers,method=method)
        try:
            with urlopen(req,timeout=3) as r: return r.status,json.loads(r.read()),r.headers
        except HTTPError as e: return e.code,json.loads(e.read()),e.headers
    def test_health_ready_and_private_routes(self):
        self.assertEqual(self.call("/api/health")[0],200); self.assertEqual(self.call("/api/ready")[0],200); self.assertEqual(self.call("/api/missions")[0],401)
    def test_console_root_is_served(self):
        with urlopen(self.base+"/",timeout=3) as response:
            self.assertEqual(response.status,200)
            self.assertIn(b"Claw3D Orchestra",response.read())
    def test_login_then_csrf_and_mission_write(self):
        status,data,headers=self.call("/api/auth/login","POST",{"password":"test-password-long-enough"})
        self.assertEqual(status,200); cookie=headers["Set-Cookie"].split(";",1)[0]
        self.assertEqual(self.call("/api/missions","GET",cookie=cookie)[0],200)
        self.assertEqual(self.call("/api/missions","POST",{"title":"x","description":"y"},cookie=cookie)[0],403)
        status,mission,_=self.call("/api/missions","POST",{"title":"x","description":"y"},cookie=cookie,csrf=True)
        self.assertEqual(status,201); self.assertEqual(mission["status"],"PENDING")
    def test_invalid_password_denied(self):
        self.assertEqual(self.call("/api/auth/login","POST",{"password":"wrong"})[0],401)
    def test_login_rate_limit(self):
        for _ in range(server.LOGIN_MAX_FAILURES):
            self.assertEqual(self.call("/api/auth/login","POST",{"password":"wrong"})[0],401)
        status,body,headers=self.call("/api/auth/login","POST",{"password":"wrong"})
        self.assertEqual(status,429); self.assertEqual(headers.get("Retry-After"),str(server.LOGIN_WINDOW_SECONDS))
    def test_cookie_attributes_and_logout_requires_csrf_then_revokes_session(self):
        status,_,headers=self.call("/api/auth/login","POST",{"password":"test-password-long-enough"})
        self.assertEqual(status,200)
        cookie=headers["Set-Cookie"].split(";",1)[0]
        set_cookie=headers["Set-Cookie"]
        self.assertIn("HttpOnly",set_cookie); self.assertIn("SameSite=Strict",set_cookie); self.assertIn("Path=/",set_cookie)
        self.assertEqual(self.call("/api/auth/logout","POST",cookie=cookie)[0],403)
        self.assertEqual(self.call("/api/auth/logout","POST",cookie=cookie,csrf=True)[0],200)
        self.assertEqual(self.call("/api/missions",cookie=cookie)[0],401)
    def test_expired_session_is_rejected(self):
        import hashlib
        token="expired-session-fixture"
        with server.STORE.connect() as conn:
            conn.execute("INSERT INTO sessions VALUES (?,?)",(hashlib.sha256(token.encode()).hexdigest(),"2000-01-01T00:00:00+00:00"))
        self.assertEqual(self.call("/api/missions",cookie=f"claw3d_session={token}")[0],401)
    def test_malformed_json_and_oversized_payload_return_client_errors(self):
        _,_,headers=self.call("/api/auth/login","POST",{"password":"test-password-long-enough"})
        cookie=headers["Set-Cookie"].split(";",1)[0]
        self.assertEqual(self.call("/api/meetings","POST",cookie=cookie,csrf=True,raw_body=b"{bad")[0],400)
        oversized={"title":"x","description":"x"*(server.MAX_BODY_BYTES+100)}
        self.assertEqual(self.call("/api/missions","POST",oversized,cookie=cookie,csrf=True)[0],413)
    def test_ready_reports_sqlite_unavailable(self):
        original=server.STORE
        class BrokenStore:
            def connect(self): raise OSError("private database path must not be exposed")
        try:
            server.STORE=BrokenStore()
            status,body,_=self.call("/api/ready")
            self.assertEqual(status,503)
            self.assertEqual(body,{"status":"not_ready","database":"unavailable","external_calls_enabled":False})
        finally:
            server.STORE=original
    def test_meeting_is_persisted_as_waiting_not_executed(self):
        _,_,headers=self.call("/api/auth/login","POST",{"password":"test-password-long-enough"})
        cookie=headers["Set-Cookie"].split(";",1)[0]
        status,data,_=self.call("/api/meetings","POST",{"topic":"Revue de risques"},cookie=cookie,csrf=True)
        self.assertEqual(status,201)
        self.assertEqual(data["status"],"WAITING_FOR_PROVIDER")

if __name__=="__main__": unittest.main()
