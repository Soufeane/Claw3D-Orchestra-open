"""Additive, checksummed SQLite migrations with a pre-migration backup."""
from __future__ import annotations
import hashlib
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).with_name("migrations")
MIGRATION_PATTERN = re.compile(r"^(\d{4})_([a-z0-9_-]+)\.sql$")

class MigrationError(RuntimeError):
    """Database schema could not be safely migrated; application must not start."""

def _migration_files(directory: Path):
    found=[]
    for path in directory.iterdir():
        if path.suffix != ".sql":
            continue
        match=MIGRATION_PATTERN.fullmatch(path.name)
        if not match:
            raise MigrationError(f"invalid migration filename: {path.name}")
        found.append((int(match.group(1)), match.group(2), path))
    found.sort(key=lambda item:item[0])
    for expected,(version,_,_) in enumerate(found,1):
        if version != expected:
            raise MigrationError(f"migration sequence gap: expected {expected:04d}, found {version:04d}")
    return found

def _backup(conn: sqlite3.Connection, database_path: Path, version: int) -> Path:
    if str(database_path) == ":memory:":
        raise MigrationError("file-backed SQLite database required for pre-migration backups")
    backup_path=Path(f"{database_path}.backup-v{version:04d}-{time.time_ns()}.sqlite3")
    backup_path.parent.mkdir(parents=True,exist_ok=True)
    # Create the backup with owner-only permissions; it may contain private data.
    fd=os.open(backup_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.close(fd)
    target=sqlite3.connect(backup_path)
    source=None
    try:
        # conn holds BEGIN IMMEDIATE, preventing a writer from changing the
        # source between the snapshot and the migration. Use a separate reader:
        # backing up from the same connection while it owns a write transaction
        # can wait indefinitely in SQLite.
        source=sqlite3.connect(database_path,timeout=10)
        source.backup(target)
        target.commit()
    except Exception:
        target.close()
        if source is not None:
            source.close()
        try: backup_path.unlink()
        except OSError: pass
        raise
    else:
        target.close()
        source.close()
    return backup_path

def _execute_script(conn: sqlite3.Connection, script: str):
    pending=[]
    for line in script.splitlines():
        pending.append(line)
        statement="\n".join(pending)
        if sqlite3.complete_statement(statement):
            if statement.strip():
                conn.execute(statement)
            pending=[]
    if "\n".join(pending).strip():
        raise MigrationError("incomplete SQL statement at end of migration")

def migrate(conn: sqlite3.Connection, database_path: str | Path, directory: Path = MIGRATIONS_DIR) -> int:
    """Apply each missing migration atomically; any failure raises and blocks startup."""
    try:
        files=_migration_files(directory)
        exists=conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'").fetchone()
        current=conn.execute("SELECT COALESCE(MAX(version),0) FROM schema_version").fetchone()[0] if exists else 0
        if current > len(files):
            raise MigrationError(f"database schema version {current} is newer than this application ({len(files)})")
        rows={}
        if exists:
            rows={row[0]:row[1] for row in conn.execute("SELECT version,checksum FROM schema_version")}
        if str(database_path) == ":memory:" and current < len(files):
            raise MigrationError("file-backed SQLite database required for pre-migration backups")
        for version,name,path in files:
            raw=path.read_bytes()
            checksum=hashlib.sha256(raw).hexdigest()
            if version <= current:
                if rows.get(version) != checksum:
                    raise MigrationError(f"checksum mismatch for applied migration {version:04d}_{name}")
                continue
            script=raw.decode("utf-8")
            try:
                conn.execute("BEGIN IMMEDIATE")
                # Acquire the write reservation before taking the snapshot, so
                # concurrent writers cannot slip between backup and migration.
                _backup(conn,Path(database_path),version)
                _execute_script(conn,script)
                applied_at=datetime.now(timezone.utc).isoformat(timespec="seconds")
                conn.execute("INSERT INTO schema_version(version,name,checksum,applied_at) VALUES(?,?,?,?)",(version,name,checksum,applied_at))
                conn.commit()
            except Exception as exc:
                conn.rollback()
                raise MigrationError(f"migration {version:04d}_{name} failed; application startup aborted") from exc
            current=version
        return current
    except MigrationError:
        raise
    except Exception as exc:
        raise MigrationError("unable to inspect or apply database migrations; application startup aborted") from exc
