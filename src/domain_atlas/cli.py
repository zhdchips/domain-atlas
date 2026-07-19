"""Command-line entry point for local development."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from domain_atlas.auth import OwnerSessionRepository
from domain_atlas.core.backup import BackupService, restore_backup
from domain_atlas.core.persistence import DataDirectoryLock
from domain_atlas.core.settings import get_settings


def main() -> None:
    """Run the server or explicit private-data maintenance commands."""
    parser = argparse.ArgumentParser(prog="domain-atlas")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("serve", help="Run the local development server.")
    backup_parser = subparsers.add_parser("backup", help="Create a verified data backup.")
    backup_parser.add_argument("--output-dir", type=Path)
    restore_parser = subparsers.add_parser("restore", help="Restore a backup into an empty path.")
    restore_parser.add_argument("archive", type=Path)
    restore_parser.add_argument("--target-dir", type=Path, required=True)
    subparsers.add_parser("revoke-sessions", help="Revoke all private owner sessions.")
    args = parser.parse_args()

    if args.command == "backup":
        settings = get_settings()
        output_dir = args.output_dir or settings.backups_path
        result = BackupService(
            data_dir=settings.data_dir,
            backup_dir=output_dir,
            lock=DataDirectoryLock(settings.data_dir),
        ).create()
        print(result.archive_path)
        return
    if args.command == "restore":
        restored = restore_backup(args.archive, args.target_dir)
        print(restored)
        return
    if args.command == "revoke-sessions":
        settings = get_settings()
        settings.validate_private_auth()
        repository = OwnerSessionRepository(
            settings.database_path,
            secret=settings.session_secret,
            ttl_seconds=settings.session_ttl_hours * 3600,
        )
        print(f"revoked={repository.revoke_all()}")
        return

    uvicorn.run(
        "domain_atlas.web.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
