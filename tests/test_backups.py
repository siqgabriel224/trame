"""Regressões de backup: versões restauráveis, falhas e retenção."""

import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import backups


class BackupHistory(unittest.TestCase):
    def test_transient_windows_file_lock_is_retried(self):
        source = Path(self.temp.name) / "source.tmp"
        target = Path(self.temp.name) / "target.json"
        source.write_text("new", encoding="utf-8")
        target.write_text("old", encoding="utf-8")
        blocked = PermissionError("Arquivo ocupado")
        blocked.winerror = 32
        original = Path.replace
        attempts = []

        def replace(path, destination):
            attempts.append(path)
            if len(attempts) == 1:
                raise blocked
            return original(path, destination)

        with patch.object(Path, "replace", replace), patch.object(backups.time, "sleep"):
            backups._replace(source, target)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(target.read_text(encoding="utf-8"), "new")

    def test_persistent_windows_file_lock_is_reported(self):
        blocked = PermissionError("Arquivo ocupado")
        blocked.winerror = 5
        with (
            patch.object(Path, "replace", side_effect=blocked) as replace,
            patch.object(backups.time, "sleep"),
            self.assertRaises(PermissionError),
        ):
            backups._replace(Path("source"), Path("target"))
        self.assertEqual(replace.call_count, 5)

    def test_status_reads_can_run_while_snapshots_are_published(self):
        backups.create(self.runtime, self.now)
        stop = threading.Event()

        def read_status():
            errors = []
            while not stop.is_set():
                state = backups.status(self.runtime)
                if state["lastError"]:
                    errors.append(state["lastError"])
            return errors

        with ThreadPoolExecutor(max_workers=1) as pool:
            reader = pool.submit(read_status)
            try:
                for index in range(1, 4):
                    state = backups.create(self.runtime, self.now + timedelta(minutes=15 * index))
                    self.assertIsNone(state["lastError"])
            finally:
                stop.set()
            self.assertEqual(reader.result(timeout=2), [])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "business.sqlite3"
        self.runtime = SimpleNamespace(DB=self.db, connect=lambda: sqlite3.connect(self.db))
        with closing(self.runtime.connect()) as con, con:
            con.execute("CREATE TABLE orders (value TEXT)")
            con.execute("INSERT INTO orders VALUES ('original')")
        self.now = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)
        self.env = patch.dict("os.environ", {"TRAME_BACKUP_DIR": ""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_interval_and_restore_later_changes(self):
        backups.create(self.runtime, self.now)
        with closing(self.runtime.connect()) as con, con:
            con.execute("INSERT INTO orders VALUES ('second')")
        backups.create(self.runtime, self.now + timedelta(minutes=1))
        root = backups.folder(self.runtime)
        self.assertEqual(len(list(root.glob("trame-snapshot-*"))), 1)
        backups.create(self.runtime, self.now + timedelta(minutes=15))
        snapshots = sorted(root.glob("trame-snapshot-*"))
        self.assertEqual(len(snapshots), 2)
        # Restore the snapshot into another DB using SQLite's backup API.
        with (
            closing(sqlite3.connect(snapshots[-1])) as source,
            closing(sqlite3.connect(Path(self.temp.name) / "restored.sqlite3")) as restored,
        ):
            source.backup(restored)
            self.assertEqual(restored.execute("SELECT count(*) FROM orders").fetchone()[0], 2)
            self.assertEqual(restored.execute("PRAGMA quick_check").fetchone()[0], "ok")
        self.assertEqual(
            backups.status(self.runtime)["lastSuccess"],
            (self.now + timedelta(minutes=15)).isoformat(),
        )

    def test_failed_copy_preserves_previous_snapshot_and_reports_error(self):
        backups.create(self.runtime, self.now)
        previous = backups.status(self.runtime)["lastSuccess"]
        with patch.object(backups, "_snapshot", side_effect=OSError("disk full")):
            backups.create(self.runtime, self.now + timedelta(minutes=15))
        state = backups.status(self.runtime)
        self.assertEqual(state["lastSuccess"], previous)
        self.assertTrue(state["lastError"])
        self.assertEqual(len(list(backups.folder(self.runtime).glob("trame-snapshot-*"))), 1)
        backups.create(self.runtime, self.now + timedelta(minutes=16))
        self.assertIsNone(backups.status(self.runtime)["lastError"])

    def test_retention_only_removes_managed_files_after_success(self):
        root = backups.folder(self.runtime)
        root.mkdir()
        unrelated = root / "minha-copia.sqlite3"
        unrelated.write_bytes(b"preserve")
        with (
            patch.object(backups, "SNAPSHOTS_TO_KEEP", 2),
            patch.object(backups, "DAILY_TO_KEEP", 2),
        ):
            for day in range(4):
                backups.create(self.runtime, self.now + timedelta(days=day))
        self.assertEqual(len(list(root.glob("trame-snapshot-*"))), 2)
        self.assertEqual(len(list(root.glob("trame-????-??-??.sqlite3"))), 2)
        self.assertEqual(unrelated.read_bytes(), b"preserve")

    def test_unavailable_destination_is_visible_without_losing_save(self):
        blocked = Path(self.temp.name) / "not-a-directory"
        blocked.write_text("blocked")
        with patch.dict("os.environ", {"TRAME_BACKUP_DIR": str(blocked)}):
            result = backups.create(self.runtime, self.now)
            self.assertTrue(result["lastError"])
            self.assertTrue(backups.status(self.runtime)["lastError"])
