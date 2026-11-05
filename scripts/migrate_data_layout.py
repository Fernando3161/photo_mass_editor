"""Copy a phase review catalog into the stable data layout without deleting its source."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
    raise SystemExit("Run this script with the repository .venv interpreter")
sys.path.insert(0, str(ROOT))

from backend.catalog.ingestion import sha256
from backend.review.export import audit_artifacts, preview_export
from backend.review.export_cli import backup_database


CATALOG_FOLDERS = ("originals", "thumbnails", "publication-inputs", "masks", "edited")


class LayoutMigrationError(ValueError):
    """A source, target, or copied artifact failed the migration contract."""


def _files(folder: Path):
    if folder.is_dir():
        for path in folder.rglob("*"):
            if path.is_symlink():
                raise LayoutMigrationError(f"Symlink in migration input: {path}")
            if path.is_file():
                yield path


def _copy_tree(source: Path, destination: Path) -> int:
    destination.mkdir(parents=True, exist_ok=False)
    count = 0
    for path in _files(source):
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        with path.open("rb") as original, target.open("xb") as copy:
            shutil.copyfileobj(original, copy)
            copy.flush()
            os.fsync(copy.fileno())
        if sha256(path) != sha256(target):
            raise LayoutMigrationError(f"Copied bytes differ: {path}")
        count += 1
    return count


def inspect_layout(source_catalog: Path, target_root: Path) -> dict:
    source = source_catalog.resolve()
    target = target_root.resolve()
    database = source / "catalog.sqlite"
    if not database.is_file():
        raise FileNotFoundError(f"Source catalog is missing: {database}")
    if (target / "catalog").exists() or (target / "input").exists() or (target / "exports").exists():
        raise LayoutMigrationError("Canonical input, catalog, or exports already exists; inspect it before retrying")
    old_input = source.parent / "input"
    db = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        photos = db.execute("SELECT id,original_path,sha256 FROM photos").fetchall()
        inside = 0
        external = 0
        for photo_id, original_path, expected in photos:
            path = Path(original_path).resolve()
            if not path.is_file() or sha256(path) != expected:
                raise LayoutMigrationError(f"Original is missing or changed: {photo_id}")
            if old_input.resolve() in path.parents:
                inside += 1
            else:
                external += 1
        exports = db.execute("SELECT COUNT(*) FROM exports").fetchone()[0]
        version = db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        if version not in (8, 9, 10, 11, 12, 13, 14):
            raise LayoutMigrationError("Source catalog must be at schema 8 through 14 before layout migration")
    finally:
        db.close()
    return {"source_catalog": str(source), "source_input": str(old_input.resolve()),
            "target_root": str(target), "photos": len(photos), "input_originals": inside,
            "external_originals_preserved": external, "exports": exports,
            "catalog_files": sum(1 for folder in CATALOG_FOLDERS for _ in _files(source / folder)),
            "input_files": sum(1 for _ in _files(old_input)),
            "export_files": sum(1 for _ in _files(source / "exports"))}


def migrate_layout(source_catalog: Path, target_root: Path) -> dict:
    plan = inspect_layout(source_catalog, target_root)
    source = Path(plan["source_catalog"])
    target = Path(plan["target_root"])
    target.mkdir(parents=True, exist_ok=True)
    backups = target / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_database(source, backups / f"catalog-before-layout-{stamp}-{uuid4().hex[:8]}.sqlite")
    stage = target / f".layout-preparing-{uuid4().hex}"
    stage.mkdir()
    try:
        _copy_tree(Path(plan["source_input"]), stage / "input")
        catalog_stage = stage / "catalog"
        catalog_stage.mkdir()
        for folder in CATALOG_FOLDERS:
            if (source / folder).is_dir():
                _copy_tree(source / folder, catalog_stage / folder)
        _copy_tree(source / "exports", stage / "exports")
        shutil.copy2(backup, catalog_stage / "catalog.sqlite")
        db = sqlite3.connect(catalog_stage / "catalog.sqlite")
        try:
            old_input = Path(plan["source_input"])
            for photo_id, original_path, expected in db.execute("SELECT id,original_path,sha256 FROM photos"):
                original = Path(original_path).resolve()
                if old_input in original.parents:
                    new_path = target / "input" / original.relative_to(old_input)
                    staged = stage / "input" / original.relative_to(old_input)
                    if not staged.is_file() or sha256(staged) != expected:
                        raise LayoutMigrationError(f"Copied original hash mismatch: {photo_id}")
                    db.execute("UPDATE photos SET original_path=? WHERE id=?", (str(new_path), photo_id))
            db.commit()
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise LayoutMigrationError("Copied catalog integrity check failed")
        finally:
            db.close()
        # Publish the database last so an incomplete copy is never the active catalog.
        (stage / "input").rename(target / "input")
        (stage / "exports").rename(target / "exports")
        catalog_stage.rename(target / "catalog")
        (target / "evidence").mkdir(parents=True, exist_ok=True)
        audit = audit_artifacts(target / "catalog")
        if any(audit[key] for key in ("missing", "changed", "source_issues", "invalid_manifests", "invalid_cost_reports")):
            raise LayoutMigrationError(f"Canonical catalog needs investigation: {audit}")
        preview = preview_export(target / "catalog")
        return {**plan, "backup": str(backup), "canonical_catalog": str(target / "catalog"),
                "canonical_input": str(target / "input"), "canonical_exports": str(target / "exports"),
                "approved_count": preview["approved_count"], "audit": audit}
    finally:
        if stage.is_dir() and not any(stage.iterdir()):
            stage.rmdir()


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy and verify a phase catalog in the stable data layout")
    parser.add_argument("--source-catalog", type=Path, default=Path("data/phase04-review/catalog"))
    parser.add_argument("--target-root", type=Path, default=Path("data"))
    parser.add_argument("--apply", action="store_true", help="Copy files and publish the canonical catalog")
    args = parser.parse_args()
    result = (migrate_layout(args.source_catalog, args.target_root) if args.apply
              else inspect_layout(args.source_catalog, args.target_root))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
