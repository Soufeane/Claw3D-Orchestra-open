import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.claw3d.approvals import (
    ApprovalEngine, ApprovalExpired, ApprovalMismatch, ApprovalStateError,
)
from backend.claw3d.core import Store
from backend.claw3d.costs import BudgetExceeded, CostManager, IdempotencyConflict, ReservationFinalized
from backend.claw3d.providers import FixtureProvider, ProviderNotReady, WaitingProvider


class ProviderContractTests(unittest.TestCase):
    def test_fixture_is_deterministic_labeled_and_zero_cost(self):
        provider = FixtureProvider(response_text="FIXTURE: fixed")
        self.assertEqual(provider.availability().status, "FIXTURE_ONLY")
        self.assertFalse(provider.availability().operational)
        self.assertFalse(provider.availability().network_enabled)
        request = provider.prepare_request("hello", {"case": 1})
        one = provider.execute(request)
        two = provider.execute(request)
        self.assertEqual(one, two)
        self.assertEqual(one.source, "LOCAL_FIXTURE")
        self.assertTrue(one.is_fixture)
        self.assertEqual(provider.estimate_cost(request).amount_cents, 0)
        self.assertTrue(provider.estimate_cost(request).simulated)
        self.assertFalse(provider.cancel("no-running-task"))

    def test_waiting_provider_never_prepares_or_executes(self):
        provider = WaitingProvider("sample-real-provider")
        self.assertEqual(provider.availability().status, "WAITING_FOR_PROVIDER")
        self.assertFalse(provider.availability().configured)
        self.assertFalse(provider.availability().operational)
        self.assertFalse(provider.validate_configuration({"api_key": "not-used"}))
        with self.assertRaises(ProviderNotReady):
            provider.prepare_request("must not be sent")
        with self.assertRaises(ProviderNotReady):
            provider.execute(None)

    def test_fixture_rejects_empty_prompt_and_foreign_request(self):
        provider = FixtureProvider()
        with self.assertRaises(ValueError):
            provider.prepare_request("  ")
        from backend.claw3d.providers import ProviderError, ProviderRequest
        with self.assertRaises(ProviderError):
            provider.execute(ProviderRequest("other", "prompt", {}))


class ControlTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "controls.sqlite3"
        self.store = Store(str(self.db))
        self.mission = self.store.create_mission({"title": "Control tests", "description": "temporary fixture"})

    def tearDown(self):
        self.tmp.cleanup()


class CostManagerTests(ControlTestCase):
    def setUp(self):
        super().setUp()
        self.costs = CostManager(self.db)

    def reserve(self, key, cents, mission_id=None):
        return self.costs.reserve(
            idempotency_key=key,
            mission_id=mission_id or self.mission["id"],
            agent_id="agent-fixture",
            provider_id="fixture-local",
            department="general",
            estimated_cents=cents,
        )

    def test_reserve_consume_and_prevent_double_consumption(self):
        reservation = self.reserve("operation-1", 150)
        self.assertEqual(reservation["status"], "RESERVED")
        self.assertEqual(self.costs.summary()["reserved_cents"], 150)
        consumed = self.costs.consume(reservation["id"], 100, cost_source="FIXTURE_SIMULATED")
        self.assertEqual(consumed["status"], "CONSUMED")
        self.assertEqual(consumed["actual_cents"], 100)
        self.assertEqual(consumed["cost_source"], "FIXTURE_SIMULATED")
        summary = self.costs.summary()
        self.assertEqual(summary["spent_cents"], 100)
        self.assertEqual(summary["reserved_cents"], 0)
        with self.assertRaises(ReservationFinalized):
            self.costs.consume(reservation["id"], 100)

    def test_release_frees_budget_and_is_single_use(self):
        reservation = self.reserve("release-me", 400)
        released = self.costs.release(reservation["id"])
        self.assertEqual(released["status"], "RELEASED")
        self.assertEqual(self.costs.summary()["reserved_cents"], 0)
        self.assertEqual(self.reserve("after-release", 500)["status"], "RESERVED")
        with self.assertRaises(ReservationFinalized):
            self.costs.release(reservation["id"])

    def test_budget_overrun_negative_and_actual_above_reservation_are_rejected(self):
        with self.assertRaises(BudgetExceeded):
            self.reserve("too-much", 501)
        with self.assertRaises(ValueError):
            self.reserve("negative", -1)
        reservation = self.reserve("cap", 100)
        with self.assertRaises(BudgetExceeded):
            self.costs.consume(reservation["id"], 101)
        self.assertEqual(self.costs.summary()["reserved_cents"], 100)

    def test_idempotency_key_returns_same_reservation_and_rejects_changed_payload(self):
        first = self.reserve("same-key", 100)
        duplicate = self.reserve("same-key", 100)
        self.assertEqual(first["id"], duplicate["id"])
        with self.assertRaises(IdempotencyConflict):
            self.reserve("same-key", 200)
        self.assertEqual(self.costs.summary()["reserved_cents"], 100)

    def test_mission_and_agent_limits_apply(self):
        self.costs.set_limit("mission", self.mission["id"], 120)
        with self.assertRaises(BudgetExceeded):
            self.reserve("mission-over", 121)
        self.costs.set_limit("agent", "agent-fixture", 80)
        with self.assertRaises(BudgetExceeded):
            self.reserve("agent-over", 81)

    def test_global_circuit_breaker_stops_new_reservations(self):
        self.costs.set_circuit_breaker(True)
        with self.assertRaisesRegex(BudgetExceeded, "circuit breaker"):
            self.reserve("blocked-by-breaker", 0)
        self.assertTrue(self.costs.summary()["circuit_breaker"])
        self.costs.set_circuit_breaker(False)
        self.assertEqual(self.reserve("after-breaker", 0)["status"], "RESERVED")

    def test_global_limit_updates_legacy_setting_and_reserved_threshold(self):
        self.costs.set_limit("organization", "claw3d", 200)
        self.assertEqual(self.store.budget()["daily_limit_cents"], 200)
        reservation = self.reserve("fills-global-budget", 200)
        self.assertEqual(reservation["status"], "RESERVED")
        self.assertTrue(self.costs.summary()["circuit_breaker"])
        self.costs.release(reservation["id"])
        self.assertFalse(self.costs.summary()["circuit_breaker"])

    def test_two_concurrent_reservations_cannot_overrun_global_budget(self):
        barrier = threading.Barrier(2)
        def attempt(key):
            barrier.wait(timeout=5)
            try:
                return self.reserve(key, 300)["status"]
            except BudgetExceeded:
                return "REJECTED"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, ("parallel-a", "parallel-b")))
        self.assertCountEqual(outcomes, ["RESERVED", "REJECTED"])
        self.assertEqual(self.costs.summary()["reserved_cents"], 300)


class ApprovalEngineTests(ControlTestCase):
    def setUp(self):
        super().setUp()
        self.approvals = ApprovalEngine(self.db)
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.bound = {
            "mission_id": self.mission["id"],
            "requester_id": "agent-fixture",
            "action": "provider.request",
            "payload": {"prompt": "fixture only", "scope": ["read"]},
            "estimated_cost_cents": 42,
        }

    def request(self, **overrides):
        ttl_seconds = overrides.pop("ttl_seconds", 600)
        args = dict(self.bound)
        args.update(overrides)
        return self.approvals.request(**args, ttl_seconds=ttl_seconds, created_at=self.now)

    def consume(self, approval_id, **overrides):
        now = overrides.pop("now", self.now + timedelta(seconds=1))
        args = dict(self.bound)
        args.update(overrides)
        return self.approvals.consume(approval_id, **args, actor="owner", now=now)

    def test_approval_bound_to_exact_action_payload_and_consumed_once(self):
        request = self.request()
        self.assertNotIn("payload", request)
        self.assertEqual(len(request["payload_sha256"]), 64)
        approved = self.approvals.decide(request["id"], approve=True, actor="owner", now=self.now + timedelta(seconds=1))
        self.assertEqual(approved["status"], "APPROVED")
        consumed = self.consume(request["id"])
        self.assertEqual(consumed["status"], "CONSUMED")
        with self.assertRaises(ApprovalStateError):
            self.consume(request["id"])

    def test_rejection_prevents_action(self):
        request = self.request()
        rejected = self.approvals.decide(request["id"], approve=False, actor="owner", now=self.now + timedelta(seconds=1))
        self.assertEqual(rejected["status"], "REJECTED")
        with self.assertRaises(ApprovalStateError):
            self.consume(request["id"])

    def test_expiration_is_enforced_at_decision_and_consumption(self):
        request = self.request(ttl_seconds=10)
        expired = self.approvals.decide(request["id"], approve=True, actor="owner", now=self.now + timedelta(seconds=10))
        self.assertEqual(expired["status"], "EXPIRED")
        request2 = self.request(action="another.action")
        self.approvals.decide(request2["id"], approve=True, actor="owner", now=self.now + timedelta(seconds=1))
        with self.assertRaises(ApprovalExpired):
            self.consume(request2["id"], action="another.action", now=self.now + timedelta(seconds=601))
        self.assertEqual(self.approvals.get(request2["id"])["status"], "EXPIRED")

    def test_changed_payload_action_mission_requester_or_cost_is_rejected(self):
        request = self.request()
        self.approvals.decide(request["id"], approve=True, actor="owner", now=self.now + timedelta(seconds=1))
        for change in (
            {"payload": {"prompt": "altered", "scope": ["read"]}},
            {"action": "provider.delete"},
            {"mission_id": "other-mission"},
            {"requester_id": "other-agent"},
            {"estimated_cost_cents": 43},
        ):
            with self.subTest(change=change), self.assertRaises(ApprovalMismatch):
                self.consume(request["id"], **change)
        self.assertEqual(self.approvals.get(request["id"])["status"], "APPROVED")

    def test_two_concurrent_consumers_only_one_succeeds(self):
        request = self.request()
        self.approvals.decide(request["id"], approve=True, actor="owner", now=self.now + timedelta(seconds=1))
        barrier = threading.Barrier(2)
        def attempt(_):
            barrier.wait(timeout=5)
            try:
                self.consume(request["id"])
                return "CONSUMED"
            except ApprovalStateError:
                return "REJECTED"
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, range(2)))
        self.assertCountEqual(outcomes, ["CONSUMED", "REJECTED"])
        self.assertEqual(self.approvals.get(request["id"])["status"], "CONSUMED")

    def test_missing_approval_is_denied_and_audit_omits_raw_payload(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.consume("missing-approval")
        request = self.request(payload={"secret_like_text": "private payload fixture"})
        with sqlite3.connect(self.db) as conn:
            logs = " ".join(str(tuple(row)) for row in conn.execute("SELECT * FROM events WHERE resource_type='approval'"))
        self.assertNotIn("private payload fixture", logs)
        self.assertEqual(request["status"], "PENDING")


if __name__ == "__main__":
    unittest.main()
