"""Explicitly authorized, resumable local edit jobs and version review."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import sqlite3
import re
from typing import Protocol
from uuid import uuid4

from PIL import Image, ImageEnhance, ImageFilter

from backend.catalog.database import connect
from backend.catalog.ingestion import sha256, utc_now
from .costs import PaidRequestError, calculate
from .image_pipeline import (
    ImageIntegrityError, _exclusive_artifact, ensure_publication_input, normalize_attempt, private_path,
    save_raw_attempt, verify_publication_input,
)


@dataclass(frozen=True)
class EditResult:
    image_bytes: bytes
    suffix: str
    model: str
    usage: dict
    actual_cost_usd: Decimal | None = None
    request_id: str | None = None


class EditProvider(Protocol):
    model: str
    estimated_cost_usd: Decimal | None

    def edit(self, publication_input: Path, prompt: str, mask: Path | None) -> EditResult: ...


class UnavailableEditProvider:
    model = "unavailable"
    estimated_cost_usd = None

    def edit(self, publication_input: Path, prompt: str, mask: Path | None) -> EditResult:
        raise RuntimeError("No editing provider is configured; no API call was made")


class EditConflict(ValueError):
    pass


def save_mask(data_dir: Path, photo_id: str, payload: bytes) -> dict:
    if not payload or len(payload) >= 4 * 1024 * 1024:
        raise EditConflict("Mask must be a nonempty PNG smaller than 4 MB")
    db = connect(data_dir)
    try:
        has_approved = db.execute(
            "SELECT 1 FROM image_versions WHERE photo_id=? AND review_status='APPROVED'", (photo_id,)
        ).fetchone() is not None
        prompt, profile, _ = _eligible(db, photo_id, has_approved)
        artifact = ensure_publication_input(db, data_dir, photo_id, profile)
        with Image.open(BytesIO(payload)) as image:
            image.load()
            if image.format != "PNG" or image.mode not in ("RGBA", "LA"):
                raise EditConflict("Mask must be a PNG with an alpha channel")
            if image.size != (artifact["width"], artifact["height"]):
                raise EditConflict("Mask dimensions must match the publication input")
            low, high = image.getchannel("A").getextrema()
            if low != 0 or high == 0:
                raise EditConflict("Mask must include both transparent edit pixels and opaque protected pixels")
        relative, path = _exclusive_artifact(data_dir, "masks", ".png", payload)
        try:
            result = {"id": str(uuid4()), "photo_id": photo_id, "publication_input_id": artifact["id"],
                      "path": relative, "sha256": sha256(path), "width": artifact["width"],
                      "height": artifact["height"], "created_at": utc_now()}
            db.execute(
                """INSERT INTO masks(id,photo_id,publication_input_id,path,sha256,width,height,created_at)
                   VALUES (:id,:photo_id,:publication_input_id,:path,:sha256,:width,:height,:created_at)""", result,
            )
            db.commit()
            return {key: result[key] for key in ("id", "width", "height", "created_at")}
        except Exception:
            path.unlink(missing_ok=True)
            raise
    finally:
        db.close()


def _profile(db: sqlite3.Connection, prompt: sqlite3.Row) -> dict:
    saved = json.loads(prompt["publication_profile_snapshot_json"])
    current = db.execute("SELECT * FROM publication_profiles WHERE id=? AND active=1", (saved["id"],)).fetchone()
    if current is None or any(current[key] != value for key, value in saved.items() if key in current.keys()):
        raise EditConflict("Approved prompt publication profile no longer matches the active profile")
    return saved


def _eligible(db: sqlite3.Connection, photo_id: str,
              replace_approved: bool = False) -> tuple[sqlite3.Row, dict, str | None]:
    prompt = db.execute(
        """SELECT cp.* FROM compiled_prompts cp JOIN review_drafts d ON d.photo_id=cp.photo_id
           JOIN photos p ON p.id=cp.photo_id
           WHERE cp.photo_id=? AND cp.approved_for_job=1 AND d.compiled_prompt_stale=0
             AND cp.source_hash=p.sha256 AND cp.photo_revision=p.revision
             AND cp.draft_revision=d.revision AND cp.publication_profile_id=d.publication_profile_id""",
        (photo_id,),
    ).fetchone()
    if prompt is None:
        raise EditConflict("Save and approve a current compiled prompt before editing")
    approved = db.execute(
        "SELECT id FROM image_versions WHERE photo_id=? AND review_status='APPROVED'", (photo_id,)
    ).fetchone()
    if approved and not replace_approved:
        raise EditConflict("Photo already has an approved version")
    if replace_approved and not approved:
        raise EditConflict("No approved version exists to replace")
    active = db.execute(
        "SELECT id FROM edit_jobs WHERE photo_id=? AND status IN ('QUEUED','RUNNING')", (photo_id,)
    ).fetchone()
    if active:
        raise EditConflict("Photo already has an active edit job")
    return prompt, _profile(db, prompt), approved["id"] if approved else None


def _settings(engine: str, settings: dict) -> dict:
    if engine == "DETERMINISTIC":
        allowed = {"exposure", "contrast", "color", "sharpness", "denoise"}
        if set(settings) - allowed:
            raise EditConflict("Unsupported deterministic setting")
        result = {"exposure": 1.0, "contrast": 1.0, "color": 1.0, "sharpness": 1.0, "denoise": 0.0}
        result.update(settings)
        for key, value in result.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= (5 if key == "denoise" else 2):
                raise EditConflict(f"Invalid {key} setting")
        return result
    if engine == "GENERATIVE":
        if settings:
            raise EditConflict("Generative settings are fixed by the server-side provider configuration")
        return {}
    raise EditConflict("Unknown edit engine")


def _signature(prompt_id: str, input_hash: str, engine: str, model: str | None, settings: dict, mask_hash: str | None) -> str:
    data = json.dumps([prompt_id, input_hash, engine, model, settings, mask_hash], sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()


def preview_batch(data_dir: Path, photo_ids: list[str], engine: str, provider: EditProvider,
                  settings: dict | None = None, mask_id: str | None = None,
                  retry_override: bool = False, replace_approved: bool = False) -> dict:
    if not 1 <= len(photo_ids) <= 20 or len(set(photo_ids)) != len(photo_ids):
        raise EditConflict("Choose 1 to 20 distinct photos")
    settings = _settings(engine, settings or {})
    db = connect(data_dir)
    try:
        items = []
        for photo_id in photo_ids:
            try:
                prompt, profile, replacement_id = _eligible(db, photo_id, replace_approved)
                source = db.execute("SELECT original_path,sha256 FROM photos WHERE id=?", (photo_id,)).fetchone()
                if source is None or not Path(source["original_path"]).is_file() or sha256(Path(source["original_path"])) != source["sha256"]:
                    raise EditConflict("Original photograph is missing or changed")
                artifact = db.execute(
                    """SELECT * FROM publication_inputs WHERE photo_id=? AND publication_profile_id=?
                       AND source_hash=?""", (photo_id, profile["id"], source["sha256"])
                ).fetchone()
                if artifact:
                    if not private_path(data_dir, artifact["path"]).is_file() or sha256(private_path(data_dir, artifact["path"])) != artifact["sha256"]:
                        raise EditConflict("Recorded publication input is missing or changed")
                    mask_hash = None
                    if mask_id:
                        mask = db.execute("SELECT * FROM masks WHERE id=? AND photo_id=? AND publication_input_id=?",
                                          (mask_id, photo_id, artifact["id"])).fetchone()
                        if mask is None:
                            raise EditConflict("Mask does not match this publication input")
                        mask_hash = mask["sha256"]
                    signature = _signature(prompt["id"], artifact["sha256"], engine,
                                           provider.model if engine == "GENERATIVE" else None, settings, mask_hash)
                    rejected = db.execute(
                        """SELECT j.id FROM edit_jobs j JOIN image_versions v ON v.id=j.image_version_id
                           WHERE j.photo_id=? AND j.signature=? AND v.review_status='REJECTED'
                             AND v.superseded_by_version_id IS NULL""",
                        (photo_id, signature),
                    ).fetchone()
                    if rejected and not retry_override:
                        raise EditConflict("Identical rejected attempt requires changed instructions or explicit retry override")
                items.append({"photo_id": photo_id, "eligible": True,
                              "prompt_id": prompt["id"], "prompt_version": prompt["version_number"],
                              "prompt_text": prompt["compiled_text"], "profile": profile,
                              "replacement_of_version_id": replacement_id})
            except EditConflict as exc:
                items.append({"photo_id": photo_id, "eligible": False, "reason": str(exc)})
        estimate = provider.estimated_cost_usd if engine == "GENERATIVE" else Decimal("0")
        if engine == "GENERATIVE" and isinstance(provider, UnavailableEditProvider):
            availability = "No editing provider is configured; no API call can be made"
        else:
            availability = "ready"
        return {"items": items, "engine": engine, "model": provider.model if engine == "GENERATIVE" else None,
                "estimated_cost_usd": str(estimate * sum(item["eligible"] for item in items)) if estimate is not None else None,
                "cost_note": "Estimate only; provider charges can differ. No automatic account spending cap.",
                "availability": availability}
    finally:
        db.close()


def enqueue_batch(data_dir: Path, photo_ids: list[str], engine: str, settings: dict,
                  provider: EditProvider, *, authorized: bool, budget_usd: Decimal | None,
                  request_key: str, retry_override: bool = False, mask_id: str | None = None,
                  replace_approved: bool = False) -> list[dict]:
    if not authorized:
        raise PermissionError("Authorize this edit run explicitly")
    if not 1 <= len(photo_ids) <= 20 or len(set(photo_ids)) != len(photo_ids):
        raise EditConflict("Choose 1 to 20 distinct photos")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", request_key):
        raise EditConflict("Request key must contain only letters, numbers, underscores, or hyphens")
    if engine == "GENERATIVE":
        if isinstance(provider, UnavailableEditProvider):
            raise EditConflict("No editing provider is configured; no API call was made")
        if provider.estimated_cost_usd is None:
            raise EditConflict("Provider cost estimate is unavailable; configure a per-image planning amount first")
        estimated = provider.estimated_cost_usd * len(photo_ids)
        if budget_usd is None or budget_usd < estimated:
            raise EditConflict("Run budget is below the estimated cost")
    if mask_id and (engine != "GENERATIVE" or len(photo_ids) != 1):
        raise EditConflict("A mask can only be used with a single generative photo")
    settings = _settings(engine, settings)
    db = connect(data_dir)
    try:
        db.execute("BEGIN IMMEDIATE")
        existing = [dict(row) for row in db.execute(
            "SELECT * FROM edit_jobs WHERE request_key LIKE ? ORDER BY created_at", (request_key + ":%",)
        )]
        if existing:
            if ({row["photo_id"] for row in existing} != set(photo_ids)
                    or any(row["engine"] != engine or json.loads(row["settings_json"]) != settings
                           or row["mask_id"] != mask_id
                           or bool(row["replacement_of_version_id"]) != replace_approved
                           for row in existing)):
                raise EditConflict("Request key was used for different edit inputs")
            db.commit()
            return [_public_job(row) for row in existing]
        batch_id = str(uuid4())
        now = utc_now()
        db.execute(
            """INSERT INTO edit_batches(id,created_at,engine,status,selection_json,authorized_at,budget_usd)
               VALUES (?,?,?,?,?,?,?)""",
            (batch_id, now, engine, "QUEUED", json.dumps(photo_ids), now,
             float(budget_usd) if budget_usd is not None else None),
        )
        jobs = []
        for photo_id in photo_ids:
            prompt, profile, replacement_id = _eligible(db, photo_id, replace_approved)
            artifact = ensure_publication_input(db, data_dir, photo_id, profile)
            selected_mask = None
            mask_hash = None
            if mask_id:
                selected_mask = db.execute(
                    "SELECT * FROM masks WHERE id=? AND photo_id=? AND publication_input_id=?",
                    (mask_id, photo_id, artifact["id"]),
                ).fetchone()
                if selected_mask is None:
                    raise EditConflict("Mask does not match this publication input")
                mask_path = private_path(data_dir, selected_mask["path"])
                if not mask_path.is_file() or sha256(mask_path) != selected_mask["sha256"]:
                    raise ImageIntegrityError("Mask is missing or changed")
                mask_hash = selected_mask["sha256"]
            model = provider.model if engine == "GENERATIVE" else None
            signature = _signature(prompt["id"], artifact["sha256"], engine, model, settings, mask_hash)
            rejected = db.execute(
                """SELECT j.id FROM edit_jobs j JOIN image_versions v ON v.id=j.image_version_id
                   WHERE j.photo_id=? AND j.signature=? AND v.review_status='REJECTED'
                     AND v.superseded_by_version_id IS NULL""",
                (photo_id, signature),
            ).fetchone()
            if rejected and not retry_override:
                raise EditConflict("Identical rejected attempt requires changed instructions or explicit retry override")
            job_id = str(uuid4())
            db.execute(
                """INSERT INTO edit_jobs(id,batch_id,photo_id,compiled_prompt_id,publication_input_id,
                   publication_input_hash,engine,model,settings_json,mask_id,signature,request_key,
                   replacement_of_version_id,status,
                   estimated_cost_usd,authorized_at,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (job_id, batch_id, photo_id, prompt["id"], artifact["id"], artifact["sha256"],
                 engine, model, json.dumps(settings, sort_keys=True), mask_id, signature,
                 request_key + ":" + photo_id, replacement_id, "QUEUED",
                 float(provider.estimated_cost_usd) if engine == "GENERATIVE" else 0.0, now, now),
            )
            jobs.append(job_id)
        db.commit()
        return [_public_job(dict(db.execute("SELECT * FROM edit_jobs WHERE id=?", (job_id,)).fetchone())) for job_id in jobs]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _deterministic(path: Path, settings: dict) -> EditResult:
    with Image.open(path) as source:
        image = source.convert("RGB")
        image = ImageEnhance.Brightness(image).enhance(settings["exposure"])
        image = ImageEnhance.Contrast(image).enhance(settings["contrast"])
        image = ImageEnhance.Color(image).enhance(settings["color"])
        image = ImageEnhance.Sharpness(image).enhance(settings["sharpness"])
        if settings["denoise"]:
            size = 3 if settings["denoise"] <= 2 else 5 if settings["denoise"] <= 4 else 7
            image = image.filter(ImageFilter.MedianFilter(size=size))
        output = BytesIO()
        image.save(output, format="PNG")
    return EditResult(output.getvalue(), ".png", "Pillow-deterministic-v1", {}, Decimal("0"))


def _public_job(row: dict) -> dict:
    item = {key: row[key] for key in (
        "id", "batch_id", "photo_id", "compiled_prompt_id", "engine", "model", "status", "error",
        "image_version_id", "estimated_cost_usd", "actual_cost_usd", "created_at", "started_at", "completed_at",
        "replacement_of_version_id",
    )}
    if item["error"]:
        item["error"] = "Edit failed; inspect the private SQLite job receipt before retrying"
    return item


def list_jobs(data_dir: Path, photo_id: str) -> list[dict]:
    db = connect(data_dir)
    try:
        return [_public_job(dict(row)) for row in db.execute(
            "SELECT * FROM edit_jobs WHERE photo_id=? ORDER BY created_at DESC", (photo_id,)
        )]
    finally:
        db.close()


def batch_jobs(data_dir: Path, batch_id: str) -> list[dict]:
    db = connect(data_dir)
    try:
        return [_public_job(dict(row)) for row in db.execute(
            "SELECT * FROM edit_jobs WHERE batch_id=? ORDER BY created_at", (batch_id,)
        )]
    finally:
        db.close()


def run_job(data_dir: Path, job_id: str, provider: EditProvider) -> dict:
    db = connect(data_dir)
    try:
        db.execute("BEGIN IMMEDIATE")
        claimed = db.execute(
            "UPDATE edit_jobs SET status='RUNNING',started_at=? WHERE id=? AND status='QUEUED'",
            (utc_now(), job_id),
        )
        if claimed.rowcount != 1:
            db.commit()
            row = db.execute("SELECT * FROM edit_jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            return _public_job(dict(row))
        row = db.execute("SELECT * FROM edit_jobs WHERE id=?", (job_id,)).fetchone()
        db.execute("UPDATE edit_batches SET status='RUNNING' WHERE id=? AND status='QUEUED'", (row["batch_id"],))
        db.commit()
        input_item, input_path = verify_publication_input(db, data_dir, row["publication_input_id"])
        if input_item["sha256"] != row["publication_input_hash"]:
            raise ImageIntegrityError("Job input hash does not match the validated derivative")
        prompt = db.execute("SELECT * FROM compiled_prompts WHERE id=?", (row["compiled_prompt_id"],)).fetchone()
        profile = json.loads(prompt["publication_profile_snapshot_json"])
        if (prompt["source_hash"] != input_item["source_hash"]
                or prompt["publication_profile_id"] != input_item["publication_profile_id"]):
            raise ImageIntegrityError("Job input source/profile does not match its approved prompt")
        current = db.execute(
            """SELECT p.original_path,p.sha256,p.revision,d.revision AS draft_revision,
                      d.compiled_prompt_stale FROM photos p JOIN review_drafts d ON d.photo_id=p.id
               WHERE p.id=?""", (row["photo_id"],)
        ).fetchone()
        if (current is None or not prompt["approved_for_job"] or current["compiled_prompt_stale"]
                or current["revision"] != prompt["photo_revision"]
                or current["draft_revision"] != prompt["draft_revision"]
                or current["sha256"] != input_item["source_hash"]
                or not Path(current["original_path"]).is_file()
                or sha256(Path(current["original_path"])) != input_item["source_hash"]):
            raise ImageIntegrityError("Photo or approved prompt changed after job was queued")
        approved = db.execute(
            "SELECT id FROM image_versions WHERE photo_id=? AND review_status='APPROVED'",
            (row["photo_id"],),
        ).fetchone()
        if row["replacement_of_version_id"]:
            if approved is None or approved["id"] != row["replacement_of_version_id"]:
                raise EditConflict("The approved version changed while the replacement ran")
        elif approved:
            raise EditConflict("Photo was approved while the edit ran")
        mask = None
        if row["mask_id"]:
            mask_record = db.execute("SELECT * FROM masks WHERE id=?", (row["mask_id"],)).fetchone()
            if mask_record is None or mask_record["publication_input_id"] != input_item["id"]:
                raise ImageIntegrityError("Mask does not match the job input")
            mask = private_path(data_dir, mask_record["path"])
            if not mask.is_file() or sha256(mask) != mask_record["sha256"]:
                raise ImageIntegrityError("Mask is missing or changed")
        if row["engine"] == "DETERMINISTIC":
            result = _deterministic(input_path, json.loads(row["settings_json"]))
        else:
            if not row["authorized_at"]:
                raise PermissionError("Generative job lacks current-run authorization")
            if provider.model != row["model"]:
                raise EditConflict("Configured provider model changed after queueing")
            result = provider.edit(input_path, prompt["compiled_text"], mask)
        raw_relative, raw_path = save_raw_attempt(data_dir, result.image_bytes, result.suffix)
        calculated, price_version = calculate("openai", row["model"], result.usage,
                                               direct_images=row["engine"] == "GENERATIVE")
        db.execute("""UPDATE edit_jobs SET raw_path=?,raw_sha256=?,usage_json=?,actual_cost_usd=?,
                   calculated_cost_usd=?,price_version=?,request_id=? WHERE id=?""",
                   (raw_relative, sha256(raw_path), json.dumps(result.usage),
                    float(result.actual_cost_usd) if result.actual_cost_usd is not None else None,
                    calculated, price_version, result.request_id, job_id))
        db.commit()
        normalized_relative, normalized_path, width, height = normalize_attempt(
            data_dir, raw_path, profile, (input_item["width"], input_item["height"])
        )
        version_id = str(uuid4())
        db.execute("BEGIN IMMEDIATE")
        final_approved = db.execute(
            "SELECT id FROM image_versions WHERE photo_id=? AND review_status='APPROVED'",
            (row["photo_id"],),
        ).fetchone()
        if row["replacement_of_version_id"]:
            if final_approved is None or final_approved["id"] != row["replacement_of_version_id"]:
                raise EditConflict("The approved version changed while the replacement ran")
        elif final_approved:
            raise EditConflict("Photo was approved while the edit ran")
        number = db.execute(
            "SELECT COALESCE(MAX(version_number),0)+1 FROM image_versions WHERE photo_id=?", (row["photo_id"],)
        ).fetchone()[0]
        db.execute(
            """INSERT INTO image_versions(id,photo_id,version_number,path,sha256,width,height,created_at,
               review_status,job_id,publication_input_id,mime)
               VALUES (?,?,?,?,?,?,?,?,'PENDING',?,?,?)""",
            (version_id, row["photo_id"], number, normalized_relative, sha256(normalized_path),
             width, height, utc_now(), job_id, input_item["id"], "image/jpeg"),
        )
        db.execute("UPDATE edit_jobs SET status='SUCCEEDED',image_version_id=?,completed_at=? WHERE id=?",
                   (version_id, utc_now(), job_id))
        db.commit()
    except Exception as exc:
        db.rollback()
        if isinstance(exc, PaidRequestError):
            calculated, price_version = calculate("openai", row["model"], exc.usage, direct_images=True)
            db.execute("""UPDATE edit_jobs SET request_id=?,usage_json=?,calculated_cost_usd=?,price_version=?
                       WHERE id=? AND status='RUNNING'""",
                       (exc.request_id, json.dumps(exc.usage) if exc.usage is not None else None,
                        calculated, price_version, job_id))
        db.execute("UPDATE edit_jobs SET status='FAILED',error=?,completed_at=? WHERE id=? AND status='RUNNING'",
                   (str(exc)[:1000], utc_now(), job_id))
        db.commit()
    finally:
        db.close()
    _update_batch(data_dir, job_id)
    lookup = connect(data_dir)
    try:
        return _public_job(dict(lookup.execute("SELECT * FROM edit_jobs WHERE id=?", (job_id,)).fetchone()))
    finally:
        lookup.close()


def _update_batch(data_dir: Path, job_id: str) -> None:
    db = connect(data_dir)
    try:
        row = db.execute("SELECT batch_id FROM edit_jobs WHERE id=?", (job_id,)).fetchone()
        if row and row["batch_id"]:
            active = db.execute(
                "SELECT COUNT(*) FROM edit_jobs WHERE batch_id=? AND status IN ('QUEUED','RUNNING')", (row["batch_id"],)
            ).fetchone()[0]
            if not active:
                db.execute("UPDATE edit_batches SET status='COMPLETED' WHERE id=?", (row["batch_id"],))
                db.commit()
    finally:
        db.close()


def cancel_job(data_dir: Path, job_id: str) -> dict:
    db = connect(data_dir)
    try:
        db.execute("UPDATE edit_jobs SET status='CANCELLED',completed_at=? WHERE id=? AND status='QUEUED'",
                   (utc_now(), job_id))
        db.commit()
        row = db.execute("SELECT * FROM edit_jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        if row["status"] == "RUNNING":
            raise EditConflict("Running provider calls cannot be cancelled reliably")
        if row["status"] == "CANCELLED" and row["batch_id"]:
            remaining = db.execute(
                "SELECT COUNT(*) FROM edit_jobs WHERE batch_id=? AND status IN ('QUEUED','RUNNING')",
                (row["batch_id"],),
            ).fetchone()[0]
            if not remaining:
                db.execute("UPDATE edit_batches SET status='CANCELLED' WHERE id=?", (row["batch_id"],))
                db.commit()
        return _public_job(dict(row))
    finally:
        db.close()


def recover_jobs(data_dir: Path, provider: EditProvider, executor: ThreadPoolExecutor) -> None:
    db = connect(data_dir)
    try:
        db.execute("UPDATE edit_jobs SET status='FAILED',error='Interrupted while processing; inspect artifacts before explicit retry',completed_at=? WHERE status='RUNNING' AND engine='DETERMINISTIC'", (utc_now(),))
        db.execute("UPDATE edit_jobs SET status='FAILED',error='Interrupted while provider call may have been billed; inspect before explicit retry',completed_at=? WHERE status='RUNNING' AND engine='GENERATIVE'", (utc_now(),))
        db.execute("UPDATE edit_jobs SET status='FAILED',error='Queued provider call was not resumed after restart; reauthorize a new run',completed_at=? WHERE status='QUEUED' AND engine='GENERATIVE'", (utc_now(),))
        db.execute("""UPDATE edit_batches SET status='COMPLETED' WHERE status IN ('QUEUED','RUNNING')
                      AND NOT EXISTS (SELECT 1 FROM edit_jobs j WHERE j.batch_id=edit_batches.id
                                      AND j.status IN ('QUEUED','RUNNING'))""")
        db.commit()
        ids = [row["id"] for row in db.execute("SELECT id FROM edit_jobs WHERE status='QUEUED' AND engine='DETERMINISTIC' ORDER BY created_at")]
    finally:
        db.close()
    for job_id in ids:
        executor.submit(run_job, data_dir, job_id, provider)


def review_version(data_dir: Path, photo_id: str, version_id: str, decision: str,
                   reason: str | None, replace_approved: bool = False) -> dict:
    if decision not in ("APPROVED", "REJECTED"):
        raise EditConflict("Review decision must be APPROVED or REJECTED")
    db = connect(data_dir)
    try:
        db.execute("BEGIN IMMEDIATE")
        version = db.execute(
            "SELECT * FROM image_versions WHERE id=? AND photo_id=?", (version_id, photo_id)
        ).fetchone()
        if version is None:
            raise KeyError(version_id)
        if version["review_status"] != "PENDING":
            raise EditConflict("Only pending versions can be reviewed")
        replacement_id = None
        if version["local_job_id"]:
            job = db.execute("SELECT status,master_path,master_sha256,replacement_of_version_id FROM local_jobs WHERE id=?",
                             (version["local_job_id"],)).fetchone()
            if job is None or job["status"] != "SUCCEEDED":
                raise EditConflict("Local correction did not succeed")
            master = private_path(data_dir, job["master_path"])
            if not master.is_file() or sha256(master) != job["master_sha256"]:
                raise ImageIntegrityError("Full-resolution master is missing or changed")
            replacement_id = job["replacement_of_version_id"]
        else:
            if version["job_id"] is None:
                raise EditConflict("Version has no completed edit job")
            job = db.execute("SELECT status,replacement_of_version_id FROM edit_jobs WHERE id=?", (version["job_id"],)).fetchone()
            if job is None or job["status"] != "SUCCEEDED":
                raise EditConflict("Version job did not succeed")
            replacement_id = job["replacement_of_version_id"]
        path = private_path(data_dir, version["path"])
        if not path.is_file() or sha256(path) != version["sha256"]:
            raise ImageIntegrityError("Version file is missing or changed")
        current_approved = db.execute(
            "SELECT id,version_number FROM image_versions WHERE photo_id=? AND review_status='APPROVED'",
            (photo_id,),
        ).fetchone()
        if decision == "APPROVED" and replacement_id:
            if not replace_approved:
                raise EditConflict("Approve this version with explicit replacement confirmation")
            if current_approved is None or replacement_id != current_approved["id"]:
                raise EditConflict("This version was not created as a replacement for the current approval")
        elif decision == "APPROVED" and current_approved:
            raise EditConflict("This version was not created as a replacement for the current approval")
        now = utc_now()
        if decision == "APPROVED" and current_approved:
            db.execute(
                """UPDATE image_versions SET review_status='REJECTED',rejection_reason=NULL,
                   superseded_by_version_id=?,superseded_at=? WHERE id=? AND review_status='APPROVED'""",
                (version_id, now, current_approved["id"]),
            )
            db.execute(
                """INSERT INTO review_events(id,version_id,actor,reviewed_at,previous_status,next_status,note)
                   VALUES (?,?,?,?,'APPROVED','REJECTED',?)""",
                (str(uuid4()), current_approved["id"], "owner", now,
                 f"Superseded by approved version {version['version_number']}"),
            )
        db.execute(
            "UPDATE image_versions SET review_status=?,reviewed_at=?,rejection_reason=? WHERE id=?",
            (decision, now, reason.strip() if decision == "REJECTED" and reason else None, version_id),
        )
        db.execute(
            """INSERT INTO review_events(id,version_id,actor,reviewed_at,previous_status,next_status,note)
               VALUES (?,?,?,?,'PENDING',?,?)""",
            (str(uuid4()), version_id, "owner", now, decision, reason.strip() if reason else None),
        )
        db.commit()
        return dict(db.execute(
            """SELECT id,photo_id,version_number,review_status,reviewed_at,rejection_reason,
                      superseded_by_version_id,superseded_at FROM image_versions WHERE id=?""",
            (version_id,),
        ).fetchone())
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def version_media(data_dir: Path, photo_id: str, version_id: str) -> Path:
    db = connect(data_dir)
    try:
        row = db.execute("SELECT path,sha256 FROM image_versions WHERE id=? AND photo_id=?", (version_id, photo_id)).fetchone()
        if row is None:
            raise KeyError(version_id)
        path = private_path(data_dir, row["path"])
        if not path.is_file() or sha256(path) != row["sha256"]:
            raise ImageIntegrityError("Version file is missing or changed")
        return path
    finally:
        db.close()
