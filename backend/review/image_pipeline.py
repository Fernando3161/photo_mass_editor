"""Immutable publication-sized image artifacts and their validation."""

from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from uuid import uuid4

from PIL import Image, ImageCms, ImageOps

from backend.catalog.ingestion import sha256, utc_now


class ImageIntegrityError(ValueError):
    """Source, profile, or derived bytes do not satisfy their recorded contract."""


def private_path(data_dir: Path, relative: str) -> Path:
    root = Path(data_dir).resolve()
    path = (root / relative).resolve()
    if root not in path.parents:
        raise ImageIntegrityError("Artifact path escapes the catalog directory")
    return path


def _exclusive_artifact(data_dir: Path, folder: str, suffix: str, payload: bytes) -> tuple[str, Path]:
    root = Path(data_dir).resolve()
    directory = root / folder
    directory.mkdir(parents=True, exist_ok=True)
    relative = f"{folder}/{uuid4().hex}{suffix}"
    target = private_path(root, relative)
    fd, temporary = tempfile.mkstemp(prefix=".artifact-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)  # Fails rather than replacing an existing artifact.
    finally:
        Path(temporary).unlink(missing_ok=True)
    return relative, target


def _rgb(image: Image.Image) -> Image.Image:
    try:
        image = ImageOps.exif_transpose(image)
    except (OSError, ValueError, TypeError, SyntaxError) as exc:
        raise ImageIntegrityError("Cannot apply source orientation") from exc
    icc = image.info.get("icc_profile")
    if icc:
        try:
            source_profile = ImageCms.ImageCmsProfile(BytesIO(icc))
            image = ImageCms.profileToProfile(
                image, source_profile, ImageCms.createProfile("sRGB"), outputMode="RGB"
            )
        except (OSError, ValueError, TypeError) as exc:
            raise ImageIntegrityError("Cannot convert embedded color profile to sRGB") from exc
    elif image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        white = Image.new("RGBA", rgba.size, "white")
        image = Image.alpha_composite(white, rgba).convert("RGB")
    else:
        image = image.convert("RGB")
    return image


def encode_publication(image: Image.Image, profile: dict) -> bytes:
    if (profile["image_format"] != "JPEG" or profile["color_space"] != "sRGB"
            or not profile["preserve_aspect_ratio"] or profile["allow_upscale"]
            or not profile["strip_metadata"] or not 1 <= profile["quality"] <= 100):
        raise ImageIntegrityError("Unsupported publication profile")
    clean = _rgb(image)
    clean.thumbnail((profile["max_long_edge"], profile["max_long_edge"]), Image.Resampling.LANCZOS)
    output = BytesIO()
    clean.save(output, format="JPEG", quality=profile["quality"], subsampling=0)
    return output.getvalue()


def validate_publication(path: Path, profile: dict, source_size: tuple[int, int] | None = None) -> tuple[int, int]:
    with Image.open(path) as image:
        image.load()
        width, height = image.size
        if image.format != "JPEG" or image.mode != "RGB":
            raise ImageIntegrityError("Publication artifact is not RGB JPEG")
        if max(image.size) > profile["max_long_edge"]:
            raise ImageIntegrityError("Publication artifact exceeds the profile long edge")
        if image.getexif() or image.info.get("icc_profile") or image.info.get("comment"):
            raise ImageIntegrityError("Publication artifact contains metadata")
        if source_size:
            oriented = source_size
            if max(image.size) > max(oriented):
                raise ImageIntegrityError("Publication artifact was upscaled")
            if abs(width / height - oriented[0] / oriented[1]) > 2 / min(width, height):
                raise ImageIntegrityError("Publication aspect ratio changed")
        return width, height


def ensure_publication_input(db: sqlite3.Connection, data_dir: Path, photo_id: str, profile: dict) -> dict:
    photo = db.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
    if photo is None:
        raise ImageIntegrityError("Photo is missing")
    source = Path(photo["original_path"])
    if not source.is_file() or sha256(source) != photo["sha256"]:
        raise ImageIntegrityError("Original photograph is missing or changed")
    existing = db.execute(
        """SELECT * FROM publication_inputs
           WHERE photo_id=? AND publication_profile_id=? AND source_hash=?""",
        (photo_id, profile["id"], photo["sha256"]),
    ).fetchone()
    if existing:
        path = private_path(data_dir, existing["path"])
        if (existing["status"] != "READY" or not path.is_file()
                or sha256(path) != existing["sha256"]):
            raise ImageIntegrityError("Recorded publication input is missing or changed; repair it before retrying")
        validate_publication(path, profile)
        return dict(existing)
    with Image.open(source) as original:
        oriented_size = ImageOps.exif_transpose(original).size
        payload = encode_publication(original, profile)
    relative, target = _exclusive_artifact(data_dir, "publication-inputs", ".jpg", payload)
    try:
        width, height = validate_publication(target, profile, oriented_size)
        if sha256(source) != photo["sha256"]:
            raise ImageIntegrityError("Original changed during derivation")
        record = {
            "id": str(uuid4()), "photo_id": photo_id, "publication_profile_id": profile["id"],
            "source_hash": photo["sha256"], "path": relative, "sha256": sha256(target),
            "width": width, "height": height, "image_format": "JPEG", "mime": "image/jpeg",
            "encoder_settings_json": json.dumps({"encoder": "Pillow", "quality": profile["quality"],
                                                  "subsampling": 0, "resample": "LANCZOS",
                                                  "color_management": "embedded ICC converted to sRGB; otherwise sRGB assumed",
                                                  "profile": profile}, sort_keys=True),
            "created_at": utc_now(), "status": "READY",
        }
        db.execute(
            """INSERT INTO publication_inputs(id,photo_id,publication_profile_id,source_hash,path,sha256,
               width,height,image_format,mime,encoder_settings_json,created_at,status)
               VALUES (:id,:photo_id,:publication_profile_id,:source_hash,:path,:sha256,:width,:height,
                       :image_format,:mime,:encoder_settings_json,:created_at,:status)""", record,
        )
        return record
    except Exception:
        target.unlink(missing_ok=True)
        raise


def verify_publication_input(db: sqlite3.Connection, data_dir: Path, input_id: str) -> tuple[dict, Path]:
    row = db.execute("SELECT * FROM publication_inputs WHERE id=?", (input_id,)).fetchone()
    if row is None or row["status"] != "READY":
        raise ImageIntegrityError("Publication input is unavailable")
    item = dict(row)
    path = private_path(data_dir, item["path"])
    if not path.is_file() or sha256(path) != item["sha256"]:
        raise ImageIntegrityError("Publication input hash mismatch")
    profile_row = db.execute("SELECT * FROM publication_profiles WHERE id=?", (item["publication_profile_id"],)).fetchone()
    if profile_row is None:
        raise ImageIntegrityError("Publication profile is missing")
    validate_publication(path, dict(profile_row))
    return item, path


def save_raw_attempt(data_dir: Path, payload: bytes, suffix: str) -> tuple[str, Path]:
    if suffix not in (".png", ".jpg", ".webp"):
        raise ImageIntegrityError("Unsupported raw output format")
    return _exclusive_artifact(data_dir, "edited/raw", suffix, payload)


def normalize_attempt(data_dir: Path, raw_path: Path, profile: dict, expected_size: tuple[int, int]) -> tuple[str, Path, int, int]:
    with Image.open(raw_path) as raw:
        raw.load()
        if abs(raw.width / raw.height - expected_size[0] / expected_size[1]) > 0.01:
            raise ImageIntegrityError("Provider output aspect ratio differs from the publication input")
        output_profile = {**profile, "max_long_edge": min(profile["max_long_edge"], max(expected_size))}
        payload = encode_publication(raw, output_profile)
    relative, target = _exclusive_artifact(data_dir, "edited/versions", ".jpg", payload)
    try:
        width, height = validate_publication(target, profile)
        if max(width, height) > max(expected_size):
            raise ImageIntegrityError("Normalized output was upscaled beyond the publication input")
        if abs(width / height - expected_size[0] / expected_size[1]) > 0.01:
            raise ImageIntegrityError("Normalized output aspect ratio differs from the publication input")
        return relative, target, width, height
    except Exception:
        target.unlink(missing_ok=True)
        raise
