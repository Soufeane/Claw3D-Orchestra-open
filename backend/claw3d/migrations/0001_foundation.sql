-- Additive bootstrap: compatible with databases created by the pre-migration Store.init().
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

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
