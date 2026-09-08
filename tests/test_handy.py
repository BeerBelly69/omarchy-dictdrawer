"""Handy's public SQLite schema, with authored data only; no app required."""

import concurrent.futures
import hashlib
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import handy
import history


class HandyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.directory = self.base / "archive"
        self.database = self.base / "Handy history #1.db"
        self.db = sqlite3.connect(self.database)
        self.addCleanup(self.db.close)
        self.db.execute("CREATE TABLE transcription_history (id INTEGER PRIMARY KEY, "
                        "timestamp INTEGER, file_name TEXT, transcription_text TEXT, post_processed_text TEXT)")
        self.db.commit()

    def insert(self, ident=1, text="A sample dictation", processed=None, stamp=1788877800):
        self.db.execute("INSERT INTO transcription_history VALUES (?, ?, ?, ?, ?)",
                        (ident, stamp, f"handy-{ident}.wav", text, processed))
        self.db.commit()

    def sync(self, **kwargs):
        return history.load_history(self.directory, handy_path=str(self.database), handy_only=True, **kwargs)

    def test_read_only_import_and_no_audio_access(self):
        self.insert(text="Original\n世界 & <notes>\n")
        before = self.database.read_bytes()
        result = self.sync()
        self.assertEqual(result["rows"][0]["text"], "Original\n世界 & <notes>\n")
        self.assertEqual(result["rows"][0]["source"], "handy")
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(list(self.base.rglob("*.wav")), [])
        target = next(self.directory.rglob("*.txt"))
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(target.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.directory / ".handy-imports.json").stat().st_mode & 0o777, 0o600)

    def test_processed_text_preferred_but_blank_falls_back(self):
        self.insert(text="raw", processed="Edited output")
        self.insert(2, text="Fallback", processed="  ")
        self.assertEqual({r["text"] for r in self.sync()["rows"]}, {"Edited output", "Fallback"})

    def test_empty_pending_row_then_transcription_and_late_postprocessing(self):
        self.insert(text="")
        self.assertEqual(self.sync()["total"], 0)
        self.db.execute("UPDATE transcription_history SET transcription_text = 'raw'")
        self.db.commit()
        first = self.sync()["rows"][0]
        self.db.execute("UPDATE transcription_history SET post_processed_text = 'Finished text'")
        self.db.commit()
        result = self.sync()
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["rows"][0]["id"], first["id"])
        self.assertEqual(result["rows"][0]["text"], "Finished text")
        self.assertEqual(len(list(self.directory.rglob("*.txt"))), 1)
        target = next(self.directory.rglob("*.txt"))
        modified = target.stat().st_mtime_ns
        self.sync()
        self.assertEqual(target.stat().st_mtime_ns, modified)

    def test_same_second_identical_text_stays_distinct(self):
        self.insert()
        self.insert(2)
        self.assertEqual(self.sync()["total"], 2)
        self.assertEqual(self.sync()["total"], 2)

    def test_handy_retention_does_not_delete_saved_copies(self):
        self.insert()
        self.sync()
        self.db.execute("DELETE FROM transcription_history")
        self.db.commit()
        self.assertEqual(self.sync()["total"], 1)

    def test_user_edits_are_preserved_when_source_changes(self):
        self.insert()
        self.sync()
        target = next(self.directory.rglob("*.txt"))
        target.write_text("My manual edit\n")
        self.db.execute("UPDATE transcription_history SET post_processed_text = 'New source text'")
        self.db.commit()
        result = self.sync()
        self.assertIn("edited", result["handyWarning"])
        self.assertEqual(result["rows"][0]["text"], "My manual edit")

    def test_committed_wal_is_read_without_changing_database(self):
        self.db.execute("PRAGMA journal_mode = WAL")
        self.insert()
        files = [self.database, Path(str(self.database) + "-wal")]
        before = [hashlib.sha256(p.read_bytes()).digest() for p in files]
        self.assertEqual(self.sync()["total"], 1)
        self.assertEqual([hashlib.sha256(p.read_bytes()).digest() for p in files], before)

    def test_missing_database_is_not_created(self):
        missing = self.base / "does-not-exist.db"
        result = history.load_history(self.directory, handy_path=str(missing), handy_only=True)
        self.assertIn("Cannot import Handy", result["handyWarning"])
        self.assertFalse(missing.exists())

    def test_corrupt_or_unsupported_database_preserves_saved_history(self):
        self.insert()
        self.sync()
        self.db.close()
        self.database.write_bytes(b"not a database")
        result = self.sync()
        self.assertEqual(result["total"], 1)
        self.assertIn("Cannot import Handy", result["handyWarning"])

    def test_schema_without_postprocessing_is_supported(self):
        self.db.execute("ALTER TABLE transcription_history DROP COLUMN post_processed_text")
        self.db.execute("INSERT INTO transcription_history VALUES (1, 1788877800, 'a.wav', 'Older Handy')")
        self.db.commit()
        self.assertEqual(self.sync()["rows"][0]["text"], "Older Handy")

    def test_unsupported_schema_warns(self):
        self.db.execute("DROP TABLE transcription_history")
        self.db.commit()
        self.assertIn("Cannot import Handy", self.sync()["handyWarning"])

    def test_invalid_rows_are_skipped_without_hiding_good_entries(self):
        self.insert()
        self.insert(2, stamp=-1)
        self.insert(3, stamp="bad timestamp")
        result = self.sync()
        self.assertEqual(result["total"], 1)
        self.assertIn("Skipped 2", result["handyWarning"])

    def test_existing_day_is_kept_after_timezone_change(self):
        self.insert()
        self.sync()
        target = next(self.directory.rglob("*.txt"))
        older_day = self.directory / "2026-09-07"
        older_day.mkdir()
        target.rename(older_day / target.name)
        self.db.execute("UPDATE transcription_history SET post_processed_text = 'Updated'")
        self.db.commit()
        self.assertEqual(self.sync()["rows"][0]["text"], "Updated")
        self.assertEqual(list(self.directory.rglob("*.txt")), [older_day / target.name])

    def test_symlinked_transcript_is_not_overwritten(self):
        self.insert()
        self.sync()
        target = next(self.directory.rglob("*.txt"))
        outside = self.base / "unrelated.txt"
        outside.write_text("Private unrelated content")
        target.unlink()
        target.symlink_to(outside)
        self.assertIn("Cannot import Handy", self.sync()["handyWarning"])
        self.assertEqual(outside.read_text(), "Private unrelated content")

    def test_busy_database_returns_warning_then_retries(self):
        self.insert()
        self.db.execute("BEGIN EXCLUSIVE")
        self.assertIn("Cannot import Handy", self.sync()["handyWarning"])
        self.db.rollback()
        self.assertEqual(self.sync()["total"], 1)

    def test_handy_only_install_needs_no_journal(self):
        self.insert()
        with patch.object(history.shutil, "which", return_value=None), patch.object(history, "read_journal", side_effect=AssertionError):
            result = history.load_history(self.directory, handy_path=str(self.database))
        self.assertEqual(result["warning"], "")
        self.assertEqual(result["total"], 1)

    def test_handy_timestamps_do_not_advance_voxtype_cursor(self):
        old = history.make_row(1700000000000000, "Voxtype sample")
        history.save_row(self.directory, old)
        self.insert(stamp=1788877800)
        with patch.object(history.shutil, "which", return_value="voxtype"), patch.object(history, "read_journal", return_value=([], "")) as journal:
            result = history.load_history(self.directory, handy_path=str(self.database))
        journal.assert_called_once_with(old["ts"])
        self.assertEqual(result["total"], 2)

    def test_no_sync_touches_neither_source_and_search_highlights_handy(self):
        self.insert(text="Straße in Handy")
        self.sync()
        with patch.object(handy, "database_path", side_effect=AssertionError), patch.object(history, "read_journal", side_effect=AssertionError):
            result = self.sync(query="STRASSE", sync=False)
        self.assertEqual(result["matched"], 1)
        self.assertIn(">Straße</span>", result["rows"][0]["highlightedText"])

    def test_custom_and_xdg_paths(self):
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(self.base)}):
            self.assertEqual(handy.database_path(), self.base / "com.pais.handy/history.db")
        self.assertEqual(handy.database_path(str(self.database)), self.database)
        with self.assertRaises(ValueError):
            handy.database_path("relative/history.db")

    def test_concurrent_monitor_imports_are_idempotent(self):
        for i in range(1, 15):
            self.insert(i)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: self.sync(), range(8)))
        self.assertTrue(all(r["total"] == 14 and not r["handyWarning"] for r in results))
        self.assertEqual(len(list(self.directory.rglob("*.txt"))), 14)

    def test_symlinked_index_is_not_read_or_replaced(self):
        self.insert()
        self.directory.mkdir()
        outside = self.base / "unrelated.json"
        outside.write_text("{}")
        (self.directory / ".handy-imports.json").symlink_to(outside)
        self.assertIn("Cannot import Handy", self.sync()["handyWarning"])
        self.assertEqual(outside.read_text(), "{}")

    def test_index_write_interruption_recovers_without_duplicates(self):
        self.insert()
        original = handy.atomic_write
        def fail_index(path, data):
            if path.name == ".handy-imports.json":
                raise OSError("interrupted")
            original(path, data)
        with patch.object(handy, "atomic_write", side_effect=fail_index):
            self.assertIn("Cannot import Handy", self.sync()["handyWarning"])
        result = self.sync()
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["handyWarning"], "")


if __name__ == "__main__":
    unittest.main()
