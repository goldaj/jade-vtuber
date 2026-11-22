"""Portable SQLite snapshot transfer for Jade, including WAL-safe online backup.

Export produces a single *unencrypted* .zip containing the database and a
versioned SHA-256 manifest. Move the zip using an encrypted disk/transfer.
Import refuses to overwrite an existing database or follow symlink targets.
Supports schema versions 1 through 8; MemoryStore performs forward migration on open.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import zipfile

ARCHIVE_VERSION = 1
DB_NAME = "jade-memory.sqlite3"
MANIFEST_NAME = "manifest.json"
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024


def _check(path: Path) -> int:
    with closing(sqlite3.connect(str(path))) as db:
        status = db.execute("PRAGMA integrity_check").fetchone()
        foreign = db.execute("PRAGMA foreign_key_check").fetchone()
        version = db.execute("PRAGMA user_version").fetchone()[0]
    if status != ("ok",) or foreign is not None:
        raise ValueError("corrupt memory database")
    if version not in (1, 2, 3, 4, 5, 6, 7, 8):
        raise ValueError("unsupported Jade memory schema version")
    return version


def export_memory(db_path: str | Path, archive_path: str | Path) -> Path:
    """Create a consistent snapshot even while Jade is running in WAL mode."""
    source, output = Path(db_path), Path(archive_path)
    if not source.is_file() or source.is_symlink() or output.is_symlink():
        raise ValueError("invalid source or archive path")
    if source.resolve() == output.resolve():
        raise ValueError("archive cannot overwrite its source database")
    if output.exists():
        raise FileExistsError("archive exists: choose a fresh output name")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    zip_tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=source.parent, suffix=".sqlite3", delete=False) as temp:
            temporary = Path(temp.name)
        # SQLite's backup API copies a transactionally coherent DB, including WAL.
        with closing(sqlite3.connect(str(source))) as src, closing(sqlite3.connect(str(temporary))) as dst:
            src.backup(dst)
        version = _check(temporary)
        raw = temporary.read_bytes()
        if len(raw) > MAX_ARCHIVE_BYTES:
            raise ValueError("memory database exceeds portable archive limit")
        manifest = {
            "format": "jade-memory-backup",
            "archive_version": ARCHIVE_VERSION,
            "schema_version": version,
            "database": DB_NAME,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
        }
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".tmp", delete=False) as temp:
            zip_tmp = Path(temp.name)
        with zipfile.ZipFile(zip_tmp, mode="w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr(DB_NAME, raw)
            bundle.writestr(MANIFEST_NAME, json.dumps(manifest, sort_keys=True))
        # The exclusive existence check above is for normal usage. Import does
        # not overwrite; export must not overwrite an existing archive either.
        if output.exists():
            raise FileExistsError("archive destination appeared during export")
        os.link(zip_tmp, output)
        return output
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if zip_tmp is not None:
            zip_tmp.unlink(missing_ok=True)


def import_memory(archive_path: str | Path, db_path: str | Path) -> Path:
    """Restore into a NEW location; never overwrite an active/migrated DB."""
    archive, target = Path(archive_path), Path(db_path)
    if not archive.is_file() or archive.is_symlink() or target.is_symlink():
        raise ValueError("invalid archive or destination path")
    if target.exists():
        raise FileExistsError("destination already exists, refusing to overwrite")
    target.parent.mkdir(parents=True, exist_ok=True)
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("archive too large")
    with zipfile.ZipFile(archive) as bundle:
        if len(bundle.namelist()) != 2 or set(bundle.namelist()) != {DB_NAME, MANIFEST_NAME}:
            raise ValueError("unexpected archive contents")
        if bundle.getinfo(MANIFEST_NAME).file_size > 8192:
            raise ValueError("manifest exceeds size limit")
        meta = json.loads(bundle.read(MANIFEST_NAME))
        if (meta.get("format") != "jade-memory-backup"
                or meta.get("archive_version") != ARCHIVE_VERSION
                or meta.get("database") != DB_NAME
                or meta.get("schema_version") not in (1, 2, 3, 4, 5, 6, 7, 8)
                or not isinstance(meta.get("size"), int)
                or not 0 < meta["size"] <= MAX_ARCHIVE_BYTES):
            raise ValueError("unsupported archive manifest")
        if bundle.getinfo(DB_NAME).file_size != meta["size"]:
            raise ValueError("incorrect backup length")
        # Bound decompression size before reading user-supplied archives.
        with bundle.open(DB_NAME) as stream:
            raw = stream.read(MAX_ARCHIVE_BYTES + 1)
        if len(raw) != meta["size"] or hashlib.sha256(raw).hexdigest() != meta.get("sha256"):
            raise ValueError("backup integrity mismatch")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".sqlite3",
                                         delete=False) as temp:
            temp_path = Path(temp.name)
            temp.write(raw)
            temp.flush()
            os.fsync(temp.fileno())
        if _check(temp_path) != meta["schema_version"]:
            raise ValueError("backup schema mismatch")
        if target.exists() or target.is_symlink():
            raise FileExistsError("destination appeared during restore")
        os.link(temp_path, target)
        try:
            target.chmod(0o600)
        except OSError:
            pass  # Windows permissions are managed separately.
        return target
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline portable Jade SQLite backup")
    sub = parser.add_subparsers(dest="operation", required=True)
    exp = sub.add_parser("export")
    exp.add_argument("--db", required=True, type=Path)
    exp.add_argument("--out", required=True, type=Path)
    imp = sub.add_parser("import")
    imp.add_argument("--archive", required=True, type=Path)
    imp.add_argument("--db", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "export":
            result = export_memory(args.db, args.out)
        else:
            result = import_memory(args.archive, args.db)
    except (OSError, ValueError, sqlite3.Error, zipfile.BadZipFile) as exc:
        parser.exit(2, f"Jade memory transfer failed: {type(exc).__name__}\n")
    print(f"OK: {result}")


if __name__ == "__main__":
    main()
