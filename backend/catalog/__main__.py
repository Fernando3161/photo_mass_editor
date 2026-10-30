"""Local catalog CLI. No network or paid operations."""

import argparse
import json
from pathlib import Path

from .database import connect
from .ingestion import import_folder, import_photo, preflight, relink_photo


def gps_status(row) -> str:
    if row["gps_present"]:
        return "VALID"
    raw = json.loads(row["original_exif_json"])
    if "_parse_error" in raw or "_gps_ifd_error" in raw:
        return "UNREADABLE"
    gps = raw.get("34853")
    if not isinstance(gps, dict) or not gps:
        return "ABSENT"
    if not {"1", "2", "3", "4"}.issubset(gps):
        return "INCOMPLETE"
    if gps["1"] not in ("N", "S") or gps["3"] not in ("E", "W"):
        return "INVALID_REFERENCE"
    return "INVALID_COORDINATES"


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
    commands.add_parser("list")
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
    elif args.command == "list":
        db = connect(args.data_dir)
        try:
            rows = db.execute(
                """SELECT id, original_filename, original_path, sha256, mime, width, height,
                          capture_datetime_raw, capture_offset, camera, lens, orientation,
                          private_lat IS NOT NULL AND private_lon IS NOT NULL AS gps_present,
                          original_exif_json, thumbnail_path, duplicate_of_id
                   FROM photos ORDER BY imported_at, id"""
            ).fetchall()
            items = []
            for row in rows:
                item = dict(row)
                item["gps_present"] = bool(row["gps_present"])
                item["gps_status"] = gps_status(row)
                item["thumbnail_path"] = str(Path(args.data_dir).resolve() / row["thumbnail_path"])
                del item["original_exif_json"]
                items.append(item)
            print(json.dumps(items, indent=2))
        finally:
            db.close()
    elif args.command == "preflight":
        print(json.dumps(preflight(args.data_dir), indent=2))
    elif args.command == "relink":
        relink_photo(args.data_dir, args.photo_id, args.source)
        print(json.dumps({"id": args.photo_id, "status": "relinked"}))


if __name__ == "__main__":
    main()
