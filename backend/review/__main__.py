"""Run the local review and editing workstation."""

import argparse
import os
from pathlib import Path

import uvicorn

from backend.catalog.database import connect
from backend.catalog.ingestion import EXTENSIONS, import_folder, preflight

from .app import create_app
from .local_config import load_local_config


def prepare_catalog(data_dir: Path) -> None:
    catalog_dir = data_dir.resolve()
    data_root = catalog_dir.parent
    input_dir = data_root / "input"
    for path in (input_dir, catalog_dir, data_root / "exports",
                 data_root / "backups", data_root / "evidence", data_root / "models"):
        path.mkdir(parents=True, exist_ok=True)
    if (catalog_dir / "catalog.sqlite").is_file():
        checks = preflight(catalog_dir)
        if any(row["source"] != "OK" or row["thumbnail"] != "OK"
               or row["managed"] not in (None, "OK") for row in checks):
            raise SystemExit("Existing catalog has missing or changed media; restore or archive it before importing a different batch")
    if any(path.is_file() and path.suffix.lower() in EXTENSIONS for path in input_dir.rglob("*")):
        result = import_folder(catalog_dir, input_dir)
        if result["errors"]:
            raise SystemExit(f"Photo import failed for {len(result['errors'])} file(s): {result['errors']}")
        print(f"Catalog ready: {len(result['imported'])} imported, {len(result['existing'])} existing photos")
    else:
        db = connect(catalog_dir)
        db.close()
        print("Catalog ready: no supported photos in data/input")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local photo review workstation")
    parser.add_argument("--data-dir", type=Path, default=Path("data/catalog"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    access_password = os.environ.get("PHOTO_EDITOR_ACCESS_PASSWORD", "")
    if args.host not in ("127.0.0.1", "localhost", "::1") and not access_password:
        raise SystemExit("Network binding requires PHOTO_EDITOR_ACCESS_PASSWORD; use scripts/start.ps1")
    try:
        loaded = load_local_config()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    if loaded:
        print("Loaded private server configuration from config/openAI.env")
    prepare_catalog(args.data_dir)
    uvicorn.run(create_app(args.data_dir, access_password=access_password), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
