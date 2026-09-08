#!/usr/bin/env python3
"""Local Voxtype and Handy history. Stdlib only; stdout is the JSON protocol."""

import argparse
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import sqlite3
from datetime import datetime
import handy

ANSI = re.compile(r"\x1b\[[0-9;]*m")
MODERN = re.compile(r"^(\d+)-([a-f0-9]{20})\.txt$")
HANDY = re.compile(r"^handy-(\d+)-([a-f0-9]{20})\.txt$")
LEGACY = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}\.txt$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
JOURNAL_LIMIT = 50000


def archive_dir():
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home) if data_home and Path(data_home).is_absolute() else Path.home() / ".local/share"
    return base / "voxtype/history"


def make_row(micros, text):
    micros = int(micros)
    digest = hashlib.sha256(f"{micros}\0{text}".encode()).hexdigest()[:20]
    return {"id": f"{micros}-{digest}", "ts": micros / 1_000_000, "text": text}


def parse_journal(line):
    try:
        rec = json.loads(line)
        message = rec.get("MESSAGE", "")
        if isinstance(message, list):
            message = bytes(message).decode("utf-8", "replace")
        if not isinstance(message, str):
            return None
        message = ANSI.sub("", message)
        marker = "INFO Transcribed:"
        if marker not in message:
            return None
        text = message.split(marker, 1)[1].strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        if text:
            return make_row(rec["__REALTIME_TIMESTAMP"], text)
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
        pass
    return None


def read_journal(since=None):
    command = ["journalctl", "--user", "-u", "voxtype.service", "-o", "json", "--no-pager", "-r", "-n", str(JOURNAL_LIMIT)]
    if since is not None:
        command += ["--since", f"@{max(0, since - 1):.6f}"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=8, check=False)
    except FileNotFoundError:
        return [], "journalctl is missing. Install systemd to read Voxtype history."
    except subprocess.TimeoutExpired:
        return [], "Reading the journal timed out. Showing saved history; try Refresh."
    except OSError:
        return [], "Cannot read the user journal. Showing saved history."
    if result.returncode:
        return [], "Cannot read the user journal. Check journalctl --user -u voxtype.service."
    rows = [row for line in result.stdout.splitlines() if (row := parse_journal(line))]
    warning = "" if not result.stderr.strip() else "The journal reported a warning. Some history may be unavailable."
    if len(result.stdout.splitlines()) >= JOURNAL_LIMIT:
        warning = f"Journal import is limited to the newest {JOURNAL_LIMIT:,} log records. Saved history is still searchable."
    return rows, warning


def read_archive(directory):
    rows, legacy, unreadable = [], [], 0
    if not directory.exists():
        return rows, legacy, ""
    # Date folders first, then flat compatibility files. An unresolved flat
    # conflict wins in merge_rows; neither copy is overwritten or discarded.
    flat = list(directory.iterdir())
    paths = []
    for folder in sorted(flat):
        if folder.is_symlink() or not DAY.fullmatch(folder.name) or not folder.is_dir():
            continue
        try:
            paths.extend(sorted(folder.iterdir()))
        except OSError:
            unreadable += 1
    paths.extend(sorted(flat))
    for path in paths:
        handy_match = HANDY.fullmatch(path.name)
        modern = MODERN.fullmatch(path.name) or handy_match
        old = LEGACY.fullmatch(path.name)
        if path.is_symlink() or not (modern or old) or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8").removesuffix("\n")
            if not text:
                continue
            if modern:
                row = make_row(modern[1], text)
                # Stable identity is the filename even if someone edits the text.
                row["id"] = path.stem
                if handy_match:
                    row["source"] = "handy"
                rows.append(row)
            else:
                stamp = datetime.strptime(path.stem, "%Y-%m-%d_%H%M%S").timestamp()
                row = make_row(round(stamp * 1_000_000), text)
                row["id"] = "legacy-" + path.stem
                legacy.append(row)
        except (OSError, ValueError, OverflowError):
            unreadable += 1
    warning = f"Skipped {unreadable} unreadable archive file(s) or folder(s)." if unreadable else ""
    return rows, legacy, warning


def day_directory(directory, stamp):
    day = directory / datetime.fromtimestamp(stamp).strftime("%Y-%m-%d")
    if day.is_symlink():
        raise OSError("Refusing a symlinked date folder")
    day.mkdir(mode=0o700, parents=True, exist_ok=True)
    return day


def migrate_flat_archive(directory):
    """Move known flat files into date folders, without replacing any file.

    Called under the snapshot lock. Linking before unlinking also leaves a
    complete readable copy after an interruption; the next pass is idempotent.
    """
    failed = 0
    for source in sorted(directory.iterdir()):
        modern = MODERN.fullmatch(source.name)
        legacy = LEGACY.fullmatch(source.name)
        if source.is_symlink() or not (modern or legacy) or not source.is_file():
            continue
        try:
            stamp = int(modern[1]) / 1_000_000 if modern else datetime.strptime(source.stem, "%Y-%m-%d_%H%M%S").timestamp()
            destination = day_directory(directory, stamp) / source.name
            if destination.is_symlink():
                raise OSError("Refusing a symlinked transcript")
            try:
                os.link(source, destination, follow_symlinks=False)
            except FileExistsError:
                if source.read_bytes() != destination.read_bytes():
                    failed += 1
                    continue
            source.unlink()
        except (OSError, ValueError, OverflowError):
            failed += 1
    return f"Could not organize {failed} flat file(s); originals were kept. Check date-folder permissions or conflicting copies." if failed else ""


def archive_snapshot(directory, organize):
    if not directory.exists():
        return [], [], ""
    # Serialize reorganization with reads from other monitor instances. Journal
    # access is outside this short lock, so typing never waits for journalctl.
    try:
        fd = os.open(directory / ".dictdrawer.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError:
        saved, legacy, warning = read_archive(directory)
        return saved, legacy, " ".join(filter(None, [warning, "Cannot lock the history folder; showing saved files without reorganizing them."]))
    with os.fdopen(fd, "r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX if organize else fcntl.LOCK_SH)
        migration_warning = migrate_flat_archive(directory) if organize else ""
        saved, legacy, warning = read_archive(directory)
        return saved, legacy, " ".join(filter(None, [migration_warning, warning]))


def save_row(directory, row):
    """Publish a complete file without replacing an existing one, across monitors."""
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    day = day_directory(directory, row["ts"])
    target = day / (row["id"] + ".txt")
    if target.is_symlink():
        raise OSError("Refusing a symlinked transcript")
    if target.exists():
        return
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=day)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(row["text"] + "\n")
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            pass
    finally:
        os.unlink(temporary)


def merge_rows(saved, legacy, journal):
    combined = {row["id"]: row for row in journal}
    combined.update({row["id"]: row for row in saved})
    # Old filenames only have second precision. Suppress their duplicate of
    # an exact journal record, but keep distinct same-second journal entries.
    exact = {(int(row["ts"]), row["text"]) for row in combined.values()}
    for row in legacy:
        if (int(row["ts"]), row["text"]) not in exact:
            combined[row["id"]] = row
    return sorted(combined.values(), key=lambda row: (row["ts"], row["id"]), reverse=True)


def search_display(text, tokens):
    """Highlight literal casefold matches without interpreting transcript HTML."""
    folded = text.casefold()
    # Case folding can expand characters (ß -> ss). Map back to the original
    # characters, so highlighting uses exactly the same rules as filtering.
    positions = [i for i, char in enumerate(text) for _ in char.casefold()]
    ranges = []
    for token in set(tokens):
        if not token:
            continue
        start = folded.find(token)
        while start != -1:
            ranges.append((positions[start], positions[start + len(token) - 1] + 1))
            start = folded.find(token, start + 1)
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))

    def render(begin, finish, preview=False):
        def escape(value):
            if preview:
                value = value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
            return html.escape(value).replace("\n", "<br>")
        parts = ["… " if begin else ""]
        cursor = begin
        for start, end in merged:
            start, end = max(begin, start), min(finish, end)
            if start >= end:
                continue
            parts.append(escape(text[cursor:start]))
            parts.append('<span style="background-color:#f4cf65;color:#241d0f">'
                         + escape(text[start:end]) + '</span>')
            cursor = end
        parts.append(escape(text[cursor:finish]))
        if finish < len(text):
            parts.append(" …")
        return "".join(parts)

    # Put a buried match in view, with a little lead-in and no cut-off words.
    first_start, first_end = merged[0] if merged else (0, 0)
    begin = max(0, first_start - 55)
    while 0 < begin < first_start and not text[begin - 1].isspace():
        begin += 1
    finish = min(len(text), max(begin + 240, first_end))
    while finish < len(text) and finish > first_end and not text[finish].isspace():
        finish -= 1
    return {"highlightedText": render(0, len(text)),
            "highlightedPreview": render(begin, finish, preview=True)}


def load_history(directory, query="", limit=20, sync=True, handy_path="", handy_only=False):
    warnings = []
    handy_warning = ""
    handy_available = False
    if sync:
        try:
            db_path = handy.database_path(handy_path)
            handy_available = db_path.is_file()
            if handy_available or handy_path:
                handy_warning = handy.sync_history(directory, db_path, day_directory)
        except (OSError, ValueError, sqlite3.Error):
            handy_available = True  # A broken Handy source is not a missing Voxtype install.
            handy_warning = "Cannot import Handy history. Check its database path, permissions, and version; saved excerpts remain available."
    saved, legacy, warning = archive_snapshot(directory, organize=sync)
    if warning:
        warnings.append(warning)
    journal = []
    if sync and not handy_only:
        # Include the newest second again, so simultaneous transcripts aren't
        # missed. First import is bounded; the archive itself has no row cap.
        since = max((row["ts"] for row in saved if row.get("source") != "handy"), default=None)
        # Handy-only installations do not need Voxtype or systemd journal access.
        journal, warning = read_journal(since) if shutil.which("voxtype") or not handy_available else ([], "")
        if warning:
            warnings.append(warning)
        if not shutil.which("voxtype") and not handy_available:
            warnings.append("No dictation source detected. Install Voxtype or set Handy's history database path. Saved history remains available.")
        try:
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            saved_ids = {row["id"] for row in saved}
            for row in sorted(journal, key=lambda row: row["ts"]):
                if row["id"] not in saved_ids:
                    save_row(directory, row)
        except OSError:
            warnings.append("Cannot save transcripts. Check permissions and free space in the history folder.")
    rows = merge_rows(saved, legacy, journal)
    tokens = query.casefold().split()
    matches = [row for row in rows if all(token in row["text"].casefold() for token in tokens)]
    displayed = [dict(row, **search_display(row["text"], tokens)) if tokens else row
                 for row in matches[:limit]]
    return {"rows": displayed, "total": len(rows), "matched": len(matches),
            "warning": " ".join(warnings), "handyWarning": handy_warning, "archiveDir": str(directory)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default="")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--no-sync", action="store_true", help="Search saved history without importing sources")
    parser.add_argument("--handy-db", default="", help="Absolute Handy history.db path (default: auto-detect)")
    parser.add_argument("--handy-only", action="store_true", help="Refresh Handy without polling Voxtype's journal")
    args = parser.parse_args()
    try:
        result = load_history(archive_dir(), args.query, max(1, min(100, args.limit)),
                              not args.no_sync, args.handy_db, args.handy_only)
    except OSError:
        print(json.dumps({"error": "Cannot open the history folder. Check its permissions.", "rows": []}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
