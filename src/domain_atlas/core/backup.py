"""Versioned, checksummed backups for a single persistent Domain Atlas data root."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from domain_atlas import __version__
from domain_atlas.core.persistence import DataDirectoryLock


BACKUP_FORMAT_VERSION = 1


class BackupError(RuntimeError):
    """Raised when a backup cannot be created or safely restored."""


@dataclass(frozen=True)
class BackupResult:
    archive_path: Path
    file_count: int
    total_bytes: int


class BackupService:
    def __init__(
        self,
        *,
        data_dir: Path,
        backup_dir: Path,
        lock: DataDirectoryLock | None = None,
    ) -> None:
        self.data_dir = data_dir.resolve()
        self.backup_dir = backup_dir.resolve()
        self.lock = lock or DataDirectoryLock(self.data_dir)

    def create(self) -> BackupResult:
        if not (self.data_dir / "domain_atlas.sqlite3").is_file():
            raise BackupError("Domain Atlas database does not exist; there is nothing to back up.")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        archive_path = self.backup_dir / f"domain-atlas-{timestamp}-{uuid.uuid4().hex[:8]}.tar.gz"
        with self.lock.exclusive():
            with tempfile.TemporaryDirectory(prefix="domain-atlas-backup-") as temporary:
                staging = Path(temporary)
                payload = staging / "payload"
                payload.mkdir()
                self._snapshot_database(payload / "domain_atlas.sqlite3")
                self._copy_payload(payload)
                entries = _manifest_entries(payload)
                manifest = {
                    "format_version": BACKUP_FORMAT_VERSION,
                    "app_version": __version__,
                    "created_at": datetime.now(UTC).isoformat(),
                    "storage_paths": "portable-v1",
                    "files": entries,
                }
                (staging / "manifest.json").write_text(
                    json.dumps(manifest, ensure_ascii=True, indent=2) + "\n",
                    encoding="utf-8",
                )
                temporary_archive = archive_path.with_suffix(archive_path.suffix + ".tmp")
                with tarfile.open(temporary_archive, "w:gz") as archive:
                    archive.add(staging / "manifest.json", arcname="manifest.json", recursive=False)
                    for entry in entries:
                        relative = str(entry["path"])
                        archive.add(
                            payload / relative,
                            arcname=f"payload/{relative}",
                            recursive=False,
                        )
                os.replace(temporary_archive, archive_path)
        return BackupResult(
            archive_path=archive_path,
            file_count=len(entries),
            total_bytes=sum(int(entry["size"]) for entry in entries),
        )

    def _snapshot_database(self, target: Path) -> None:
        source = sqlite3.connect(self.data_dir / "domain_atlas.sqlite3")
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        self._make_database_paths_portable(target)

    def _make_database_paths_portable(self, database_path: Path) -> None:
        connection = sqlite3.connect(database_path)
        try:
            rows = connection.execute(
                "SELECT id, raw_path, normalized_path FROM sources"
            ).fetchall()
            for source_id, raw_path, normalized_path in rows:
                connection.execute(
                    "UPDATE sources SET raw_path = ?, normalized_path = ? WHERE id = ?",
                    (
                        self._portable_path(str(raw_path or "")),
                        self._portable_path(str(normalized_path or "")),
                        int(source_id),
                    ),
                )
            connection.commit()
        finally:
            connection.close()

    def _portable_path(self, value: str) -> str:
        if not value:
            return ""
        path = Path(value)
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(self.data_dir)
        except ValueError as exc:
            raise BackupError(f"Source path is outside DATA_DIR and cannot be backed up: {value}") from exc
        return f"@data/{relative.as_posix()}"

    def _copy_payload(self, payload: Path) -> None:
        excluded_backup = _relative_if_within(self.backup_dir, self.data_dir)
        for source in sorted(self.data_dir.rglob("*")):
            relative = source.relative_to(self.data_dir)
            if source.is_symlink():
                raise BackupError(f"Symlinks are not supported in DATA_DIR: {relative}")
            if not source.is_file():
                continue
            if relative.name in {
                "domain_atlas.sqlite3",
                "domain_atlas.sqlite3-wal",
                "domain_atlas.sqlite3-shm",
                ".domain-atlas.lock",
            }:
                continue
            if relative.name == ".env" or relative.name.startswith(".env."):
                continue
            if excluded_backup is not None and relative.is_relative_to(excluded_backup):
                continue
            destination = payload / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def restore_backup(archive_path: Path, target_dir: Path) -> Path:
    """Restore a verified archive into a missing or empty target directory."""
    archive_path = archive_path.resolve()
    target_dir = target_dir.resolve()
    if not archive_path.is_file():
        raise BackupError(f"Backup archive does not exist: {archive_path}")
    if target_dir.exists() and any(target_dir.iterdir()):
        raise BackupError("Restore target must be missing or empty.")
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        _validate_members(members)
        manifest_member = archive.getmember("manifest.json")
        manifest_file = archive.extractfile(manifest_member)
        if manifest_file is None:
            raise BackupError("Backup manifest is missing.")
        try:
            manifest = json.loads(manifest_file.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackupError("Backup manifest is invalid.") from exc
        entries = _validate_manifest(manifest)
        expected_members = {"manifest.json"} | {
            f"payload/{entry['path']}" for entry in entries
        }
        actual_members = {member.name for member in members}
        if actual_members != expected_members:
            raise BackupError("Backup archive contents do not match its manifest.")

        staging = Path(
            tempfile.mkdtemp(prefix=f".{target_dir.name}-restore-", dir=target_dir.parent)
        )
        try:
            for entry in entries:
                relative = PurePosixPath(str(entry["path"]))
                member = archive.getmember(f"payload/{relative.as_posix()}")
                source = archive.extractfile(member)
                if source is None:
                    raise BackupError(f"Backup file is missing: {relative}")
                destination = staging.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                size = 0
                with destination.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                if size != int(entry["size"]) or digest.hexdigest() != entry["sha256"]:
                    raise BackupError(f"Backup checksum verification failed: {relative}")
            _rebase_restored_database(staging / "domain_atlas.sqlite3", target_dir)
            if target_dir.exists():
                target_dir.rmdir()
            os.replace(staging, target_dir)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    return target_dir


class BackupScheduler:
    """Run the same verified backup operation on a single-process timer."""

    def __init__(
        self,
        service: BackupService,
        *,
        interval_seconds: float,
        retention_count: int,
    ) -> None:
        if interval_seconds <= 0 or retention_count <= 0:
            raise ValueError("Backup schedule values must be positive.")
        self.service = service
        self.interval_seconds = interval_seconds
        self.retention_count = retention_count
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="domain-atlas-backup-scheduler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def run_once(self) -> BackupResult:
        result = self.service.create()
        archives = sorted(
            self.service.backup_dir.glob("domain-atlas-*.tar.gz"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for expired in archives[self.retention_count :]:
            expired.unlink()
        return result

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                self.run_once()
            except Exception:
                # The next interval retries; request handling must not be terminated by backup failure.
                continue


def _manifest_entries(payload: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(item for item in payload.rglob("*") if item.is_file()):
        entries.append(
            {
                "path": path.relative_to(payload).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return entries


def _validate_members(members: list[tarfile.TarInfo]) -> None:
    names: set[str] = set()
    for member in members:
        path = PurePosixPath(member.name)
        if member.name in names:
            raise BackupError("Backup archive contains duplicate paths.")
        names.add(member.name)
        if path.is_absolute() or ".." in path.parts or not member.isfile():
            raise BackupError("Backup archive contains an unsafe member.")
        if member.name != "manifest.json" and not member.name.startswith("payload/"):
            raise BackupError("Backup archive contains an unknown top-level path.")
    if "manifest.json" not in names:
        raise BackupError("Backup manifest is missing.")


def _validate_manifest(manifest: object) -> list[dict[str, object]]:
    if not isinstance(manifest, dict) or manifest.get("format_version") != BACKUP_FORMAT_VERSION:
        raise BackupError("Backup format version is not supported.")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise BackupError("Backup manifest has no files.")
    validated: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict):
            raise BackupError("Backup manifest contains an invalid file entry.")
        path = PurePosixPath(str(entry.get("path") or ""))
        checksum = str(entry.get("sha256") or "")
        size = entry.get("size")
        if (
            not path.parts
            or path.is_absolute()
            or ".." in path.parts
            or path.as_posix() in seen
            or not isinstance(size, int)
            or size < 0
            or len(checksum) != 64
        ):
            raise BackupError("Backup manifest contains an unsafe file entry.")
        seen.add(path.as_posix())
        validated.append({"path": path.as_posix(), "size": size, "sha256": checksum})
    return validated


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_if_within(path: Path, parent: Path) -> Path | None:
    try:
        return path.relative_to(parent)
    except ValueError:
        return None


def _rebase_restored_database(database_path: Path, target_dir: Path) -> None:
    if not database_path.is_file():
        raise BackupError("Backup does not contain the Domain Atlas database.")
    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute("SELECT id, raw_path, normalized_path FROM sources").fetchall()
        for source_id, raw_path, normalized_path in rows:
            rebased: list[str] = []
            for value in (str(raw_path or ""), str(normalized_path or "")):
                if not value:
                    rebased.append("")
                    continue
                if not value.startswith("@data/"):
                    raise BackupError("Backup database contains a non-portable source path.")
                relative = PurePosixPath(value.removeprefix("@data/"))
                if relative.is_absolute() or ".." in relative.parts:
                    raise BackupError("Backup database contains an unsafe source path.")
                rebased.append(str(target_dir.joinpath(*relative.parts)))
            connection.execute(
                "UPDATE sources SET raw_path = ?, normalized_path = ? WHERE id = ?",
                (rebased[0], rebased[1], int(source_id)),
            )
        result = connection.execute("PRAGMA quick_check").fetchone()
        if result is None or str(result[0]) != "ok":
            raise BackupError("Restored SQLite database did not pass its integrity check.")
        connection.commit()
    finally:
        connection.close()
