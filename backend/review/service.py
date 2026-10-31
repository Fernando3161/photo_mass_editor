"""Persistence operations for the local photo-review UI."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.catalog.database import connect
from backend.catalog.ingestion import utc_now


class ReviewConflict(RuntimeError):
    """The client attempted to save an outdated photo revision."""


class ReviewNotFound(RuntimeError):
    """The requested catalog record does not exist."""


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or f"label-{uuid4().hex[:8]}"


def _media_url(photo_id: str, kind: str) -> str:
    return f"/api/photos/{photo_id}/{kind}"


def _tags(db: sqlite3.Connection, photo_id: str) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(
        """SELECT t.id, t.slug, t.display_name, t.kind, pt.source, pt.user_confirmed
           FROM photo_tags pt JOIN tags t ON t.id = pt.tag_id
           WHERE pt.photo_id = ? ORDER BY t.kind, lower(t.display_name)""",
        (photo_id,),
    )]


def _photo(db: sqlite3.Connection, photo_id: str) -> dict[str, Any]:
    row = db.execute(
        """SELECT p.*, s.display_name AS primary_subject
           FROM photos p LEFT JOIN subjects s ON s.id = p.primary_subject_id
           WHERE p.id = ?""",
        (photo_id,),
    ).fetchone()
    if row is None:
        raise ReviewNotFound(photo_id)
    item = dict(row)
    item.pop("original_exif_json", None)
    for internal in (
        "original_path", "managed_original_path", "thumbnail_path", "thumbnail_sha256",
        "sha256", "primary_subject_id", "duplicate_of_id",
    ):
        item.pop(internal, None)
    private_lat = item.pop("private_lat")
    private_lon = item.pop("private_lon")
    item["gps_present"] = private_lat is not None and private_lon is not None
    item["thumbnail_url"] = _media_url(photo_id, "thumbnail")
    item["original_url"] = _media_url(photo_id, "original")
    item["tags"] = _tags(db, photo_id)
    draft = db.execute(
        """SELECT preset_id, publication_profile_id, ai_allowance, ai_suggestion_editable, user_instructions,
                  approved_constraints, semantic_change_consent, analysis_run_id,
                  compiled_prompt_stale, revision AS draft_revision, saved_at
           FROM review_drafts WHERE photo_id = ?""",
        (photo_id,),
    ).fetchone()
    item["draft"] = dict(draft) if draft else {
        "preset_id": None,
        "publication_profile_id": "website-standard-v1",
        "ai_allowance": 0,
        "ai_suggestion_editable": "",
        "user_instructions": "",
        "approved_constraints": "",
        "semantic_change_consent": 0,
        "analysis_run_id": None,
        "compiled_prompt_stale": 1,
        "draft_revision": 0,
        "saved_at": None,
    }
    versions = db.execute(
        """SELECT id, version_number, review_status, created_at
           FROM image_versions WHERE photo_id = ? ORDER BY version_number""",
        (photo_id,),
    ).fetchall()
    item["versions"] = [dict(version) for version in versions]
    from .prompts import prompt_history
    item["prompt_history"] = prompt_history(db, photo_id)
    return item


def list_photos(data_dir: Path) -> list[dict[str, Any]]:
    db = connect(data_dir)
    try:
        rows = db.execute(
            """SELECT p.id, p.original_filename, p.width, p.height, p.capture_datetime_raw,
                      p.camera, p.city, p.country, p.review_state, p.revision,
                      s.display_name AS primary_subject
               FROM photos p LEFT JOIN subjects s ON s.id = p.primary_subject_id
               ORDER BY COALESCE(p.capture_datetime_raw, p.imported_at), p.id"""
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["thumbnail_url"] = _media_url(item["id"], "thumbnail")
            item["tags"] = _tags(db, item["id"])
            result.append(item)
        return result
    finally:
        db.close()


def get_photo(data_dir: Path, photo_id: str) -> dict[str, Any]:
    db = connect(data_dir)
    try:
        return _photo(db, photo_id)
    finally:
        db.close()


def media_path(data_dir: Path, photo_id: str, kind: str) -> tuple[Path, str]:
    db = connect(data_dir)
    try:
        row = db.execute(
            "SELECT original_path, thumbnail_path, mime FROM photos WHERE id = ?", (photo_id,)
        ).fetchone()
        if row is None:
            raise ReviewNotFound(photo_id)
        if kind == "thumbnail":
            return Path(data_dir).resolve() / row["thumbnail_path"], "image/png"
        if kind == "original":
            return Path(row["original_path"]), row["mime"]
        raise ReviewNotFound(kind)
    finally:
        db.close()


def _upsert_subject(db: sqlite3.Connection, display_name: str | None) -> str | None:
    if not display_name or not display_name.strip():
        return None
    name = display_name.strip()
    slug = _slug(name)
    row = db.execute("SELECT id FROM subjects WHERE slug = ?", (slug,)).fetchone()
    if row:
        db.execute("UPDATE subjects SET display_name = ? WHERE id = ?", (name, row["id"]))
        return row["id"]
    subject_id = str(uuid4())
    db.execute("INSERT INTO subjects(id, slug, display_name) VALUES (?, ?, ?)", (subject_id, slug, name))
    return subject_id


def _replace_tags(db: sqlite3.Connection, photo_id: str, values: dict[str, list[str]]) -> None:
    db.execute("DELETE FROM photo_tags WHERE photo_id = ? AND source = 'USER'", (photo_id,))
    for kind, names in (("CONTENT", values["content_tags"]), ("CONDITION", values["condition_tags"])):
        seen: set[str] = set()
        for raw_name in names:
            name = raw_name.strip()
            slug = _slug(name)
            if not name or slug in seen:
                continue
            seen.add(slug)
            row = db.execute("SELECT id, kind FROM tags WHERE slug = ?", (slug,)).fetchone()
            if row and row["kind"] != kind:
                slug = f"{kind.lower()}-{slug}"
                row = db.execute("SELECT id, kind FROM tags WHERE slug = ?", (slug,)).fetchone()
            if row:
                tag_id = row["id"]
                db.execute("UPDATE tags SET display_name = ? WHERE id = ?", (name, tag_id))
            else:
                tag_id = str(uuid4())
                db.execute(
                    "INSERT INTO tags(id, slug, display_name, kind) VALUES (?, ?, ?, ?)",
                    (tag_id, slug, name, kind),
                )
            db.execute(
                """INSERT INTO photo_tags(photo_id, tag_id, source, user_confirmed, confidence)
                   VALUES (?, ?, 'USER', 1, NULL)
                   ON CONFLICT(photo_id, tag_id) DO UPDATE SET
                       source = 'USER', user_confirmed = 1, confidence = NULL""",
                (photo_id, tag_id),
            )


def save_photo(data_dir: Path, photo_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    db = connect(data_dir)
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT revision FROM photos WHERE id = ?", (photo_id,)).fetchone()
        if row is None:
            raise ReviewNotFound(photo_id)
        if row["revision"] != payload["expected_revision"]:
            raise ReviewConflict(f"expected revision {payload['expected_revision']}, found {row['revision']}")
        profile = db.execute(
            "SELECT id FROM publication_profiles WHERE id=? AND active=1",
            (payload["publication_profile_id"],),
        ).fetchone()
        if profile is None:
            raise ReviewNotFound(payload["publication_profile_id"])
        subject_id = _upsert_subject(db, payload.get("primary_subject"))
        analysis_run_id = payload.get("analysis_run_id")
        if analysis_run_id:
            analysis = db.execute(
                "SELECT id FROM analysis_runs WHERE id=? AND photo_id=? AND status='SUCCEEDED'",
                (analysis_run_id, photo_id),
            ).fetchone()
            if analysis is None:
                raise ReviewNotFound(analysis_run_id)
        now = utc_now()
        reviewed_at = now if payload["review_state"] == "REVIEWED" else None
        cursor = db.execute(
            """UPDATE photos SET primary_subject_id = ?, editorial_description = ?, city = ?, country = ?,
                      review_state = ?, metadata_reviewed_at = ?, revision = revision + 1
               WHERE id = ? AND revision = ?""",
            (subject_id, payload["editorial_description"], payload["city"], payload["country"],
             payload["review_state"], reviewed_at, photo_id, payload["expected_revision"]),
        )
        if cursor.rowcount != 1:
            raise ReviewConflict("photo changed while saving")
        _replace_tags(db, photo_id, payload)
        existing = db.execute("SELECT id, revision FROM review_drafts WHERE photo_id = ?", (photo_id,)).fetchone()
        if existing:
            db.execute(
                """UPDATE review_drafts SET preset_id = ?, publication_profile_id = ?, ai_allowance = ?, ai_suggestion_editable = ?,
                          user_instructions = ?, approved_constraints = ?, semantic_change_consent = ?,
                          analysis_run_id = ?, revision = revision + 1, updated_at = ?, saved_at = ?,
                          compiled_prompt_stale = 1 WHERE photo_id = ?""",
                (payload["preset_id"], payload["publication_profile_id"], payload["ai_allowance"], payload["ai_suggestion_editable"],
                 payload["user_instructions"], payload["approved_constraints"],
                 int(payload["semantic_change_consent"]), analysis_run_id, now, now, photo_id),
            )
        else:
            db.execute(
                """INSERT INTO review_drafts(
                       id, photo_id, revision, preset_id, publication_profile_id, ai_allowance, ai_suggestion_editable,
                       user_instructions, approved_constraints, semantic_change_consent,
                       analysis_run_id, updated_at, saved_at, compiled_prompt_stale
                   ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (str(uuid4()), photo_id, payload["preset_id"], payload["publication_profile_id"], payload["ai_allowance"],
                 payload["ai_suggestion_editable"], payload["user_instructions"],
                 payload["approved_constraints"], int(payload["semantic_change_consent"]),
                 analysis_run_id, now, now),
            )
        db.execute(
            "UPDATE compiled_prompts SET approved_for_job=0, approved_at=NULL WHERE photo_id=? AND approved_for_job=1",
            (photo_id,),
        )
        db.commit()
        return _photo(db, photo_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_options(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    db = connect(data_dir)
    try:
        return {
            "subjects": [dict(row) for row in db.execute("SELECT id, slug, display_name FROM subjects ORDER BY lower(display_name)")],
            "tags": [dict(row) for row in db.execute("SELECT id, slug, display_name, kind FROM tags ORDER BY kind, lower(display_name)")],
            "presets": [dict(row) for row in db.execute("SELECT id, version, name, structured_instructions, updated_at FROM presets ORDER BY rowid")],
            "publication_profiles": [dict(row) for row in db.execute(
                """SELECT id, version, name, image_format, file_extension, mime, max_long_edge,
                          quality, color_space, preserve_aspect_ratio, allow_upscale, strip_metadata
                   FROM publication_profiles WHERE active=1 ORDER BY name, version"""
            )],
        }
    finally:
        db.close()


def update_preset(data_dir: Path, preset_id: str, name: str, instructions: str) -> dict[str, Any]:
    db = connect(data_dir)
    try:
        cursor = db.execute(
            """UPDATE presets SET name = ?, structured_instructions = ?, version = version + 1,
                      updated_at = ? WHERE id = ?""",
            (name.strip(), instructions.strip(), utc_now(), preset_id),
        )
        if cursor.rowcount != 1:
            raise ReviewNotFound(preset_id)
        affected = [row["photo_id"] for row in db.execute(
            "SELECT photo_id FROM review_drafts WHERE preset_id=?", (preset_id,)
        )]
        db.execute("UPDATE review_drafts SET compiled_prompt_stale=1 WHERE preset_id=?", (preset_id,))
        if affected:
            placeholders = ",".join("?" for _ in affected)
            db.execute(
                f"UPDATE compiled_prompts SET approved_for_job=0, approved_at=NULL "
                f"WHERE approved_for_job=1 AND photo_id IN ({placeholders})",
                affected,
            )
        db.commit()
        return dict(db.execute(
            "SELECT id, version, name, structured_instructions, updated_at FROM presets WHERE id = ?",
            (preset_id,),
        ).fetchone())
    finally:
        db.close()
