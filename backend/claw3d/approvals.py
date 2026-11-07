"""Human approval tokens bound to a canonical action payload and single use."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class ApprovalError(RuntimeError):
    pass


class ApprovalExpired(ApprovalError):
    pass


class ApprovalMismatch(ApprovalError):
    pass


class ApprovalStateError(ApprovalError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _canonical_payload(payload: Any) -> bytes:
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("payload must be JSON-serializable") from exc


def _payload_digest(payload: Any) -> str:
    return hashlib.sha256(_canonical_payload(payload)).hexdigest()


def _id() -> str:
    return "appr_" + uuid.uuid4().hex


def _connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _event(conn: sqlite3.Connection, actor: str, action: str, approval_id: str, result: str) -> None:
    conn.execute(
        "INSERT INTO events VALUES (?,?,?,?,?,?,?,?)",
        ("evt_" + uuid.uuid4().hex[:12], actor, action, "approval", approval_id, result, None, _stamp(_utcnow())),
    )


class ApprovalEngine:
    """Approvals are capabilities for one exact action, payload, mission and cost."""

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)

    def request(self, *, mission_id: str, requester_id: str, action: str, payload: Any,
                estimated_cost_cents: int, ttl_seconds: int = 900, created_at: datetime | None = None) -> dict:
        if not mission_id or not requester_id or not action or len(action) > 200:
            raise ValueError("mission_id, requester_id and action are required")
        if not isinstance(estimated_cost_cents, int) or isinstance(estimated_cost_cents, bool) or estimated_cost_cents < 0:
            raise ValueError("estimated_cost_cents must be a non-negative integer")
        if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or not 1 <= ttl_seconds <= 86400:
            raise ValueError("ttl_seconds must be between 1 and 86400")
        digest = _payload_digest(payload)
        created = created_at or _utcnow()
        created_s = _stamp(created)
        expires_s = _stamp(created + timedelta(seconds=ttl_seconds))
        approval_id = _id()
        conn = _connect(self.database_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM missions WHERE id=?", (mission_id,)).fetchone() is None:
                raise ValueError("mission does not exist")
            conn.execute(
                "INSERT INTO approval_requests(id,mission_id,requester_id,action,payload_sha256,estimated_cost_cents,created_at,expires_at,status) VALUES(?,?,?,?,?,?,?,?, 'PENDING')",
                (approval_id, mission_id, requester_id, action, digest, estimated_cost_cents, created_s, expires_s),
            )
            _event(conn, requester_id, "approval.requested", approval_id, "PENDING")
            conn.commit()
            return self.get(approval_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get(self, approval_id: str) -> dict | None:
        conn = _connect(self.database_path)
        try:
            row = conn.execute("SELECT id,mission_id,requester_id,action,payload_sha256,estimated_cost_cents,created_at,expires_at,status,decided_by,decided_at,consumed_at FROM approval_requests WHERE id=?", (approval_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def decide(self, approval_id: str, *, approve: bool, actor: str, now: datetime | None = None) -> dict:
        if not isinstance(approve, bool) or not actor:
            raise ValueError("approve must be boolean and actor is required")
        current = _stamp(now or _utcnow())
        conn = _connect(self.database_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM approval_requests WHERE id=?", (approval_id,)).fetchone()
            if row is None:
                raise ValueError("approval does not exist")
            if row["status"] != "PENDING":
                raise ApprovalStateError(f"approval is {row['status'].lower()}")
            if current >= row["expires_at"]:
                conn.execute("UPDATE approval_requests SET status='EXPIRED' WHERE id=? AND status='PENDING'", (approval_id,))
                _event(conn, actor, "approval.expired", approval_id, "EXPIRED")
                conn.commit()
                return self.get(approval_id)
            status = "APPROVED" if approve else "REJECTED"
            conn.execute("UPDATE approval_requests SET status=?,decided_by=?,decided_at=? WHERE id=? AND status='PENDING'", (status, actor, current, approval_id))
            _event(conn, actor, "approval.decided", approval_id, status)
            conn.commit()
            return self.get(approval_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def consume(self, approval_id: str, *, mission_id: str, requester_id: str, action: str,
                payload: Any, estimated_cost_cents: int, actor: str, now: datetime | None = None) -> dict:
        current = _stamp(now or _utcnow())
        digest = _payload_digest(payload)
        conn = _connect(self.database_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM approval_requests WHERE id=?", (approval_id,)).fetchone()
            if row is None:
                raise ValueError("approval does not exist")
            if row["status"] == "APPROVED" and current >= row["expires_at"]:
                conn.execute("UPDATE approval_requests SET status='EXPIRED' WHERE id=? AND status='APPROVED'", (approval_id,))
                _event(conn, actor, "approval.expired", approval_id, "EXPIRED")
                conn.commit()
                raise ApprovalExpired("approval has expired")
            if row["status"] != "APPROVED":
                raise ApprovalStateError(f"approval is {row['status'].lower()}")
            bound = (row["mission_id"] == mission_id and row["requester_id"] == requester_id
                     and row["action"] == action and row["payload_sha256"] == digest
                     and row["estimated_cost_cents"] == estimated_cost_cents)
            if not bound:
                raise ApprovalMismatch("action payload or context differs from the approved request")
            conn.execute("UPDATE approval_requests SET status='CONSUMED',consumed_at=? WHERE id=? AND status='APPROVED'", (current, approval_id))
            _event(conn, actor, "approval.consumed", approval_id, "CONSUMED")
            conn.commit()
            return self.get(approval_id)
        except ApprovalExpired:
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
