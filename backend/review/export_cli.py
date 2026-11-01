"""Local website export, audit, and SQLite recovery commands."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from .export import ExportError, audit_artifacts, create_export, preview_export


def backup_database(data_dir: Path, output: Path) -> Path:
    catalog = Path(data_dir).resolve() / "catalog.sqlite"
    if not catalog.is_file():
        raise FileNotFoundError(f"Catalog is missing: {catalog}")
    target = output.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"Backup already exists: {target}")
    fd, temporary = tempfile.mkstemp(prefix=".catalog-backup-", dir=target.parent)
    os.close(fd)
    try:
        source = sqlite3.connect(f"file:{catalog.as_posix()}?mode=ro", uri=True)
        try:
            destination = sqlite3.connect(temporary)
            try:
                source.backup(destination)
                destination.commit()
                if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Backup integrity check failed")
            finally:
                destination.close()
        finally:
            source.close()
        os.link(temporary, target)  # Exclusive publication; never overwrite a backup.
        return target
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Approved website export and local recovery checks")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preview")
    export = commands.add_parser("export")
    export.add_argument("--authorized", action="store_true", help="Confirm publication of approved versions")
    commands.add_parser("audit")
    backup = commands.add_parser("backup")
    backup.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command != "backup" and not (args.data_dir / "catalog.sqlite").is_file():
        parser.error(f"Catalog is missing: {args.data_dir / 'catalog.sqlite'}")
    try:
        if args.command == "preview":
            result = preview_export(args.data_dir)
        elif args.command == "export":
            if not args.authorized:
                parser.error("Export requires --authorized after reviewing the preview")
            result = create_export(args.data_dir)
        elif args.command == "audit":
            result = audit_artifacts(args.data_dir)
        else:
            result = {"backup": str(backup_database(args.data_dir, args.output))}
    except (ExportError, FileExistsError, FileNotFoundError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
