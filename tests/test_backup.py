from __future__ import annotations

import io
import json
import sys
import tarfile

import pytest

from domain_atlas.core.backup import BackupError, BackupScheduler, BackupService, restore_backup
from domain_atlas.core.db import initialize_database
from domain_atlas.core.persistence import PersistentDataError, validate_private_data_directory
from domain_atlas.core.settings import get_settings
from domain_atlas import cli
from domain_atlas.domain.artifacts import KnowledgeArtifactRepository
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.sources import CreateSource, SourceRepository


def _seed_data(data_dir):
    database_path = data_dir / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(
        CreateDomainProject(name="Private Learning Atlas")
    )
    KnowledgeArtifactRepository(database_path).replace_project_artifacts(
        project.id,
        {
            "wiki_pages": [
                {
                    "slug": "index",
                    "page_type": "index",
                    "path": "wiki/index",
                    "title": "Private Wiki Index",
                    "topic_path": "index",
                    "summary": "Recovered summary.",
                    "body_markdown": "# Private Wiki Index",
                    "sections": [
                        {
                            "section_uid": "index#overview",
                            "heading": "Overview",
                            "body_markdown": "Recovered knowledge.",
                        }
                    ],
                }
            ],
            "source_profiles": [],
            "concepts": [],
            "concept_edges": [],
            "learning_modules": [],
        },
    )
    source_file = data_dir / "sources" / str(project.id) / "1" / "normalized.txt"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("private source evidence", encoding="utf-8")
    source_repository = SourceRepository(database_path)
    source = source_repository.create(
        CreateSource(
            project_id=project.id,
            source_type="markdown",
            title="Private source",
            locator="upload:private-source",
            raw_path=str(source_file),
        )
    )
    source_repository.update_ingested(
        source.id,
        raw_path=str(source_file),
        normalized_path=str(source_file),
        checksum="fixture-checksum",
        metadata={},
    )
    chroma_file = data_dir / "chroma" / "chroma.sqlite3"
    chroma_file.parent.mkdir(parents=True)
    chroma_file.write_bytes(b"fixture-chroma-state")
    (data_dir / ".env").write_text("SHOULD_NOT_BE_HERE=true", encoding="utf-8")
    return project


def test_private_data_directory_requires_absolute_acknowledged_writable_path(tmp_path):
    with pytest.raises(PersistentDataError, match="absolute path"):
        validate_private_data_directory(tmp_path.relative_to(tmp_path.parent), acknowledged=True)
    with pytest.raises(PersistentDataError, match="PERSISTENT_DATA_ACKNOWLEDGED"):
        validate_private_data_directory(tmp_path.resolve(), acknowledged=False)

    resolved = validate_private_data_directory(tmp_path.resolve(), acknowledged=True)

    assert resolved == tmp_path.resolve()
    assert not list(tmp_path.glob(".write-probe-*"))


def test_backup_restore_round_trip_recovers_database_wiki_and_files(tmp_path):
    data_dir = tmp_path / "private-data"
    project = _seed_data(data_dir)
    backup_dir = data_dir / "backups"
    service = BackupService(data_dir=data_dir, backup_dir=backup_dir)

    result = service.create()

    assert result.archive_path.is_file()
    assert result.file_count >= 3
    with tarfile.open(result.archive_path, "r:gz") as archive:
        names = archive.getnames()
        manifest = json.load(archive.extractfile("manifest.json"))
    assert "payload/domain_atlas.sqlite3" in names
    assert "payload/sources/1/1/normalized.txt" in names
    assert "payload/chroma/chroma.sqlite3" in names
    assert not any("backups/" in name for name in names)
    assert not any(name.endswith(".env") for name in names)
    assert manifest["format_version"] == 1
    assert all(len(entry["sha256"]) == 64 for entry in manifest["files"])

    restored_dir = tmp_path / "restored"
    restored_dir.mkdir()
    restore_backup(result.archive_path, restored_dir)

    restored_project = DomainProjectRepository(
        restored_dir / "domain_atlas.sqlite3"
    ).get(project.id)
    restored_page = KnowledgeArtifactRepository(
        restored_dir / "domain_atlas.sqlite3"
    ).get_wiki_page_by_path(project.id, "wiki/index")
    restored_source = SourceRepository(restored_dir / "domain_atlas.sqlite3").get(1)
    assert restored_project is not None
    assert restored_project.name == "Private Learning Atlas"
    assert restored_page is not None
    assert restored_page.title == "Private Wiki Index"
    assert restored_source is not None
    assert restored_source.raw_path == str(restored_dir / "sources/1/1/normalized.txt")
    assert restored_source.normalized_path == str(restored_dir / "sources/1/1/normalized.txt")
    assert (restored_dir / "sources/1/1/normalized.txt").read_text() == "private source evidence"
    assert (restored_dir / "chroma/chroma.sqlite3").read_bytes() == b"fixture-chroma-state"


def test_restore_rejects_nonempty_target_and_path_traversal(tmp_path):
    data_dir = tmp_path / "private-data"
    _seed_data(data_dir)
    archive_path = BackupService(
        data_dir=data_dir,
        backup_dir=tmp_path / "backups",
    ).create().archive_path
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "keep.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(BackupError, match="missing or empty"):
        restore_backup(archive_path, nonempty)

    malicious = tmp_path / "malicious.tar.gz"
    with tarfile.open(malicious, "w:gz") as archive:
        manifest = tarfile.TarInfo("manifest.json")
        manifest_payload = json.dumps({"format_version": 1, "files": []}).encode()
        manifest.size = len(manifest_payload)
        archive.addfile(manifest, io.BytesIO(manifest_payload))
        traversal = tarfile.TarInfo("payload/../../escaped.txt")
        traversal.size = 4
        archive.addfile(traversal, io.BytesIO(b"nope"))

    with pytest.raises(BackupError, match="unsafe member"):
        restore_backup(malicious, tmp_path / "malicious-restore")
    assert not (tmp_path / "escaped.txt").exists()


def test_restore_rejects_checksum_mismatch(tmp_path):
    archive_path = tmp_path / "bad-checksum.tar.gz"
    payload = b"database-like-content"
    manifest_payload = json.dumps(
        {
            "format_version": 1,
            "files": [
                {
                    "path": "domain_atlas.sqlite3",
                    "size": len(payload),
                    "sha256": "0" * 64,
                }
            ],
        }
    ).encode()
    with tarfile.open(archive_path, "w:gz") as archive:
        manifest = tarfile.TarInfo("manifest.json")
        manifest.size = len(manifest_payload)
        archive.addfile(manifest, io.BytesIO(manifest_payload))
        database = tarfile.TarInfo("payload/domain_atlas.sqlite3")
        database.size = len(payload)
        archive.addfile(database, io.BytesIO(payload))

    with pytest.raises(BackupError, match="checksum verification failed"):
        restore_backup(archive_path, tmp_path / "restored")


def test_backup_scheduler_enforces_retention(tmp_path):
    data_dir = tmp_path / "private-data"
    _seed_data(data_dir)
    service = BackupService(data_dir=data_dir, backup_dir=tmp_path / "backups")
    scheduler = BackupScheduler(service, interval_seconds=3600, retention_count=2)

    scheduler.run_once()
    scheduler.run_once()
    scheduler.run_once()

    assert len(list(service.backup_dir.glob("domain-atlas-*.tar.gz"))) == 2


def test_cli_backup_and_restore_commands_round_trip(tmp_path, monkeypatch, capsys):
    data_dir = tmp_path / "private-data"
    _seed_data(data_dir)
    backup_dir = tmp_path / "cli-backups"
    restored_dir = tmp_path / "cli-restored"
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    get_settings.cache_clear()
    monkeypatch.setattr(
        sys,
        "argv",
        ["domain-atlas", "backup", "--output-dir", str(backup_dir)],
    )

    cli.main()

    archive_path = capsys.readouterr().out.strip()
    assert archive_path.endswith(".tar.gz")
    get_settings.cache_clear()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain-atlas",
            "restore",
            archive_path,
            "--target-dir",
            str(restored_dir),
        ],
    )

    cli.main()

    assert capsys.readouterr().out.strip() == str(restored_dir)
    restored = DomainProjectRepository(restored_dir / "domain_atlas.sqlite3").get(1)
    assert restored is not None
    assert restored.name == "Private Learning Atlas"
    get_settings.cache_clear()
