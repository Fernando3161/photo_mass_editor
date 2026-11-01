"""Private Phase 05 catalog backup and original-hash comparison."""

import argparse
import json
from pathlib import Path
import sqlite3
import sys
from datetime import datetime, timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
    raise SystemExit("Run this script with the repository .venv interpreter")
sys.path.insert(0, str(ROOT))

from backend.catalog.ingestion import sha256  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--stage", choices=("before", "after"), required=True)
    args = parser.parse_args()
    database = args.data_dir.resolve() / "catalog.sqlite"
    if not database.is_file():
        raise SystemExit(f"Required catalog is missing: {database}")
    evidence = args.evidence_dir.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    before = evidence / "source-before.json"
    if args.stage == "before" and before.exists():
        raise SystemExit(f"Before snapshot already exists; choose a new evidence directory: {before}")
    with sqlite3.connect(database) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT id, original_path, managed_original_path, sha256 FROM photos ORDER BY id").fetchall()
        if not rows:
            raise SystemExit("Catalog contains no photos")
        if args.stage == "before":
            backup = evidence / f"catalog-before-phase05-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}.sqlite"
            with sqlite3.connect(backup) as target:
                db.backup(target)
        observed = {}
        for row in rows:
            path = Path(row["original_path"])
            if not path.is_file() and row["managed_original_path"]:
                path = args.data_dir.resolve() / row["managed_original_path"]
            if not path.is_file():
                raise SystemExit(f"Source missing for photo {row['id']}")
            digest = sha256(path)
            if digest != row["sha256"]:
                raise SystemExit(f"Source hash differs from catalog for photo {row['id']}")
            observed[row["id"]] = digest
    if args.stage == "before":
        before.write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")
        print(f"Backed up catalog and verified {len(observed)} sources in {evidence}")
    else:
        if not before.is_file():
            raise SystemExit(f"Before-hash manifest is missing: {before}")
        if json.loads(before.read_text(encoding="utf-8")) != observed:
            raise SystemExit("Photo selection or source hash changed since before snapshot")
        (evidence / "source-after.json").write_text(json.dumps(observed, indent=2) + "\n", encoding="utf-8")
        print(f"Verified {len(observed)} unchanged sources")


if __name__ == "__main__":
    main()
