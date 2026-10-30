"""Cached, bounded, explicitly authorized analysis orchestration."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from backend.catalog.database import connect
from backend.catalog.ingestion import utc_now

from .analysis import AnalysisProvider
from .service import ReviewNotFound


MAX_ANALYSIS_BATCH = 25


def _photo_rows(db: sqlite3.Connection, photo_ids: list[str]) -> list[sqlite3.Row]:
    if not photo_ids or len(photo_ids) > MAX_ANALYSIS_BATCH or len(set(photo_ids)) != len(photo_ids):
        raise ValueError(f"Choose 1 to {MAX_ANALYSIS_BATCH} distinct photos")
    placeholders = ",".join("?" for _ in photo_ids)
    rows = db.execute(
        f"""SELECT id, original_path, sha256, original_filename, width, height,
                   camera, lens, capture_datetime_raw
            FROM photos WHERE id IN ({placeholders})""",
        photo_ids,
    ).fetchall()
    by_id = {row["id"]: row for row in rows}
    missing = [photo_id for photo_id in photo_ids if photo_id not in by_id]
    if missing:
        raise ReviewNotFound(missing[0])
    return [by_id[photo_id] for photo_id in photo_ids]


def _cached(db: sqlite3.Connection, photo: sqlite3.Row, provider: AnalysisProvider) -> sqlite3.Row | None:
    return db.execute(
        """SELECT * FROM analysis_runs
           WHERE photo_id=? AND source_hash=? AND config_signature=? AND status='SUCCEEDED'
           ORDER BY analyzed_at DESC LIMIT 1""",
        (photo["id"], photo["sha256"], provider.config_signature),
    ).fetchone()


def estimate_analysis(data_dir: Path, photo_ids: list[str], provider: AnalysisProvider) -> dict[str, Any]:
    db = connect(data_dir)
    try:
        rows = _photo_rows(db, photo_ids)
        cached = sum(1 for row in rows if _cached(db, row, provider))
        billable = len(rows) - cached
        estimate = provider.estimate(billable)
        return {
            "photo_count": len(rows),
            "cached_count": cached,
            "billable_count": billable,
            "estimated_cost": str(estimate),
            "currency": provider.currency,
            "provider": provider.provider_name,
            "model": provider.model,
            "template_version": provider.template_version,
            "max_batch": MAX_ANALYSIS_BATCH,
        }
    finally:
        db.close()


def _public_run(row: sqlite3.Row | dict[str, Any], cached: bool) -> dict[str, Any]:
    item = dict(row)
    item["cached"] = cached
    for key in ("raw_response_json", "usage_json", "sanitized_output_json", "suggested_tags_json"):
        raw = item.pop(key, None)
        if key == "suggested_tags_json":
            item["suggested_tags"] = json.loads(raw or "[]")
        elif key == "sanitized_output_json":
            item["sanitized_output"] = json.loads(raw) if raw else None
        elif key == "usage_json":
            item["usage"] = json.loads(raw) if raw else None
        # Raw provider response is deliberately retained server-side, not returned to the browser.
    item.pop("source_hash", None)
    item.pop("config_signature", None)
    return item


def run_analysis(
    data_dir: Path,
    photo_ids: list[str],
    provider: AnalysisProvider,
    *,
    authorized: bool,
    force_refresh: bool = False,
) -> dict[str, Any]:
    if not authorized:
        raise PermissionError("Owner authorization is required for this analysis run")
    db = connect(data_dir)
    try:
        photos = _photo_rows(db, photo_ids)
        results: list[dict[str, Any]] = []
        for photo in photos:
            cached = None if force_refresh else _cached(db, photo, provider)
            if cached:
                results.append(_public_run(cached, True))
                continue
            path = Path(photo["original_path"])
            if not path.is_file():
                raise FileNotFoundError(f"Source image is missing for {photo['original_filename']}")
            run_id = str(uuid4())
            now = utc_now()
            estimate = provider.estimate(1)
            db.execute(
                """INSERT INTO analysis_runs(
                       id, photo_id, source_hash, provider, model, template_version,
                       config_signature, status, estimated_cost, currency, analyzed_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, 'RUNNING', ?, ?, ?)""",
                (run_id, photo["id"], photo["sha256"], provider.provider_name, provider.model,
                 provider.template_version, provider.config_signature, float(estimate),
                 provider.currency, now),
            )
            db.commit()
            context = {
                "photo_id": photo["id"],
                "filename": photo["original_filename"],
                "width": photo["width"],
                "height": photo["height"],
                "camera": photo["camera"],
                "lens": photo["lens"],
                "capture_datetime": photo["capture_datetime_raw"],
                # Precise GPS, EXIF snapshot, and filesystem paths are intentionally excluded.
            }
            try:
                suggestion = provider.analyze(path, context)
                sanitized = suggestion.sanitized()
                db.execute(
                    """UPDATE analysis_runs SET raw_response_json=?, sanitized_output_json=?,
                              suggested_primary=?, suggested_tags_json=?, suggested_edits=?,
                              status='SUCCEEDED', actual_cost=?, usage_json=? WHERE id=?""",
                    (json.dumps(suggestion.raw_response), json.dumps(sanitized), suggestion.primary_subject,
                     json.dumps(suggestion.tags), suggestion.suggested_edits,
                     float(suggestion.actual_cost) if suggestion.actual_cost is not None else None,
                     json.dumps(suggestion.usage) if suggestion.usage is not None else None, run_id),
                )
                db.commit()
            except Exception as exc:
                db.execute("UPDATE analysis_runs SET status='FAILED', error=? WHERE id=?", (str(exc), run_id))
                db.commit()
                raise
            completed = db.execute("SELECT * FROM analysis_runs WHERE id=?", (run_id,)).fetchone()
            results.append(_public_run(completed, False))
        return {"results": results}
    finally:
        db.close()
