-- Additive control primitives for atomic budgets and one-shot approvals.
CREATE TABLE IF NOT EXISTS cost_reservations (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    mission_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    department TEXT NOT NULL,
    estimated_cents INTEGER NOT NULL CHECK (estimated_cents >= 0),
    reserved_cents INTEGER NOT NULL CHECK (reserved_cents >= 0),
    actual_cents INTEGER CHECK (actual_cents IS NULL OR actual_cents >= 0),
    cost_source TEXT CHECK (cost_source IS NULL OR cost_source IN ('FIXTURE_SIMULATED','OPERATOR_RECORDED')),
    status TEXT NOT NULL CHECK (status IN ('RESERVED','CONSUMED','RELEASED')),
    created_at TEXT NOT NULL,
    finalized_at TEXT,
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);
CREATE INDEX IF NOT EXISTS idx_cost_reservations_status_created
    ON cost_reservations(status, created_at);
CREATE INDEX IF NOT EXISTS idx_cost_reservations_mission_status
    ON cost_reservations(mission_id, status);
CREATE INDEX IF NOT EXISTS idx_cost_reservations_agent_status
    ON cost_reservations(agent_id, status);

CREATE TABLE IF NOT EXISTS approval_requests (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL,
    requester_id TEXT NOT NULL,
    action TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    estimated_cost_cents INTEGER NOT NULL CHECK (estimated_cost_cents >= 0),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING','APPROVED','REJECTED','EXPIRED','CONSUMED')),
    decided_by TEXT,
    decided_at TEXT,
    consumed_at TEXT,
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);
CREATE INDEX IF NOT EXISTS idx_approval_requests_status_expiry
    ON approval_requests(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_approval_requests_mission
    ON approval_requests(mission_id, created_at);

INSERT OR IGNORE INTO settings(key,value) VALUES ('cost_circuit_breaker','0');
