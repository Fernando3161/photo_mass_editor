"""Read-only source inspection and atomic catalog artifact creation."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError

from .database import connect


SUPPORTED = {"JPEG": "image/jpeg", "PNG": "image/png", "TIFF": "image/tiff", "WEBP": "image/webp"}
EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
KNOWN_UNSUPPORTED = {".heic", ".heif", ".dng", ".raw", ".cr2", ".cr3", ".nef", ".arw"}
THUMB_SIZE = (512, 512)


class ImportErrorDetail(ValueError):
    """A source cannot be safely imported."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_safe(value):
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (tuple, list)):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        return {"numerator": value.numerator, "denominator": value.denominator}
    return str(value)


def _gps_decimal(gps: dict, keys: tuple[int, int], positive: str, negative: str) -> float | None:
    coordinate, ref = (gps.get(key) for key in keys)
    if not isinstance(coordinate, (tuple, list)) or len(coordinate) != 3:
        return None
    if isinstance(ref, bytes):
        ref = ref.decode("ascii", errors="ignore")
    if ref not in (positive, negative):
        return None
    try:
        parts = [float(item) for item in coordinate]
        value = parts[0] + parts[1] / 60 + parts[2] / 3600
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    limit = 90 if positive == "N" else 180
    if not 0 <= value <= limit:
        return None
    return value if ref == positive else -value


def inspect_image(path: Path) -> dict:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            if image.format not in SUPPORTED:
                raise ImportErrorDetail(f"Unsupported image format: {image.format}")
            width, height = image.size
            try:
                exif = image.getexif()
                raw = {str(key): json_safe(value) for key, value in exif.items()}
            except (OSError, ValueError, TypeError, SyntaxError):
                exif = Image.Exif()
                raw = {"_parse_error": "Invalid EXIF metadata"}
            try:
                exif_ifd = dict(exif.get_ifd(ExifTags.IFD.Exif))
            except (OSError, ValueError, TypeError, SyntaxError):
                exif_ifd = {}
                raw["_exif_ifd_error"] = "Invalid EXIF IFD"
            if exif_ifd:
                raw["ExifIFD"] = json_safe(exif_ifd)
            try:
                gps = dict(exif.get_ifd(ExifTags.IFD.GPSInfo)) if ExifTags.Base.GPSInfo in exif else {}
            except (OSError, ValueError, TypeError, SyntaxError):
                gps = {}
                raw["_gps_ifd_error"] = "Invalid GPS IFD"
            if gps:
                raw[str(ExifTags.Base.GPSInfo)] = json_safe(gps)
            lat = _gps_decimal(gps, (2, 1), "N", "S")
            lon = _gps_decimal(gps, (4, 3), "E", "W")
            def field(tag):
                return exif_ifd.get(tag, exif.get(tag))
            def text_field(tag):
                value = field(tag)
                return value if isinstance(value, str) else None
            orientation = exif.get(ExifTags.Base.Orientation)
            return {
                "mime": SUPPORTED[image.format],
                "width": width,
                "height": height,
                "capture_datetime_raw": text_field(ExifTags.Base.DateTimeOriginal)
                    or text_field(ExifTags.Base.DateTime),
                "capture_offset": text_field(ExifTags.Base.OffsetTimeOriginal),
                "camera": text_field(ExifTags.Base.Model),
                "lens": text_field(ExifTags.Base.LensModel),
                "orientation": orientation if isinstance(orientation, int) and 1 <= orientation <= 8 else None,
                "original_exif_json": json.dumps(raw, ensure_ascii=False, sort_keys=True),
                "private_lat": lat if lat is not None and lon is not None else None,
                "private_lon": lon if lat is not None and lon is not None else None,
            }
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ImportErrorDetail(f"Cannot decode image: {path.name}: {exc}") from exc


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".import-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as destination, source.open("rb") as original:
            shutil.copyfileobj(original, destination)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _thumbnail(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".thumb-", dir=target.parent)
    os.close(fd)
    try:
        with Image.open(source) as original:
            try:
                preview = ImageOps.exif_transpose(original)
            except (OSError, ValueError, TypeError, SyntaxError):
                preview = original.copy()
            preview.thumbnail(THUMB_SIZE)
            preview.convert("RGB").save(temporary, format="PNG")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def import_photo(data_dir: Path, source: Path, mode: str = "reference") -> dict:
    if mode not in ("reference", "copy"):
        raise ValueError("mode must be reference or copy")
    data_dir = Path(data_dir).resolve()
    source = Path(source).resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in EXTENSIONS:
        raise ImportErrorDetail(f"Not a supported image path: {source}")
    db = connect(data_dir)
    created: list[Path] = []
    try:
        before = sha256(source)
        previous = db.execute("SELECT * FROM photos WHERE original_path = ?", (str(source),)).fetchone()
        if previous:
            if previous["sha256"] != before:
                raise ImportErrorDetail("Path conflict: cataloged original bytes changed")
            return {"id": previous["id"], "status": "existing", "duplicate_of_id": previous["duplicate_of_id"]}
        metadata = inspect_image(source)
        photo_id = str(uuid4())
        duplicate = db.execute("SELECT id FROM photos WHERE sha256 = ? ORDER BY imported_at, id LIMIT 1", (before,)).fetchone()
        managed = None
        if mode == "copy":
            suffix = source.suffix.lower()
            managed = data_dir / "originals" / f"{photo_id}{suffix}"
            _atomic_copy(source, managed)
            created.append(managed)
            if sha256(managed) != before:
                raise ImportErrorDetail("Managed copy checksum mismatch")
        thumb = data_dir / "thumbnails" / f"{photo_id}.png"
        _thumbnail(source, thumb)
        created.append(thumb)
        thumb_hash = sha256(thumb)
        if sha256(source) != before:
            raise ImportErrorDetail("Original changed during import")
        db.execute(
            """INSERT INTO photos (
                id, original_filename, original_path, managed_original_path, thumbnail_path, thumbnail_sha256,
                sha256, mime, width, height, imported_at, capture_datetime_raw,
                capture_offset, camera, lens, orientation, original_exif_json,
                private_lat, private_lon, duplicate_of_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (photo_id, source.name, str(source), str(managed.relative_to(data_dir)) if managed else None,
             str(thumb.relative_to(data_dir)), thumb_hash, before, metadata["mime"], metadata["width"],
             metadata["height"], utc_now(), metadata["capture_datetime_raw"],
             metadata["capture_offset"], metadata["camera"], metadata["lens"],
             metadata["orientation"], metadata["original_exif_json"],
             metadata["private_lat"], metadata["private_lon"], duplicate["id"] if duplicate else None),
        )
        db.commit()
        return {"id": photo_id, "status": "imported", "duplicate_of_id": duplicate["id"] if duplicate else None}
    except Exception:
        db.rollback()
        for artifact in created:
            artifact.unlink(missing_ok=True)
        raise
    finally:
        db.close()


def import_folder(data_dir: Path, folder: Path, mode: str = "reference") -> dict:
    folder = Path(folder).resolve(strict=True)
    if not folder.is_dir():
        raise ImportErrorDetail(f"Not a directory: {folder}")
    results = {"imported": [], "existing": [], "errors": [], "sidecars": [], "unsupported": []}
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        if path.resolve().is_relative_to(Path(data_dir).resolve()):
            continue
        if path.suffix.lower() in {".xmp", ".aae", ".json"}:
            results["sidecars"].append(str(path))
        elif path.suffix.lower() in KNOWN_UNSUPPORTED:
            results["unsupported"].append(str(path))
        elif path.suffix.lower() in EXTENSIONS:
            try:
                item = import_photo(data_dir, path, mode)
                results[item["status"]].append(item)
            except (ImportErrorDetail, OSError) as exc:
                results["errors"].append({"path": str(path), "error": str(exc)})
    return results


def preflight(data_dir: Path) -> list[dict]:
    data_dir = Path(data_dir).resolve()
    db = connect(data_dir)
    output = []
    try:
        for row in db.execute("SELECT * FROM photos ORDER BY imported_at, id"):
            source = Path(row["original_path"])
            try:
                if not source.is_file():
                    status = "MISSING"
                elif sha256(source) != row["sha256"]:
                    status = "CHANGED"
                else:
                    status = "OK"
            except OSError:
                status = "UNREADABLE"
            managed = data_dir / row["managed_original_path"] if row["managed_original_path"] else None
            thumb = data_dir / row["thumbnail_path"]
            managed_status = ("MISSING" if not managed.is_file() else
                              "CHANGED" if sha256(managed) != row["sha256"] else "OK") if managed else None
            thumb_status = ("MISSING" if not thumb.is_file() else
                            "CHANGED" if sha256(thumb) != row["thumbnail_sha256"] else "OK")
            output.append({"id": row["id"], "source": status,
                           "managed": managed_status,
                           "thumbnail": thumb_status})
            db.execute("UPDATE photos SET source_missing = ? WHERE id = ?", (int(status == "MISSING"), row["id"]))
        db.commit()
        return output
    finally:
        db.close()


def relink_photo(data_dir: Path, photo_id: str, new_source: Path) -> None:
    """Point an existing ID at moved identical bytes; never move a source ourselves."""
    new_source = Path(new_source).resolve(strict=True)
    if not new_source.is_file():
        raise ImportErrorDetail("Replacement source is not a file")
    db = connect(data_dir)
    try:
        row = db.execute("SELECT sha256 FROM photos WHERE id = ?", (photo_id,)).fetchone()
        if row is None:
            raise ImportErrorDetail("Unknown photo ID")
        if sha256(new_source) != row["sha256"]:
            raise ImportErrorDetail("Replacement bytes do not match cataloged source")
        if db.execute("SELECT id FROM photos WHERE original_path = ? AND id != ?", (str(new_source), photo_id)).fetchone():
            raise ImportErrorDetail("Replacement path belongs to another photo")
        db.execute("UPDATE photos SET original_path = ?, original_filename = ?, source_missing = 0 WHERE id = ?",
                   (str(new_source), new_source.name, photo_id))
        db.commit()
    finally:
        db.close()
