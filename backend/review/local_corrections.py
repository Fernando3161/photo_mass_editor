"""Source-based, non-destructive local correction recipes and immutable outputs."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

import numpy as np
from PIL import Image, ImageFilter

from backend.catalog.database import connect
from backend.catalog.ingestion import sha256, utc_now
from .image_pipeline import (
    ImageIntegrityError, _exclusive_artifact, _rgb, encode_publication, private_path,
    validate_publication,
)


ANALYSIS_VERSION = "local-auto-v2-01"
PRESETS = {
    "natural": ("Natural balance", .35, .42),
    "architecture": ("Architecture detail", .45, .46),
    "landscape": ("Landscape", .40, .45),
    "night": ("Night scene", .18, .27),
    "artwork": ("Artwork and sculpture", .15, .43),
    "people": ("People", .23, .43),
}


class LocalCorrectionError(ValueError):
    pass


def _photo_and_profile(db: sqlite3.Connection, photo_id: str, *, verify_source: bool = True):
    photo = db.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
    if photo is None:
        raise KeyError(photo_id)
    profile = db.execute(
        """SELECT p.* FROM publication_profiles p
           LEFT JOIN review_drafts d ON d.photo_id=?
           WHERE p.id=COALESCE(d.publication_profile_id,'website-standard-v1') AND p.active=1""",
        (photo_id,),
    ).fetchone()
    if profile is None:
        raise LocalCorrectionError("An active publication profile is required")
    source = Path(photo["original_path"])
    if not source.is_file() or (verify_source and sha256(source) != photo["sha256"]):
        raise ImageIntegrityError("Original photograph is missing or changed")
    return photo, dict(profile), source


@lru_cache(maxsize=8)
def _interactive_source(path_value: str, expected_hash: str, size: int,
                        modified_ns: int) -> Image.Image:
    """Return a verified, oriented working image keyed by source identity and file stat."""
    source = Path(path_value)
    before = source.stat()
    if before.st_size != size or before.st_mtime_ns != modified_ns or sha256(source) != expected_hash:
        raise ImageIntegrityError("Original photograph is missing or changed")
    with Image.open(source) as opened:
        sample = _rgb(opened)
        sample.thumbnail((960, 960), Image.Resampling.LANCZOS)
        sample.load()
    after = source.stat()
    if after.st_size != size or after.st_mtime_ns != modified_ns:
        raise ImageIntegrityError("Original changed while preparing the interactive preview")
    return sample


def _choose_preset(db: sqlite3.Connection, photo_id: str, median: float) -> str:
    draft = db.execute("SELECT preset_id FROM review_drafts WHERE photo_id=?", (photo_id,)).fetchone()
    named = draft["preset_id"] if draft else ""
    if named in ("museum-artwork", "museum-art", "artwork"):
        return "artwork"
    if named in ("group-photos", "group-photo", "portrait-gentle", "people"):
        return "people"
    if named in ("night-architecture", "night-scene") or median < .25:
        return "night"
    if named in ("architecture-clarity", "architecture"):
        return "architecture"
    if named in ("landscape", "panoramic-scenes", "panoramic-scene", "panorama"):
        return "landscape"
    return "natural"


def _analyze(db: sqlite3.Connection, photo_id: str, preset_override: str | None = None) -> dict:
    photo, profile, source = _photo_and_profile(db, photo_id)
    with Image.open(source) as opened:
        oriented = _rgb(opened)
        oriented.thumbnail((512, 512), Image.Resampling.LANCZOS)
        sample = np.asarray(oriented, dtype=np.float32) / 255.0
    luminance = sample @ np.array([.2126, .7152, .0722], dtype=np.float32)
    low, median, high = (float(x) for x in np.quantile(luminance, [.01, .5, .99]))
    preset_id = preset_override or _choose_preset(db, photo_id, median)
    if preset_id not in PRESETS:
        raise LocalCorrectionError("Unknown local correction preset")
    _, strength, target_median = PRESETS[preset_id]
    is_night = preset_id == "night"
    is_art = preset_id == "artwork"
    exposure = max(-.4, min(.4, math.log2(target_median / max(.08, median))))
    if is_night:
        exposure = max(-.15, min(.2, exposure))
    mids = sample[(luminance > .15) & (luminance < .85)]
    if mids.size and not (is_night or is_art):
        means = mids.mean(axis=0)
        red_gain = max(.94, min(1.06, float(means[1] / max(.05, means[0]))))
        blue_gain = max(.94, min(1.06, float(means[1] / max(.05, means[2]))))
    else:
        red_gain = blue_gain = 1.0
    settings = {
        "preset_id": preset_id,
        "levels_strength": round(strength if high - low > .12 else 0.0, 3),
        "black_point": round(max(0.0, min(.08, low)), 4),
        "white_point": round(max(.88, min(1.0, high)), 4),
        "exposure_ev": round(exposure, 3),
        "red_gain": round(red_gain, 3),
        "blue_gain": round(blue_gain, 3),
        "shadow_lift": round(min(.18, max(0.0, (.32 - low) * .35)) if not is_night else .02, 3),
        "highlight_compression": round(min(.2, max(0.0, (high - .88) * .9)), 3),
        "denoise": 0,
        "sharpen": 0.0,
        "straighten_deg": 0.0,
        "lens_k1": 0.0,
        "perspective_vertical": 0.0,
        "crop": [0.0, 0.0, 1.0, 1.0],
    }
    measurements = {
        "luminance_p01": round(low, 4), "luminance_median": round(median, 4),
        "luminance_p99": round(high, 4), "sample_width": int(sample.shape[1]),
        "sample_height": int(sample.shape[0]),
        "geometry_note": "No reliable horizon, lens profile, or perspective measurement; geometry stays unchanged.",
        "white_balance_note": "Conservative midtone estimate; neutral for night and artwork.",
    }
    if sha256(source) != photo["sha256"]:
        raise ImageIntegrityError("Original changed during local analysis")
    return {"photo_id": photo_id, "photo_revision": photo["revision"],
            "profile_id": profile["id"], "preset_id": preset_id,
            "preset_name": PRESETS[preset_id][0], "presets": [
                {"id": key, "name": value[0]} for key, value in PRESETS.items()],
            "analysis_version": ANALYSIS_VERSION, "measurements": measurements,
            "settings": settings}


def recommend(data_dir: Path, photo_id: str, preset_id: str | None = None) -> dict:
    db = connect(data_dir)
    try:
        return _analyze(db, photo_id, preset_id)
    finally:
        db.close()


def validate_settings(value: dict) -> dict:
    ranges = {
        "levels_strength": (0, 1), "black_point": (0, .2), "white_point": (.8, 1),
        "exposure_ev": (-1, 1), "red_gain": (.85, 1.15), "blue_gain": (.85, 1.15),
        "shadow_lift": (0, .4), "highlight_compression": (0, .4),
        "denoise": (0, 2), "sharpen": (0, 1), "straighten_deg": (-10, 10),
        "lens_k1": (-.12, .12), "perspective_vertical": (-.2, .2),
    }
    if set(value) != set(ranges) | {"crop", "preset_id"} or value.get("preset_id") not in PRESETS:
        raise LocalCorrectionError("Local recipe fields or preset are invalid")
    result = {"preset_id": value["preset_id"]}
    for key, (minimum, maximum) in ranges.items():
        number = value[key]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or not minimum <= number <= maximum:
            raise LocalCorrectionError(f"Invalid local recipe value: {key}")
        if key == "denoise" and int(number) != number:
            raise LocalCorrectionError("Denoise must be a whole number")
        result[key] = int(number) if key == "denoise" else float(number)
    crop = value["crop"]
    if (not isinstance(crop, list) or len(crop) != 4
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in crop)):
        raise LocalCorrectionError("Crop must have four normalized coordinates")
    left, top, right, bottom = crop
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1 and right - left >= .5 and bottom - top >= .5):
        raise LocalCorrectionError("Crop must stay within the image and retain at least half of each dimension")
    if result["black_point"] >= result["white_point"] - .3:
        raise LocalCorrectionError("Black and white points are too close")
    result["crop"] = [float(v) for v in crop]
    return result


def _lens(image: Image.Image, k1: float) -> Image.Image:
    if not k1:
        return image
    width, height = image.size
    scale = 1 / (1 + max(k1, 0))

    def mapped(x: float, y: float) -> tuple[float, float]:
        dx = (x - width / 2) / (width / 2)
        dy = (y - height / 2) / (height / 2)
        factor = (1 + k1 * (dx * dx + dy * dy) / 2) * scale
        return width / 2 + dx * factor * width / 2, height / 2 + dy * factor * height / 2

    mesh = []
    step = 96
    for y0 in range(0, height, step):
        for x0 in range(0, width, step):
            x1, y1 = min(width, x0 + step), min(height, y0 + step)
            a, b, c, d = mapped(x0, y0), mapped(x0, y1), mapped(x1, y1), mapped(x1, y0)
            mesh.append(((x0, y0, x1, y1), (*a, *b, *c, *d)))
    return image.transform(image.size, Image.Transform.MESH, mesh, resample=Image.Resampling.BICUBIC)


def apply_recipe(source: Image.Image, settings: dict) -> Image.Image:
    """Apply float32 tonal math in stripes, then explicit geometry at source resolution."""
    settings = validate_settings(settings)
    image = _rgb(source)
    if settings["denoise"]:
        image = image.filter(ImageFilter.MedianFilter(size=3 if settings["denoise"] == 1 else 5))
    output = Image.new("RGB", image.size)
    black, white = settings["black_point"], settings["white_point"]
    gains = np.array([settings["red_gain"], 1.0, settings["blue_gain"]], dtype=np.float32)
    for y in range(0, image.height, 256):
        lower = min(image.height, y + 256)
        pixels = np.asarray(image.crop((0, y, image.width, lower)), dtype=np.float32) / 255.0
        leveled = np.clip((pixels - black) / (white - black), 0, 1)
        pixels += (leveled - pixels) * settings["levels_strength"]
        pixels *= gains
        pixels *= 2 ** settings["exposure_ev"]
        lum = pixels @ np.array([.2126, .7152, .0722], dtype=np.float32)
        lum = np.clip(lum, 0, 1)
        offset = (settings["shadow_lift"] * (1 - lum) ** 2
                  - settings["highlight_compression"] * lum ** 2) * .25
        pixels = np.clip(pixels + offset[:, :, None], 0, 1)
        output.paste(Image.fromarray(np.uint8(np.rint(pixels * 255)), "RGB"), (0, y))
    if settings["sharpen"]:
        output = output.filter(ImageFilter.UnsharpMask(radius=1.3, percent=int(settings["sharpen"] * 90), threshold=3))
    output = _lens(output, settings["lens_k1"])
    perspective = settings["perspective_vertical"]
    if perspective:
        w, h = output.size
        inset = abs(perspective) * w
        top = inset if perspective > 0 else 0
        bottom = inset if perspective < 0 else 0
        output = output.transform((w, h), Image.Transform.QUAD,
                                  (top, 0, bottom, h, w - bottom, h, w - top, 0),
                                  resample=Image.Resampling.BICUBIC)
    angle = settings["straighten_deg"]
    if angle:
        w, h = output.size
        theta = math.radians(abs(angle))
        safe_w = int(w * math.cos(theta) - h * math.sin(theta))
        safe_h = int(h * math.cos(theta) - w * math.sin(theta))
        if safe_w < w * .5 or safe_h < h * .5:
            raise LocalCorrectionError("Straighten would crop too much of this aspect ratio")
        output = output.rotate(angle, resample=Image.Resampling.BICUBIC)
        left, top = (w - safe_w) // 2, (h - safe_h) // 2
        output = output.crop((left, top, left + safe_w, top + safe_h))
    left, top, right, bottom = settings["crop"]
    w, h = output.size
    box = (int(left * w), int(top * h), int(right * w), int(bottom * h))
    if box[2] <= box[0] or box[3] <= box[1]:
        raise LocalCorrectionError("Crop is empty at this image resolution")
    return output.crop(box)


def preview(data_dir: Path, photo_id: str, settings: dict) -> bytes:
    settings = validate_settings(settings)
    db = connect(data_dir)
    try:
        photo, _, source = _photo_and_profile(db, photo_id, verify_source=False)
        source_stat = source.stat()
        sample = _interactive_source(
            str(source.resolve()), photo["sha256"], source_stat.st_size, source_stat.st_mtime_ns,
        ).copy()
        result = apply_recipe(sample, settings)
        payload = BytesIO()
        result.save(payload, format="JPEG", quality=85)
        final_stat = source.stat()
        if (final_stat.st_size != source_stat.st_size
                or final_stat.st_mtime_ns != source_stat.st_mtime_ns):
            raise ImageIntegrityError("Original changed during local preview")
        return payload.getvalue()
    finally:
        db.close()


def _public_job(row: sqlite3.Row | dict) -> dict:
    item = dict(row)
    return {key: item[key] for key in (
        "id", "photo_id", "recipe_id", "status", "image_version_id", "created_at",
        "started_at", "completed_at", "error", "master_width", "master_height",
        "replacement_of_version_id",
    )} | {"error": "Local correction failed; inspect the private job receipt" if item["error"] else None}


def enqueue(data_dir: Path, photo_id: str, settings: dict, expected_revision: int,
            request_key: str, retry_override: bool = False, replace_approved: bool = False) -> dict:
    settings = validate_settings(settings)
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", request_key):
        raise LocalCorrectionError("Invalid request key")
    db = connect(data_dir)
    try:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT * FROM local_jobs WHERE request_key=?", (request_key,)).fetchone()
        if existing:
            recipe = db.execute("SELECT settings_json FROM local_recipes WHERE id=?", (existing["recipe_id"],)).fetchone()
            if (existing["photo_id"] != photo_id or json.loads(recipe[0]) != settings
                    or bool(existing["replacement_of_version_id"]) != replace_approved):
                raise LocalCorrectionError("Request key was used for different local inputs")
            db.commit()
            return _public_job(existing)
        photo, profile, _ = _photo_and_profile(db, photo_id)
        if photo["revision"] != expected_revision:
            raise LocalCorrectionError("Photo metadata changed; reload the local recommendation")
        approved = db.execute(
            "SELECT id FROM image_versions WHERE photo_id=? AND review_status='APPROVED'", (photo_id,)
        ).fetchone()
        if approved and not replace_approved:
            raise LocalCorrectionError("Photo already has an approved version")
        if replace_approved and not approved:
            raise LocalCorrectionError("No approved version exists to replace")
        replacement_id = approved["id"] if approved else None
        if db.execute("SELECT 1 FROM local_jobs WHERE photo_id=? AND status IN ('QUEUED','RUNNING')", (photo_id,)).fetchone():
            raise LocalCorrectionError("A local correction is already running")
        if db.execute("SELECT 1 FROM edit_jobs WHERE photo_id=? AND status IN ('QUEUED','RUNNING')", (photo_id,)).fetchone():
            raise LocalCorrectionError("An image edit is already running")
        recommendation = _analyze(db, photo_id, settings["preset_id"])
        signature = hashlib.sha256(json.dumps(
            [photo["sha256"], profile["id"], profile["version"], settings, replacement_id],
            sort_keys=True).encode()).hexdigest()
        rejected = db.execute(
            """SELECT 1 FROM local_jobs j JOIN image_versions v ON v.id=j.image_version_id
               WHERE j.photo_id=? AND j.signature=? AND v.review_status='REJECTED'
                 AND v.superseded_by_version_id IS NULL""",
            (photo_id, signature),
        ).fetchone()
        if rejected and not retry_override:
            raise LocalCorrectionError("Identical rejected local recipe requires a change or explicit retry")
        recipe_id, job_id, now = str(uuid4()), str(uuid4()), utc_now()
        number = db.execute("SELECT COALESCE(MAX(version_number),0)+1 FROM local_recipes WHERE photo_id=?", (photo_id,)).fetchone()[0]
        db.execute(
            """INSERT INTO local_recipes(id,photo_id,version_number,source_hash,photo_revision,
               publication_profile_id,profile_snapshot_json,preset_id,analysis_version,measurements_json,
               recommended_json,settings_json,user_modified,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (recipe_id, photo_id, number, photo["sha256"], photo["revision"], profile["id"],
             json.dumps(profile, sort_keys=True), settings["preset_id"], ANALYSIS_VERSION,
             json.dumps(recommendation["measurements"], sort_keys=True),
             json.dumps(recommendation["settings"], sort_keys=True), json.dumps(settings, sort_keys=True),
             int(settings != recommendation["settings"]), now),
        )
        db.execute("""INSERT INTO local_jobs(id,photo_id,recipe_id,source_hash,signature,request_key,
                      replacement_of_version_id,status,created_at)
                      VALUES (?,?,?,?,?,?,?,'QUEUED',?)""",
                   (job_id, photo_id, recipe_id, photo["sha256"], signature, request_key,
                    replacement_id, now))
        db.commit()
        return _public_job(db.execute("SELECT * FROM local_jobs WHERE id=?", (job_id,)).fetchone())
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_job(data_dir: Path, job_id: str) -> dict:
    db = connect(data_dir)
    try:
        db.execute("BEGIN IMMEDIATE")
        claimed = db.execute("UPDATE local_jobs SET status='RUNNING',started_at=? WHERE id=? AND status='QUEUED'",
                             (utc_now(), job_id))
        row = db.execute("SELECT * FROM local_jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        db.commit()
        if claimed.rowcount != 1:
            return _public_job(row)
        recipe = db.execute("SELECT * FROM local_recipes WHERE id=?", (row["recipe_id"],)).fetchone()
        photo, profile, source = _photo_and_profile(db, row["photo_id"])
        if (row["source_hash"] != photo["sha256"] or recipe["source_hash"] != photo["sha256"]
                or recipe["photo_revision"] != photo["revision"]
                or json.loads(recipe["profile_snapshot_json"]) != profile):
            raise ImageIntegrityError("Local source or recipe changed after queueing")
        with Image.open(source) as opened:
            corrected = apply_recipe(opened, json.loads(recipe["settings_json"]))
            master_size = corrected.size
            master_bytes = BytesIO()
            corrected.save(master_bytes, format="PNG", optimize=False)
            web_bytes = encode_publication(corrected, profile)
        if sha256(source) != photo["sha256"]:
            raise ImageIntegrityError("Original changed during local correction")
        master_rel, master_path = _exclusive_artifact(data_dir, "edited/masters", ".png", master_bytes.getvalue())
        db.execute("UPDATE local_jobs SET master_path=?,master_sha256=?,master_width=?,master_height=? WHERE id=?",
                   (master_rel, sha256(master_path), *master_size, job_id))
        db.commit()
        web_rel, web_path = _exclusive_artifact(data_dir, "edited/versions", ".jpg", web_bytes)
        web_size = validate_publication(web_path, profile, master_size)
        db.execute("BEGIN IMMEDIATE")
        latest = db.execute("SELECT revision,sha256 FROM photos WHERE id=?", (row["photo_id"],)).fetchone()
        current_profile = db.execute("SELECT * FROM publication_profiles WHERE id=?", (profile["id"],)).fetchone()
        if (latest is None or latest["revision"] != recipe["photo_revision"]
                or latest["sha256"] != recipe["source_hash"]
                or current_profile is None or dict(current_profile) != profile
                or sha256(source) != recipe["source_hash"]):
            raise ImageIntegrityError("Local source, metadata, or profile changed during correction")
        approved = db.execute(
            "SELECT id FROM image_versions WHERE photo_id=? AND review_status='APPROVED'",
            (row["photo_id"],),
        ).fetchone()
        if row["replacement_of_version_id"]:
            if approved is None or approved["id"] != row["replacement_of_version_id"]:
                raise LocalCorrectionError("The approved version changed while the replacement ran")
        elif approved:
            raise LocalCorrectionError("Photo was approved while local correction ran")
        number = db.execute("SELECT COALESCE(MAX(version_number),0)+1 FROM image_versions WHERE photo_id=?",
                            (row["photo_id"],)).fetchone()[0]
        version_id = str(uuid4())
        db.execute("""INSERT INTO image_versions(id,photo_id,version_number,path,sha256,width,height,created_at,
                      review_status,local_job_id,mime) VALUES (?,?,?,?,?,?,?,?,'PENDING',?,'image/jpeg')""",
                   (version_id, row["photo_id"], number, web_rel, sha256(web_path), *web_size, utc_now(), job_id))
        db.execute("UPDATE local_jobs SET status='SUCCEEDED',image_version_id=?,completed_at=? WHERE id=?",
                   (version_id, utc_now(), job_id))
        db.commit()
    except Exception as exc:
        db.rollback()
        db.execute("UPDATE local_jobs SET status='FAILED',error=?,completed_at=? WHERE id=? AND status='RUNNING'",
                   (str(exc)[:1000], utc_now(), job_id))
        db.commit()
    finally:
        db.close()
    return job_status(data_dir, job_id)


def job_status(data_dir: Path, job_id: str) -> dict:
    db = connect(data_dir)
    try:
        row = db.execute("SELECT * FROM local_jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return _public_job(row)
    finally:
        db.close()


def list_jobs(data_dir: Path, photo_id: str) -> list[dict]:
    db = connect(data_dir)
    try:
        return [_public_job(row) for row in db.execute(
            "SELECT * FROM local_jobs WHERE photo_id=? ORDER BY created_at DESC", (photo_id,))]
    finally:
        db.close()


def master_media(data_dir: Path, photo_id: str, version_id: str) -> Path:
    db = connect(data_dir)
    try:
        row = db.execute("""SELECT j.master_path,j.master_sha256 FROM image_versions v
                            JOIN local_jobs j ON j.id=v.local_job_id
                            WHERE v.id=? AND v.photo_id=? AND j.status='SUCCEEDED'""",
                         (version_id, photo_id)).fetchone()
        if row is None:
            raise KeyError(version_id)
        path = private_path(data_dir, row["master_path"])
        if not path.is_file() or sha256(path) != row["master_sha256"]:
            raise ImageIntegrityError("Full-resolution master is missing or changed")
        return path
    finally:
        db.close()


def recover_jobs(data_dir: Path) -> None:
    db = connect(data_dir)
    try:
        db.execute("""UPDATE local_jobs SET status='FAILED',completed_at=?,
                      error='Interrupted local correction; inspect artifacts before retrying'
                      WHERE status IN ('QUEUED','RUNNING')""", (utc_now(),))
        db.commit()
    finally:
        db.close()
