import os, tempfile, unittest
from backend.claw3d.core import Store, TRANSITIONS

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.store=Store(os.path.join(self.tmp.name,"db.sqlite3"))
    def tearDown(self): self.tmp.cleanup()
    def test_initial_status_and_valid_transition(self):
        m=self.store.create_mission({"title":"Test","description":"Mission test"})
        self.assertEqual(m["status"],"PENDING")
        self.assertEqual(self.store.transition(m["id"],"PLANNED")["status"],"PLANNED")
    def test_invalid_transition_is_rejected(self):
        m=self.store.create_mission({"title":"Test","description":"Mission test"})
        with self.assertRaisesRegex(ValueError,"not allowed"):
            self.store.transition(m["id"],"COMPLETED")
    def test_completed_is_terminal(self): self.assertEqual(TRANSITIONS["COMPLETED"],set())
    def test_budget_default_and_circuit_breaker(self):
        self.assertEqual(self.store.budget(),{"daily_limit_cents":500,"spent_today_cents":0,"circuit_breaker":False})
    def test_initial_providers_wait_without_keys(self):
        old={k:os.environ.pop(k,None) for k in ("DEEPSEEK_API_KEY","GROK_API_KEY","GROQ_API_KEY")}
        try: self.assertTrue(all(p["status"]=="WAITING_FOR_API_KEY" for p in self.store.providers()))
        finally:
            for k,v in old.items():
                if v is not None: os.environ[k]=v
    def test_required_fields_and_budget_validation(self):
        with self.assertRaises(ValueError): self.store.create_mission({"title":"","description":"x"})
        with self.assertRaises(ValueError): self.store.create_mission({"title":"x","description":"y","budget_cents":-1})
    def test_mission_creation_audited(self):
        m=self.store.create_mission({"title":"Audit","description":"Test"})
        self.assertEqual(m["events"][0]["action"],"mission.created")

if __name__=="__main__": unittest.main()
