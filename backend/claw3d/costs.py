"""Atomic SQLite cost reservations and budget circuit breaker; no provider calls."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


class CostError(RuntimeError):
    pass


class BudgetExceeded(CostError):
    pass


class IdempotencyConflict(CostError):
    pass


class ReservationFinalized(CostError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _event(conn: sqlite3.Connection, actor: str, action: str, resource_type: str, resource_id: str, result: str) -> None:
    conn.execute(
        "INSERT INTO events VALUES (?,?,?,?,?,?,?,?)",
        (_id("evt"), actor, action, resource_type, resource_id, result, None, _now()),
    )


class CostManager:
    """Budget manager with transaction-level serialization via BEGIN IMMEDIATE."""

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)

    def set_limit(self, scope: str, scope_id: str, limit_cents: int, actor: str = "owner") -> dict:
        if scope not in {"organization", "mission", "agent"}:
            raise ValueError("unsupported budget scope")
        if not scope_id or not isinstance(scope_id, str):
            raise ValueError("scope_id is required")
        if scope == "organization" and scope_id != "claw3d":
            raise ValueError("only the organization scope 'claw3d' is supported")
        if not isinstance(limit_cents, int) or isinstance(limit_cents, bool) or limit_cents < 0:
            raise ValueError("limit_cents must be a non-negative integer")
        conn = _connect(self.database_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT id FROM budgets WHERE scope=? AND scope_id=? AND period='DAILY' ORDER BY id LIMIT 1", (scope, scope_id)).fetchone()
            if row:
                conn.execute("UPDATE budgets SET limit_cents=? WHERE id=?", (limit_cents, row[0]))
                budget_id = row[0]
            else:
                budget_id = _id("bud")
                conn.execute("INSERT INTO budgets(id,scope,scope_id,limit_cents,period) VALUES(?,?,?,?,'DAILY')", (budget_id, scope, scope_id, limit_cents))
            if scope == "organization":
                conn.execute("INSERT INTO settings(key,value) VALUES('daily_budget_cents',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(limit_cents),))
            _event(conn, actor, "budget.limit_set", "budget", budget_id, "OK")
            conn.commit()
            return {"id": budget_id, "scope": scope, "scope_id": scope_id, "limit_cents": limit_cents, "period": "DAILY"}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def set_circuit_breaker(self, enabled: bool, actor: str = "owner") -> None:
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be boolean")
        conn = _connect(self.database_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO settings(key,value) VALUES('cost_circuit_breaker',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", ("1" if enabled else "0",))
            _event(conn, actor, "budget.circuit_breaker_changed", "budget", "organization", "ENABLED" if enabled else "DISABLED")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def reserve(self, *, idempotency_key: str, mission_id: str, agent_id: str, provider_id: str,
                department: str, estimated_cents: int, reserve_cents: int | None = None,
                actor: str = "system") -> dict:
        reserve_cents = estimated_cents if reserve_cents is None else reserve_cents
        for name, amount in (("estimated_cents", estimated_cents), ("reserve_cents", reserve_cents)):
            if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if reserve_cents < estimated_cents:
            raise ValueError("reserve_cents cannot be lower than estimated_cents")
        if not idempotency_key or len(idempotency_key) > 200:
            raise ValueError("idempotency_key is required and must be at most 200 characters")
        for name, value in (("mission_id", mission_id), ("agent_id", agent_id), ("provider_id", provider_id), ("department", department)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        conn = _connect(self.database_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT * FROM cost_reservations WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if existing:
                same = (existing["mission_id"] == mission_id and existing["agent_id"] == agent_id
                        and existing["provider_id"] == provider_id and existing["department"] == department
                        and existing["estimated_cents"] == estimated_cents and existing["reserved_cents"] == reserve_cents)
                if not same:
                    raise IdempotencyConflict("idempotency key was already used for a different reservation")
                conn.commit()
                return dict(existing)
            if conn.execute("SELECT 1 FROM missions WHERE id=?", (mission_id,)).fetchone() is None:
                raise ValueError("mission does not exist")
            breaker = conn.execute("SELECT value FROM settings WHERE key='cost_circuit_breaker'").fetchone()
            if breaker and breaker[0] == "1":
                raise BudgetExceeded("global cost circuit breaker is enabled")
            today = _now()[:10]
            scopes = [("organization", "claw3d"), ("mission", mission_id), ("agent", agent_id)]
            for scope, scope_id in scopes:
                limit_row = conn.execute("SELECT limit_cents FROM budgets WHERE scope=? AND scope_id=? AND period='DAILY' ORDER BY id LIMIT 1", (scope, scope_id)).fetchone()
                if limit_row is None:
                    if scope == "organization":
                        setting = conn.execute("SELECT value FROM settings WHERE key='daily_budget_cents'").fetchone()
                        limit = int(setting[0]) if setting else 0
                    else:
                        continue
                else:
                    limit = int(limit_row[0])
                if scope == "organization":
                    actual = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM spend WHERE substr(created_at,1,10)=?", (today,)).fetchone()[0]
                    held = conn.execute("SELECT COALESCE(SUM(reserved_cents),0) FROM cost_reservations WHERE status='RESERVED' AND substr(created_at,1,10)=?", (today,)).fetchone()[0]
                elif scope == "mission":
                    actual = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM spend WHERE mission_id=? AND substr(created_at,1,10)=?", (mission_id, today)).fetchone()[0]
                    held = conn.execute("SELECT COALESCE(SUM(reserved_cents),0) FROM cost_reservations WHERE mission_id=? AND status='RESERVED' AND substr(created_at,1,10)=?", (mission_id, today)).fetchone()[0]
                else:
                    actual = conn.execute("SELECT COALESCE(SUM(actual_cents),0) FROM cost_reservations WHERE agent_id=? AND status='CONSUMED' AND substr(finalized_at,1,10)=?", (agent_id, today)).fetchone()[0]
                    held = conn.execute("SELECT COALESCE(SUM(reserved_cents),0) FROM cost_reservations WHERE agent_id=? AND status='RESERVED' AND substr(created_at,1,10)=?", (agent_id, today)).fetchone()[0]
                if int(actual) + int(held) + reserve_cents > limit:
                    raise BudgetExceeded(f"{scope} daily budget exceeded")
            reservation_id = _id("res")
            created = _now()
            conn.execute(
                "INSERT INTO cost_reservations(id,idempotency_key,mission_id,agent_id,provider_id,department,estimated_cents,reserved_cents,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (reservation_id, idempotency_key, mission_id, agent_id, provider_id, department, estimated_cents, reserve_cents, "RESERVED", created),
            )
            _event(conn, actor, "cost.reserved", "cost_reservation", reservation_id, "RESERVED")
            conn.commit()
            return dict(conn.execute("SELECT * FROM cost_reservations WHERE id=?", (reservation_id,)).fetchone())
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def consume(self, reservation_id: str, actual_cents: int, *, cost_source: str = "FIXTURE_SIMULATED", actor: str = "system") -> dict:
        if not isinstance(actual_cents, int) or isinstance(actual_cents, bool) or actual_cents < 0:
            raise ValueError("actual_cents must be a non-negative integer")
        if cost_source not in {"FIXTURE_SIMULATED", "OPERATOR_RECORDED"}:
            raise ValueError("cost_source must identify a fixture or operator-recorded amount")
        conn = _connect(self.database_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM cost_reservations WHERE id=?", (reservation_id,)).fetchone()
            if row is None:
                raise ValueError("reservation does not exist")
            if row["status"] != "RESERVED":
                raise ReservationFinalized("reservation is already finalized")
            if actual_cents > row["reserved_cents"]:
                raise BudgetExceeded("actual cost exceeds the reserved amount")
            finalized = _now()
            conn.execute("UPDATE cost_reservations SET status='CONSUMED',actual_cents=?,cost_source=?,finalized_at=? WHERE id=? AND status='RESERVED'", (actual_cents, cost_source, finalized, reservation_id))
            conn.execute("INSERT INTO spend(id,mission_id,department,amount_cents,created_at) VALUES(?,?,?,?,?)", (_id("spend"), row["mission_id"], row["department"], actual_cents, finalized))
            _event(conn, actor, "cost.consumed", "cost_reservation", reservation_id, cost_source)
            conn.commit()
            return dict(conn.execute("SELECT * FROM cost_reservations WHERE id=?", (reservation_id,)).fetchone())
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def release(self, reservation_id: str, *, actor: str = "system") -> dict:
        conn = _connect(self.database_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM cost_reservations WHERE id=?", (reservation_id,)).fetchone()
            if row is None:
                raise ValueError("reservation does not exist")
            if row["status"] != "RESERVED":
                raise ReservationFinalized("reservation is already finalized")
            conn.execute("UPDATE cost_reservations SET status='RELEASED',finalized_at=? WHERE id=? AND status='RESERVED'", (_now(), reservation_id))
            _event(conn, actor, "cost.released", "cost_reservation", reservation_id, "RELEASED")
            conn.commit()
            return dict(conn.execute("SELECT * FROM cost_reservations WHERE id=?", (reservation_id,)).fetchone())
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def summary(self) -> dict:
        conn = _connect(self.database_path)
        try:
            today = _now()[:10]
            limit = conn.execute("SELECT limit_cents FROM budgets WHERE scope='organization' AND scope_id='claw3d' AND period='DAILY' ORDER BY id LIMIT 1").fetchone()
            if limit is None:
                limit = conn.execute("SELECT value FROM settings WHERE key='daily_budget_cents'").fetchone()
                limit_cents = int(limit[0]) if limit else 0
            else:
                limit_cents = int(limit[0])
            spent = int(conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM spend WHERE substr(created_at,1,10)=?", (today,)).fetchone()[0])
            reserved = int(conn.execute("SELECT COALESCE(SUM(reserved_cents),0) FROM cost_reservations WHERE status='RESERVED' AND substr(created_at,1,10)=?", (today,)).fetchone()[0])
            breaker = conn.execute("SELECT value FROM settings WHERE key='cost_circuit_breaker'").fetchone()
            threshold_reached = limit_cents == 0 or spent + reserved >= limit_cents
            return {"period": "DAILY", "limit_cents": limit_cents, "spent_cents": spent, "reserved_cents": reserved, "available_cents": max(0, limit_cents-spent-reserved), "circuit_breaker": bool((breaker and breaker[0] == "1") or threshold_reached), "cost_source_note": "Provider-reported real costs are unavailable until a real provider is integrated."}
        finally:
            conn.close()
