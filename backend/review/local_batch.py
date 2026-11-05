"""Bounded, resumable receipts for selection-wide deterministic corrections."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
import re
from uuid import uuid4

from backend.catalog.database import connect
from backend.catalog.ingestion import utc_now
from . import local_corrections as local


@contextmanager
def _db(data_dir: Path):
    db = connect(data_dir)
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _operations(settings: dict) -> list[str]:
    return [key for key, value in settings.items()
            if key != "preset_id" and value != 0 and value != [0.0, 0.0, 1.0, 1.0]]


def named_recipes(data_dir: Path) -> list[dict]:
    with _db(data_dir) as db:
        return [{"id": row["id"], "name": row["name"], "settings": json.loads(row["settings_json"])}
                for row in db.execute("SELECT * FROM named_local_recipes ORDER BY name")]


def save_named_recipe(data_dir: Path, name: str, settings: dict) -> dict:
    name = name.strip()
    if not 1 <= len(name) <= 80:
        raise local.LocalCorrectionError("Recipe name must contain 1 to 80 characters")
    settings = local.validate_settings(settings)
    recipe_id = str(uuid4())
    with _db(data_dir) as db:
        if db.execute("SELECT 1 FROM named_local_recipes WHERE name=?", (name,)).fetchone():
            raise local.LocalCorrectionError("A named recipe already uses this name")
        db.execute("INSERT INTO named_local_recipes VALUES (?,?,?,?)",
                   (recipe_id, name, json.dumps(settings, sort_keys=True), utc_now()))
    return {"id": recipe_id, "name": name, "settings": settings}


def preview(data_dir: Path, photo_ids: list[str], recipe_id: str | None = None,
            overrides: dict[str, dict] | None = None, retry_override: bool = False,
            replace_approved: bool = False) -> dict:
    if not 1 <= len(photo_ids) <= 200 or len(set(photo_ids)) != len(photo_ids):
        raise local.LocalCorrectionError("Choose 1 to 200 distinct photos")
    overrides = overrides or {}
    if set(overrides) - set(photo_ids):
        raise local.LocalCorrectionError("Override photo is outside the selection")
    db = connect(data_dir)
    try:
        named = db.execute("SELECT settings_json FROM named_local_recipes WHERE id=?", (recipe_id,)).fetchone() if recipe_id else None
        if recipe_id and named is None:
            raise local.LocalCorrectionError("Named recipe does not exist")
        shared = json.loads(named[0]) if named else None
        items = []
        for photo_id in photo_ids:
            item = {"photo_id": photo_id, "eligible": False}
            try:
                photo, profile, _ = local._photo_and_profile(db, photo_id)
                approved = db.execute("SELECT id FROM image_versions WHERE photo_id=? AND review_status='APPROVED'", (photo_id,)).fetchone()
                replacement_id = approved["id"] if approved else None
                if approved and not replace_approved:
                    raise local.LocalCorrectionError("Already approved; enable explicit replacement")
                if replace_approved and not approved:
                    raise local.LocalCorrectionError("No approved version to replace")
                if db.execute("SELECT 1 FROM local_jobs WHERE photo_id=? AND status IN ('QUEUED','RUNNING')", (photo_id,)).fetchone() or db.execute("SELECT 1 FROM edit_jobs WHERE photo_id=? AND status IN ('QUEUED','RUNNING')", (photo_id,)).fetchone():
                    raise local.LocalCorrectionError("An edit is already active")
                settings = local.validate_settings(overrides[photo_id] if photo_id in overrides else shared or local._analyze(db, photo_id)["settings"])
                signature = _digest([photo["sha256"], profile["id"], profile["version"], settings, replacement_id])
                if not retry_override and db.execute("""SELECT 1 FROM local_jobs j JOIN image_versions v ON v.id=j.image_version_id
                    WHERE j.photo_id=? AND j.signature=? AND v.review_status='REJECTED'
                    AND v.superseded_by_version_id IS NULL""", (photo_id, signature)).fetchone():
                    raise local.LocalCorrectionError("Identical rejected recipe requires an override")
                item.update(eligible=True, settings=settings, revision=photo["revision"],
                            operations=_operations(settings), output_targets=["full-resolution PNG master", "website JPEG"],
                            replacement_of_version_id=replacement_id, source_hash=photo["sha256"],
                            profile_id=profile["id"])
            except (KeyError, local.LocalCorrectionError, local.ImageIntegrityError) as exc:
                item["reason"] = str(exc) if not isinstance(exc, KeyError) else "Photo not found"
            items.append(item)
        signature = _digest([items, recipe_id, retry_override, replace_approved])
        for item in items:
            item.pop("source_hash", None)
        return {"items": items, "signature": signature, "eligible_count": sum(item["eligible"] for item in items)}
    finally:
        db.close()


def enqueue(data_dir: Path, photo_ids: list[str], request_key: str, preview_signature: str,
            recipe_id: str | None = None, overrides: dict[str, dict] | None = None,
            retry_override: bool = False, replace_approved: bool = False) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", request_key):
        raise local.LocalCorrectionError("Invalid batch request key")
    request_signature = _digest([photo_ids, recipe_id, overrides or {}, retry_override, replace_approved, preview_signature])
    db = connect(data_dir)
    try:
        existing = db.execute("SELECT * FROM local_batches WHERE request_key=?", (request_key,)).fetchone()
        if existing:
            if existing["input_signature"] != request_signature:
                raise local.LocalCorrectionError("Batch request key was used for different inputs")
            return batch_status(data_dir, existing["id"])
    finally:
        db.close()
    plan = preview(data_dir, photo_ids, recipe_id, overrides, retry_override, replace_approved)
    if plan["signature"] != preview_signature:
        raise local.LocalCorrectionError("Selection or source changed; preview the batch again")
    if not plan["eligible_count"]:
        raise local.LocalCorrectionError("No photos are eligible for this local batch")
    batch_id = str(uuid4())
    with _db(data_dir) as db:
        db.execute("INSERT INTO local_batches VALUES (?,?,?,?,?,?)",
                   (batch_id, request_key, request_signature, json.dumps(plan["items"], sort_keys=True), utc_now(), "QUEUED"))
    # Each photo has its own immutable recipe/job. One failure cannot erase another receipt.
    for item in plan["items"]:
        if not item["eligible"]:
            continue
        try:
            job = local.enqueue(data_dir, item["photo_id"], item["settings"], item["revision"],
                                _digest([request_key, item["photo_id"]]), retry_override, replace_approved)
            with _db(data_dir) as db:
                db.execute("UPDATE local_jobs SET batch_id=? WHERE id=?", (batch_id, job["id"]))
        except (KeyError, local.LocalCorrectionError, local.ImageIntegrityError):
            # A concurrent change is reflected as skipped in the persisted plan.
            item["eligible"] = False
            item["reason"] = "Changed while queueing; preview before retrying"
    with _db(data_dir) as db:
        db.execute("UPDATE local_batches SET selection_json=? WHERE id=?", (json.dumps(plan["items"], sort_keys=True), batch_id))
    return batch_status(data_dir, batch_id)


def batch_status(data_dir: Path, batch_id: str) -> dict:
    db = connect(data_dir)
    try:
        row = db.execute("SELECT * FROM local_batches WHERE id=?", (batch_id,)).fetchone()
        if row is None:
            raise KeyError(batch_id)
        jobs = [local._public_job(job) for job in db.execute("SELECT * FROM local_jobs WHERE batch_id=? ORDER BY created_at,id", (batch_id,))]
        statuses = {job["status"] for job in jobs}
        status = "RUNNING" if statuses & {"QUEUED", "RUNNING"} else "CANCELLED" if jobs and statuses == {"CANCELLED"} else "COMPLETED"
        if status != row["status"]:
            db.execute("UPDATE local_batches SET status=? WHERE id=?", (status, batch_id))
            db.commit()
        return {"id": batch_id, "status": status, "items": json.loads(row["selection_json"]), "jobs": jobs}
    finally:
        db.close()


def recent_batches(data_dir: Path, limit: int = 10) -> list[dict]:
    db = connect(data_dir)
    try:
        ids = [row[0] for row in db.execute("SELECT id FROM local_batches ORDER BY created_at DESC,id DESC LIMIT ?", (limit,))]
    finally:
        db.close()
    return [batch_status(data_dir, batch_id) for batch_id in ids]


def cancel(data_dir: Path, batch_id: str) -> dict:
    with _db(data_dir) as db:
        if not db.execute("SELECT 1 FROM local_batches WHERE id=?", (batch_id,)).fetchone():
            raise KeyError(batch_id)
        db.execute("UPDATE local_jobs SET status='CANCELLED',completed_at=? WHERE batch_id=? AND status='QUEUED'", (utc_now(), batch_id))
    return batch_status(data_dir, batch_id)


def resume_queued(data_dir: Path) -> list[str]:
    with _db(data_dir) as db:
        db.execute("UPDATE local_jobs SET status='FAILED',completed_at=?,error='Interrupted while running; inspect artifacts before retrying' WHERE status='RUNNING'", (utc_now(),))
        db.execute("UPDATE local_jobs SET status='FAILED',completed_at=?,error='Interrupted single-photo correction; retry explicitly' WHERE status='QUEUED' AND batch_id IS NULL", (utc_now(),))
        return [row[0] for row in db.execute("SELECT id FROM local_jobs WHERE status='QUEUED' AND batch_id IS NOT NULL ORDER BY created_at,id")]
