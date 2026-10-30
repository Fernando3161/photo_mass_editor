"""SQLite connection and numbered, forward-only migrations."""

from pathlib import Path
import sqlite3


MIGRATIONS = Path(__file__).with_name("migrations")


def connect(data_dir: Path) -> sqlite3.Connection:
    data_dir = Path(data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(data_dir / "catalog.sqlite")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    migrate(db)
    return db


def migrate(db: sqlite3.Connection) -> None:
    existing = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    current = (
        db.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]
        if existing else 0
    )
    scripts = sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql"))
    versions = [int(script.name[:3]) for script in scripts]
    if versions != list(range(1, len(versions) + 1)):
        raise RuntimeError("Migration files must have contiguous unique versions")
    if current > len(scripts):
        raise RuntimeError(f"Database schema {current} is newer than this application")
    for version, script in enumerate(scripts, 1):
        if version > current:
            db.executescript(script.read_text(encoding="utf-8"))
