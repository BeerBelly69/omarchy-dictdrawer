"""Read-only Handy adapter. Never opens recordings or writes Handy's database."""

from contextlib import closing
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile


def database_path(custom=""):
    if custom:
        path = Path(custom).expanduser()
        if not path.is_absolute():
            raise ValueError("Handy history path must be absolute.")
        return path
    value = os.environ.get("XDG_DATA_HOME", "")
    base = Path(value) if Path(value).is_absolute() else Path.home() / ".local/share"
    return base / "com.pais.handy/history.db"


def read_database(path):
    """Take a consistent SQLite snapshot, including committed WAL entries."""
    rows, skipped = [], 0
    # mode=ro cannot create a missing database; immutable=1 would miss WAL data.
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
        db.execute("PRAGMA query_only = ON")
        db.execute("PRAGMA trusted_schema = OFF")
        db.execute("BEGIN")
        columns = {row[1] for row in db.execute("PRAGMA table_info(transcription_history)")}
        if not {"id", "timestamp", "file_name", "transcription_text"} <= columns:
            raise ValueError("Unsupported Handy history schema.")
        processed = "post_processed_text" if "post_processed_text" in columns else "NULL"
        for ident, stamp, filename, original, final in db.execute(
                f"SELECT id, timestamp, file_name, transcription_text, {processed} "
                "FROM transcription_history ORDER BY timestamp, id"):
            try:
                if not isinstance(ident, int) or not isinstance(stamp, int) or not isinstance(filename, str):
                    raise ValueError("Invalid Handy entry")
                if stamp < 0:
                    raise ValueError("Invalid Handy timestamp")
                datetime.fromtimestamp(stamp)  # Reject unusable date-folder timestamps.
                text = final if isinstance(final, str) and final.strip() else original
                if not isinstance(text, str):
                    raise ValueError("Invalid Handy text")
                if not text.strip():  # Handy inserts empty placeholders during transcription.
                    continue
                digest = hashlib.sha256(f"{ident}\0{filename}".encode()).hexdigest()[:20]
                rows.append({"id": f"handy-{stamp * 1_000_000}-{digest}",
                             "ts": stamp, "text": text, "source": "handy"})
            except (ValueError, OSError, OverflowError):
                skipped += 1
    return rows, f"Skipped {skipped} invalid Handy history entries." if skipped else ""


def atomic_write(path, data):
    if path.is_symlink():
        raise OSError("Refusing a symlinked Handy archive file")
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sync_history(directory, path, day_directory):
    """Update imported text, preserving user edits and Handy-deleted entries.

    A private checksum index lets post-processing replace our own prior copy
    without overwriting manual edits. The lock spans DB read and publication so
    another monitor cannot publish an older snapshot over a newer one.
    """
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(directory / ".handy.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows, warning = read_database(path)
        index_path = directory / ".handy-imports.json"
        if index_path.is_symlink():
            raise OSError("Refusing a symlinked Handy index")
        index = json.loads(index_path.read_text()) if index_path.exists() else {}
        if not isinstance(index, dict) or any(not isinstance(v, str) for v in index.values()):
            raise ValueError("Invalid Handy import index")
        before = dict(index)
        edited = 0
        paths = {}
        for candidate in directory.glob("????-??-??/handy-*.txt"):
            if not candidate.parent.is_symlink():
                paths.setdefault(candidate.name, []).append(candidate)
        for row in rows:
            # Keep an existing file in its original day after a timezone change.
            name = row["id"] + ".txt"
            existing = paths.get(name, [])
            if len(existing) > 1:
                edited += 1
                continue
            target = existing[0] if existing else day_directory(directory, row["ts"]) / name
            if target.is_symlink():
                raise OSError("Refusing a symlinked Handy transcript")
            content = (row["text"] + "\n").encode("utf-8")
            digest = hashlib.sha256(content).hexdigest()
            if target.exists():
                current = hashlib.sha256(target.read_bytes()).hexdigest()
                if current == digest:
                    index[row["id"]] = digest
                    continue
                if current != index.get(row["id"]):
                    edited += 1
                    continue
            atomic_write(target, content)
            index[row["id"]] = digest
        if index != before:
            atomic_write(index_path, json.dumps(index, sort_keys=True).encode())
        if edited:
            warning = " ".join(filter(None, [warning,
                f"Kept {edited} edited or conflicting Handy archive file(s); source updates were not applied."]))
        return warning
