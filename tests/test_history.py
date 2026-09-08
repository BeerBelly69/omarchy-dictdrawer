import concurrent.futures
import html
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import history


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "history"

    def row(self, micros=1_700_000_000_123456, text="A test dictation"):
        return history.make_row(micros, text)

    def test_ansi_and_byte_array_journal(self):
        message = '\x1b[32m INFO\x1b[0m Transcribed: "Hello, 世界"'
        for value in (message, list(message.encode())):
            row = history.parse_journal(json.dumps({"MESSAGE": value, "__REALTIME_TIMESTAMP": "1700000000123456"}))
            self.assertEqual(row["text"], "Hello, 世界")
            self.assertAlmostEqual(row["ts"], 1700000000.123456)

    def test_malformed_and_non_transcription_records(self):
        for line in ("broken", "null", "[]", "{}", '{"MESSAGE":42}', '{"MESSAGE":[999]}', '{"MESSAGE":"INFO Transcribed: hi"}'):
            self.assertIsNone(history.parse_journal(line))

    def test_archive_survives_empty_journal_and_searches_beyond_limit(self):
        rows = [self.row(1700000000000000 + i, "Old needle" if i == 0 else f"Entry {i}") for i in range(30)]
        for row in rows:
            history.save_row(self.directory, row)
        with patch.object(history, "read_journal", return_value=([], "")):
            result = history.load_history(self.directory, "OLD needle", limit=5)
        self.assertEqual(result["total"], 30)
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["rows"][0]["text"], "Old needle")

    def test_same_second_and_same_timestamp_do_not_collide(self):
        rows = [self.row(1700000000123456, "one"), self.row(1700000000123457, "two"), self.row(1700000000123456, "three")]
        for row in rows:
            history.save_row(self.directory, row)
        saved, _, _ = history.read_archive(self.directory)
        self.assertEqual(len(saved), 3)

    def test_legacy_migration_deduplicates_only_legacy(self):
        self.directory.mkdir()
        legacy_path = self.directory / "2023-11-14_221320.txt"
        legacy_path.write_text("A test dictation\n")
        _, legacy, _ = history.read_archive(self.directory)
        micros = round(legacy[0]["ts"] * 1000000)
        journal = [self.row(micros + 1), self.row(micros + 2)]
        merged = history.merge_rows([], legacy, journal)
        self.assertEqual(len(merged), 2)
        self.assertEqual(len(history.merge_rows([], legacy, [])), 1)

    def test_writes_are_private_atomic_and_idempotent(self):
        row = self.row(text="第一行\n\nSecond line\n")
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(lambda _: history.save_row(self.directory, row), range(12)))
        files = list(self.directory.rglob("*.txt"))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)
        self.assertEqual(history.read_archive(self.directory)[0][0]["text"], row["text"])

    def test_user_edited_archive_is_not_overwritten(self):
        row = self.row()
        history.save_row(self.directory, row)
        path = history.day_directory(self.directory, row["ts"]) / (row["id"] + ".txt")
        path.write_text("An edited excerpt\n")
        history.save_row(self.directory, row)
        saved, _, _ = history.read_archive(self.directory)
        self.assertEqual(history.merge_rows(saved, [], [row])[0]["text"], "An edited excerpt")

    def test_unicode_multiterm_literal_search(self):
        history.save_row(self.directory, self.row(text="Straße café [notes]"))
        result = history.load_history(self.directory, "STRASSE [notes]", sync=False)
        self.assertEqual(result["matched"], 1)
        self.assertEqual(history.load_history(self.directory, "[.*]", sync=False)["matched"], 0)

    def highlighted_words(self, markup):
        return [html.unescape(word) for word in re.findall(r'<span[^>]*>(.*?)</span>', markup)]

    def test_highlights_all_literal_case_insensitive_matches(self):
        result = history.search_display("Notes [a.*] NOTES and notes", ["notes", "[a.*]"])
        self.assertEqual(self.highlighted_words(result["highlightedText"]), ["Notes", "[a.*]", "NOTES", "notes"])

    def test_highlights_unicode_expansion_and_emoji_without_offset_errors(self):
        result = history.search_display("🎙 Straße café STRASSE", ["strasse", "café"])
        self.assertEqual(self.highlighted_words(result["highlightedText"]), ["Straße", "café", "STRASSE"])
        self.assertTrue(result["highlightedText"].startswith("🎙 "))

    def test_highlight_merges_overlapping_matches(self):
        result = history.search_display("banana", ["ana", "nan", "ana"])
        self.assertEqual(self.highlighted_words(result["highlightedText"]), ["anana"])

    def test_highlight_escapes_transcript_html_even_inside_matches(self):
        source = '<img src="https://example.com/private"> & <script>hello</script>'
        result = history.search_display(source, ["<img", "hello"])
        self.assertNotIn("<img", result["highlightedText"])
        self.assertNotIn("<script>", result["highlightedText"])
        plain = html.unescape(re.sub(r'</?span[^>]*>', '', result["highlightedText"]))
        self.assertEqual(plain, source)

    def test_preview_reveals_buried_match_and_expanded_text_keeps_every_match(self):
        source = "Lead-in words. " * 100 + "Needle in context. " + "Later words. " * 100 + "NEEDLE"
        result = history.search_display(source, ["needle"])
        preview = result["highlightedPreview"]
        self.assertTrue(preview.startswith("… "))
        self.assertTrue(preview.endswith(" …"))
        self.assertEqual(self.highlighted_words(preview), ["Needle"])
        self.assertLess(len(re.sub(r'<[^>]*>', '', preview)), 250)
        self.assertEqual(self.highlighted_words(result["highlightedText"]), ["Needle", "NEEDLE"])

    def test_preview_flattens_newlines_without_joining_words(self):
        result = history.search_display("first\nneedle\nlast", ["needle"])
        self.assertIn("first ", result["highlightedPreview"])
        self.assertIn(" last", result["highlightedPreview"])
        self.assertEqual(result["highlightedText"].count("<br>"), 2)

    def test_search_formatting_never_changes_copy_text_or_archive(self):
        source = "Original\nStraße & <notes>\n"
        history.save_row(self.directory, self.row(text=source))
        row = history.load_history(self.directory, "STRASSE", sync=False)["rows"][0]
        self.assertEqual(row["text"], source)
        self.assertEqual(self.highlighted_words(row["highlightedText"]), ["Straße"])
        unfiltered = history.load_history(self.directory, "  ", sync=False)["rows"][0]
        self.assertNotIn("highlightedText", unfiltered)
        self.assertEqual(unfiltered["text"], source)

    def test_journal_failure_keeps_saved_history(self):
        history.save_row(self.directory, self.row())
        with patch.object(history, "read_journal", return_value=([], "Journal unavailable")):
            result = history.load_history(self.directory)
        self.assertEqual(len(result["rows"]), 1)
        self.assertIn("Journal unavailable", result["warning"])

    def test_journal_missing_timeout_and_exit_failure(self):
        for failure in (FileNotFoundError(), subprocess.TimeoutExpired("journalctl", 8)):
            with patch.object(subprocess, "run", side_effect=failure):
                rows, warning = history.read_journal()
            self.assertEqual(rows, [])
            self.assertTrue(warning)
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "denied")):
            self.assertTrue(history.read_journal()[1])

    def test_unreadable_file_does_not_hide_other_rows(self):
        history.save_row(self.directory, self.row())
        (self.directory / "1700000000000000-aaaaaaaaaaaaaaaaaaaa.txt").write_bytes(b"\xff")
        saved, _, warning = history.read_archive(self.directory)
        self.assertEqual(len(saved), 1)
        self.assertIn("1 unreadable", warning)

    def test_symlinks_are_not_read(self):
        self.directory.mkdir()
        source = Path(self.temp.name) / "private.txt"
        source.write_text("Do not read")
        (self.directory / "1700000000000000-aaaaaaaaaaaaaaaaaaaa.txt").symlink_to(source)
        self.assertEqual(history.read_archive(self.directory)[0], [])

    def test_no_sync_never_calls_journal(self):
        with patch.object(history, "read_journal", side_effect=AssertionError("unexpected journal access")):
            self.assertEqual(history.load_history(self.directory, sync=False)["rows"], [])

    def test_failed_save_does_not_advance_past_unsaved_entries(self):
        rows = [self.row(1700000000000000 + i, str(i)) for i in range(3)]
        original = history.save_row
        def fail_second(directory, row):
            if row["text"] == "1":
                raise OSError("disk full")
            original(directory, row)
        with patch.object(history, "read_journal", return_value=(list(reversed(rows)), "")), patch.object(history, "save_row", side_effect=fail_second):
            result = history.load_history(self.directory)
        self.assertIn("Cannot save", result["warning"])
        self.assertEqual(len(result["rows"]), 3)
        self.assertEqual(history.read_archive(self.directory)[0][0]["text"], "0")

    def test_xdg_data_home(self):
        with patch.dict(os.environ, {"XDG_DATA_HOME": self.temp.name}):
            self.assertEqual(history.archive_dir(), Path(self.temp.name) / "voxtype/history")

    def test_new_files_use_private_local_date_folders(self):
        stamp = datetime(2026, 9, 8, 23, 59, 59).timestamp()
        row = self.row(round(stamp * 1000000))
        history.save_row(self.directory, row)
        target = self.directory / "2026-09-08" / (row["id"] + ".txt")
        self.assertEqual(target.read_text(), row["text"] + "\n")
        self.assertEqual(target.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_date_folder_search_covers_every_day_beyond_display_limit(self):
        for day in range(1, 26):
            stamp = datetime(2026, 8, day, 12).timestamp()
            history.save_row(self.directory, self.row(round(stamp * 1000000), f"Day {day} unique{day:02}"))
        recent = history.load_history(self.directory, sync=False)
        self.assertEqual(len(recent["rows"]), 20)
        self.assertEqual(recent["total"], 25)
        self.assertEqual(recent["rows"][0]["text"], "Day 25 unique25")
        self.assertEqual(history.load_history(self.directory, "unique01", sync=False)["matched"], 1)
        self.assertEqual(len(history.load_history(self.directory, limit=5, sync=False)["rows"]), 5)

    def test_flat_migration_preserves_bytes_identity_edits_and_permissions(self):
        self.directory.mkdir()
        row = self.row()
        source = self.directory / (row["id"] + ".txt")
        original = b"An edited excerpt\r\nwith exact bytes\n\n"
        source.write_bytes(original)
        source.chmod(0o600)
        legacy = self.directory / "2026-09-07_123456.txt"
        legacy.write_text("An older dictation\n")
        with patch.object(history, "read_journal", return_value=([row], "")):
            result = history.load_history(self.directory)
        target = history.day_directory(self.directory, row["ts"]) / source.name
        self.assertFalse(source.exists())
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertTrue((self.directory / "2026-09-07" / legacy.name).exists())
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(next(r for r in result["rows"] if r["id"] == row["id"])["text"], "An edited excerpt\nwith exact bytes\n")
        self.assertEqual(history.archive_snapshot(self.directory, True)[2], "")

    def test_migration_conflict_keeps_both_files_and_warns(self):
        row = self.row()
        history.save_row(self.directory, row)
        source = self.directory / (row["id"] + ".txt")
        source.write_text("A distinct edited flat copy\n")
        saved, _, warning = history.archive_snapshot(self.directory, True)
        self.assertIn("originals were kept", warning)
        self.assertTrue(source.exists())
        target = history.day_directory(self.directory, row["ts"]) / source.name
        self.assertEqual(target.read_text(), row["text"] + "\n")
        self.assertEqual(history.merge_rows(saved, [], [])[0]["text"], "A distinct edited flat copy")

    def test_interrupted_migration_recovers_idempotently(self):
        self.directory.mkdir()
        row = self.row()
        source = self.directory / (row["id"] + ".txt")
        source.write_text(row["text"] + "\n")
        original_unlink = Path.unlink
        def fail_source(path, *args, **kwargs):
            if path == source:
                raise OSError("interrupted before unlink")
            return original_unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", fail_source):
            self.assertIn("originals were kept", history.archive_snapshot(self.directory, True)[2])
        self.assertTrue(source.exists())
        self.assertEqual(history.archive_snapshot(self.directory, True)[2], "")
        self.assertFalse(source.exists())
        self.assertEqual(len(history.read_archive(self.directory)[0]), 1)

    def test_concurrent_migration_and_search_keep_complete_history(self):
        self.directory.mkdir()
        for i in range(40):
            row = self.row(1700000000000000 + i, f"entry {i}")
            (self.directory / (row["id"] + ".txt")).write_text(row["text"] + "\n")
        def snapshot(i):
            return history.archive_snapshot(self.directory, organize=i % 2 == 0)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            snapshots = list(executor.map(snapshot, range(20)))
        for saved, legacy, warning in snapshots:
            self.assertEqual(len(saved), 40)
            self.assertEqual(legacy, [])
            self.assertEqual(warning, "")

    def test_symlinked_date_folder_is_neither_read_nor_written(self):
        self.directory.mkdir()
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        row = self.row(round(datetime(2026, 9, 8, 12).timestamp() * 1000000))
        (self.directory / "2026-09-08").symlink_to(outside, target_is_directory=True)
        (outside / (row["id"] + ".txt")).write_text("Private unrelated data")
        self.assertEqual(history.read_archive(self.directory)[0], [])
        with self.assertRaises(OSError):
            history.save_row(self.directory, row)
        flat = self.directory / (row["id"] + ".txt")
        flat.write_text(row["text"] + "\n")
        self.assertIn("originals were kept", history.archive_snapshot(self.directory, True)[2])
        self.assertTrue(flat.exists())

    def test_search_does_not_migrate_or_touch_unrelated_files(self):
        self.directory.mkdir()
        row = self.row()
        flat = self.directory / (row["id"] + ".txt")
        flat.write_text(row["text"] + "\n")
        unrelated = self.directory / "notes.txt"
        unrelated.write_text("Keep me here")
        history.load_history(self.directory, sync=False)
        self.assertTrue(flat.exists())
        history.archive_snapshot(self.directory, True)
        self.assertEqual(unrelated.read_text(), "Keep me here")


if __name__ == "__main__":
    unittest.main()
