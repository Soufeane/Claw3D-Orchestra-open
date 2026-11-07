import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.claw3d.core import Store
from backend.claw3d import migrations
from backend.claw3d.migrations import MigrationError, migrate

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.db_path=self.root/"case.sqlite3"
    def tearDown(self): self.tmp.cleanup()
    def test_fresh_database_gets_version_and_backup(self):
        store=Store(str(self.db_path))
        with store.connect() as conn:
            self.assertEqual(conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0],1)
            self.assertIsNotNone(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='missions'").fetchone())
        backups=list(self.root.glob("case.sqlite3.backup-v0001-*.sqlite3"))
        self.assertEqual(len(backups),1)
        self.assertEqual(backups[0].stat().st_mode & 0o777,0o600)
        with sqlite3.connect(backups[0]) as backup:
            self.assertIsNone(backup.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'").fetchone())
    def test_legacy_database_data_is_preserved_and_backed_up_before_migration(self):
        # This fixture represents a database produced by the old inline CREATE TABLE code.
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE missions (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL, priority TEXT NOT NULL, department TEXT NOT NULL, owner TEXT NOT NULL, status TEXT NOT NULL, budget_cents INTEGER NOT NULL, created_at TEXT NOT NULL, result TEXT)")
            conn.execute("INSERT INTO missions VALUES ('mis_keep','Keep this row','legacy data','NORMAL','general','director','PENDING',0,'2026-01-01T00:00:00+00:00',NULL)")
        store=Store(str(self.db_path))
        with store.connect() as conn:
            row=conn.execute("SELECT id,title,description FROM missions WHERE id='mis_keep'").fetchone()
            self.assertEqual(tuple(row),("mis_keep","Keep this row","legacy data"))
            self.assertEqual(conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0],1)
        backups=list(self.root.glob("case.sqlite3.backup-v0001-*.sqlite3"))
        self.assertEqual(len(backups),1)
        with sqlite3.connect(backups[0]) as backup:
            self.assertEqual(backup.execute("SELECT title FROM missions WHERE id='mis_keep'").fetchone()[0],"Keep this row")
            self.assertIsNone(backup.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'").fetchone())
        restored=self.root/"restored.sqlite3"
        restored.write_bytes(backups[0].read_bytes())
        with sqlite3.connect(restored) as recovered:
            self.assertEqual(recovered.execute("SELECT title FROM missions WHERE id='mis_keep'").fetchone()[0],"Keep this row")
    def test_migration_failure_rolls_back_and_startup_fails(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE preserved (value TEXT NOT NULL)")
            conn.execute("INSERT INTO preserved VALUES ('original')")
        migration_dir=self.root/"migrations"
        migration_dir.mkdir()
        (migration_dir/"0001_broken.sql").write_text("CREATE TABLE partial_change (id INTEGER);\nTHIS IS NOT VALID SQL;\n",encoding="utf-8")
        with self.assertRaisesRegex(MigrationError,"startup aborted"):
            Store(str(self.db_path),migrations_dir=migration_dir)
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT value FROM preserved").fetchone()[0],"original")
            self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='partial_change'").fetchone())
        self.assertEqual(len(list(self.root.glob("case.sqlite3.backup-v0001-*.sqlite3"))),1)
    def test_applied_migration_checksum_must_not_change(self):
        Store(str(self.db_path))
        migration_dir=self.root/"different"
        migration_dir.mkdir()
        (migration_dir/"0001_foundation.sql").write_text("-- changed",encoding="utf-8")
        conn=sqlite3.connect(self.db_path)
        try:
            with self.assertRaisesRegex(MigrationError,"checksum mismatch"):
                migrate(conn,self.db_path,migration_dir)
        finally:
            conn.close()

    def test_writer_cannot_change_database_between_backup_and_migration(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE legacy (value TEXT NOT NULL)")
            conn.execute("INSERT INTO legacy VALUES ('before')")
        migration_dir=self.root/"concurrent_migrations"
        migration_dir.mkdir()
        migration=("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, applied_at TEXT NOT NULL);\n"
                   "CREATE TABLE added (value TEXT NOT NULL);\n")
        (migration_dir/"0001_add_table.sql").write_text(migration,encoding="utf-8")
        blocked=[]
        original_backup=migrations._backup
        def backup_then_try_write(conn,path,version):
            result=original_backup(conn,path,version)
            writer=sqlite3.connect(self.db_path,timeout=0.05)
            try:
                try:
                    writer.execute("INSERT INTO legacy VALUES ('racing-write')")
                except sqlite3.OperationalError as exc:
                    blocked.append("locked" in str(exc).lower())
                else:
                    writer.commit()
            finally:
                writer.close()
            return result
        with patch.object(migrations,"_backup",side_effect=backup_then_try_write):
            conn=sqlite3.connect(self.db_path,timeout=2)
            try:
                self.assertEqual(migrate(conn,self.db_path,migration_dir),1)
            finally:
                conn.close()
        self.assertEqual(blocked,[True])
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("SELECT value FROM legacy").fetchall(),[("before",)])

    def test_in_memory_database_is_explicitly_rejected_without_losing_transaction_state(self):
        conn=sqlite3.connect(":memory:")
        try:
            with self.assertRaisesRegex(MigrationError,"file-backed SQLite database required"):
                migrate(conn,":memory:")
            self.assertFalse(conn.in_transaction)
        finally:
            conn.close()

if __name__=="__main__": unittest.main()
