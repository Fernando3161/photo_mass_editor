"""Inspect a stopped, host-mounted Docker evaluation without changing its catalog."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from importlib.metadata import version


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def query_count(db: sqlite3.Connection, table: str) -> int:
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone():
        return 0
    return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", choices=["stopped"], required=True)
    args = parser.parse_args()
    del args
    root = Path("/evaluation")
    workspace = Path("/workspace")
    expected = (workspace / ".venv").resolve()
    if Path(sys.prefix).resolve() != expected:
        raise SystemExit("Report must use the workspace .venv interpreter")
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8-sig"))
    tests_file = root / "test-results/results.json"
    tests = json.loads(tests_file.read_text(encoding="utf-8-sig")) if tests_file.is_file() else []
    if isinstance(tests, dict):
        tests = [tests]
    manifest = json.loads((root / "input-checksums.json").read_text(encoding="utf-8-sig"))
    if isinstance(manifest, dict):
        manifest = [manifest]
    input_checks = []
    for item in manifest:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise SystemExit("Invalid input manifest path")
        copied = workspace / "data/input" / relative
        host = Path("/host-input") / relative
        input_checks.append((item["path"], copied.is_file() and digest(copied) == item["sha256"],
                             host.is_file() and digest(host) == item["sha256"]))
    database = workspace / "data/catalog/catalog.sqlite"
    integrity = "NOT_RUN: catalog absent"
    foreign_keys = "NOT_RUN"
    counts = {}
    exports = []
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = root / "test-results" / f"catalog-snapshot-{stamp}.sqlite"
    if database.is_file():
        db = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = str(len(db.execute("PRAGMA foreign_key_check").fetchall()))
            for table in ("photos", "local_jobs", "edit_jobs", "image_versions", "exports"):
                counts[table] = query_count(db, table)
            if query_count(db, "exports"):
                exports = [dict(id=row[0], status=row[1], manifest=row[2])
                           for row in db.execute("SELECT id,status,manifest_path FROM exports ORDER BY created_at")]
            target = sqlite3.connect(backup)
            try:
                db.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise SystemExit("SQLite backup failed integrity_check")
            finally:
                target.close()
        finally:
            db.close()
    node = subprocess.check_output(["node", "--version"], text=True).strip()
    python = sys.version.split()[0]
    package_versions = {name: version(name) for name in ("fastapi", "uvicorn", "pillow", "numpy")
                        if _has_distribution(name)}
    required_workspace = [
        workspace / ".git", workspace / ".venv/bin/python",
        workspace / "frontend/node_modules", workspace / "frontend/dist/index.html",
        workspace / "data/input", workspace / "data/catalog",
        workspace / "data/exports",
    ]
    workspace_ok = all(path.exists() for path in required_workspace)
    local_jobs = Counter()
    edit_jobs = Counter()
    if database.is_file():
        db = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            for table, target in (("local_jobs", local_jobs), ("edit_jobs", edit_jobs)):
                if query_count(db, table):
                    target.update(dict(db.execute(f"SELECT status,COUNT(*) FROM {table} GROUP BY status")))
        finally:
            db.close()
    now = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Local Docker evaluation report", "",
        f"- Run ID: {metadata['run_id']}",
        f"- Evaluated at UTC: {now}",
        f"- Repository: {metadata['repository']}",
        f"- Selected revision: {metadata['revision']}",
        f"- Exact commit: {metadata['commit_sha']}",
        f"- Docker image: {metadata['image_id']}",
        f"- Runtime: Python {python}; Node.js {node}",
        f"- Dependencies: {json.dumps(package_versions, sort_keys=True)}",
        f"- Host port: 127.0.0.1:{metadata['port']}",
        f"- Application startup and authenticated health: {metadata.get('health_status', 'NOT_RUN')} "
        f"at {metadata.get('health_checked_at_utc', 'unknown')}; see logs/server.log",
        "", "## Automated checks", "",
    ]
    for test in tests:
        lines.append(f"- {test['name']}: {test['status']} ({test['log']})")
    for name in ("python-unittest", "frontend-vitest", "frontend-build"):
        if name not in {test["name"] for test in tests}:
            lines.append(f"- {name}: NOT_RUN")
    lines += [
        "", "## State and recovery", "",
        f"- Imported photos in catalog: {counts.get('photos', 0)}",
        f"- Local jobs by status: {dict(local_jobs)}",
        f"- Generative jobs by status: {dict(edit_jobs)}",
        f"- Image versions: {counts.get('image_versions', 0)}",
        f"- Exports: {counts.get('exports', 0)}",
        f"- SQLite integrity_check: {integrity}",
        f"- SQLite foreign_key_check violations: {foreign_keys}",
        f"- Consistent SQLite backup: {'test-results/' + backup.name if backup.is_file() else 'NOT_RUN'}",
        f"- Input checksums: copied {sum(copy for _, copy, _ in input_checks)}/{len(input_checks)}; host originals {sum(host for _, _, host in input_checks)}/{len(input_checks)}",
        f"- Workspace snapshot: {'PASS' if workspace_ok else 'FAIL'}; workspace/ is directly mounted and retained after stop",
        "- Workspace includes repository source, .venv, frontend dependencies and build, data, and generated artifacts.",
        "", "## Export records", "",
    ]
    lines += [f"- {row['id']}: {row['status']} — workspace/data/{row['manifest']}"
              for row in exports] or ["- None"]
    lines += [
        "", "## Manual acceptance", "",
        "- Browser layout, photographic quality, recognition accuracy, full workflows and owner approval: NOT_RUN unless separately recorded by the owner.",
        "- Paid OpenAI calls: NOT_RUN by this evaluator. A separately authorized interactive run may change the catalog.",
        "- Export privacy and image integrity: NOT_RUN unless separately inspected; see each export manifest and audit.",
        "", "## Limits", "",
        "- Credentials are held in data/exports/docker/.credentials/ outside this run. Provider environment files are external.",
        "- Stop or Snapshot closes the server before this report; preserve the whole run directory privately.",
        "- If a checksum or database check fails, investigate before resuming or publishing.",
    ]
    (root / "evaluation-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report written; integrity={integrity}; inputs={len(input_checks)}")
    required = {"python-unittest", "frontend-vitest", "frontend-build"}
    checks_passed = required <= {test["name"] for test in tests if test["status"] == "PASS"}
    return 0 if (integrity == "ok" and foreign_keys == "0" and
                 all(a and b for _, a, b in input_checks) and
                 checks_passed and workspace_ok and metadata.get("health_status") == "PASS") else 1


def _has_distribution(name: str) -> bool:
    from importlib.metadata import PackageNotFoundError
    try:
        version(name)
        return True
    except PackageNotFoundError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
