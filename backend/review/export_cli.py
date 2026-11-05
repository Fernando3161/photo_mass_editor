"""Local website export, audit, and SQLite recovery commands."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from .export import ExportError, audit_artifacts, create_export, preview_export
from .billing import import_billing
from .c2pa_signing import SigningConfig


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
    parser.add_argument("--data-dir", type=Path, default=Path("data/catalog"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preview")
    export = commands.add_parser("export")
    export.add_argument("--authorized", action="store_true", help="Confirm publication of approved versions")
    export.add_argument("--c2pa-cert", type=Path, help="Owner-supplied C2PA certificate, for optional signed copies")
    export.add_argument("--c2pa-key", type=Path, help="Matching private key; keep outside version control")
    commands.add_parser("audit")
    backup = commands.add_parser("backup")
    backup.add_argument("--output", type=Path, required=True)
    billing = commands.add_parser("reconcile-billing")
    billing.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    if args.command != "backup" and not (args.data_dir / "catalog.sqlite").is_file():
        parser.error(f"Catalog is missing: {args.data_dir / 'catalog.sqlite'}")
    try:
        if args.command == "preview":
            result = preview_export(args.data_dir)
        elif args.command == "export":
            if not args.authorized:
                parser.error("Export requires --authorized after reviewing the preview")
            if bool(args.c2pa_cert) != bool(args.c2pa_key):
                parser.error("C2PA signing requires both certificate and key")
            signing = SigningConfig(args.c2pa_cert, args.c2pa_key) if args.c2pa_cert else None
            result = create_export(args.data_dir, signing=signing)
        elif args.command == "audit":
            result = audit_artifacts(args.data_dir)
        elif args.command == "reconcile-billing":
            result = import_billing(args.data_dir, args.csv)
        else:
            result = {"backup": str(backup_database(args.data_dir, args.output))}
    except (ExportError, FileExistsError, FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
