"""Local catalog CLI. No network or paid operations."""

import argparse
import json
from pathlib import Path

from .database import connect
from .ingestion import import_folder, import_photo, preflight, relink_photo


def main() -> None:
    parser = argparse.ArgumentParser(description="Photo Mass Editor catalog")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    photo = commands.add_parser("import-photo")
    photo.add_argument("source", type=Path)
    photo.add_argument("--mode", choices=("reference", "copy"), default="reference")
    folder = commands.add_parser("import-folder")
    folder.add_argument("folder", type=Path)
    folder.add_argument("--mode", choices=("reference", "copy"), default="reference")
    commands.add_parser("preflight")
    relink = commands.add_parser("relink")
    relink.add_argument("photo_id")
    relink.add_argument("source", type=Path)
    args = parser.parse_args()

    if args.command == "init":
        with connect(args.data_dir) as db:
            print(json.dumps({"schema_version": db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]}))
    elif args.command == "import-photo":
        print(json.dumps(import_photo(args.data_dir, args.source, args.mode)))
    elif args.command == "import-folder":
        print(json.dumps(import_folder(args.data_dir, args.folder, args.mode), indent=2))
    elif args.command == "preflight":
        print(json.dumps(preflight(args.data_dir), indent=2))
    elif args.command == "relink":
        relink_photo(args.data_dir, args.photo_id, args.source)
        print(json.dumps({"id": args.photo_id, "status": "relinked"}))


if __name__ == "__main__":
    main()
