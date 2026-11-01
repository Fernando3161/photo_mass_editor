"""Approved-only, byte-identical website export and read-only artifact audit."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4

from PIL import Image

from backend.catalog.database import connect
from backend.catalog.ingestion import sha256, utc_now

from .image_pipeline import ImageIntegrityError, private_path, validate_publication, verify_publication_input


PRIVACY_POLICY = "confirmed-editorial-location-only-v1"
TARGET = "website-standard-v1"


class ExportError(ValueError):
    """An approved version or export artifact failed its publication contract."""


def export_path(data_dir: Path, relative: str) -> Path:
    """Resolve an export under the final data/exports layout or a legacy catalog."""
    root = Path(data_dir).resolve()
    parts = Path(relative).parts
    if len(parts) < 2 or parts[0] != "exports" or any(part in (".", "..") for part in parts):
        raise ExportError("Invalid export path")
    export_root = (root.parent / "exports" if root.name == "catalog" and root.parent.name == "data"
                   else root / "exports").resolve()
    path = export_root.joinpath(*parts[1:]).resolve()
    if export_root not in path.parents:
        raise ExportError("Export path escapes the export directory")
    return path


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _approved(db: sqlite3.Connection, root: Path) -> list[dict]:
    rows = db.execute(
        """SELECT p.id AS photo_id, p.original_path, p.sha256 AS source_sha256,
                  p.editorial_description, p.city, p.country,
                  s.display_name AS subject,
                  v.id AS version_id, v.path, v.sha256 AS version_sha256,
                  v.width, v.height, v.mime, v.reviewed_at, v.job_id,
                  v.publication_input_id, pi.source_hash AS input_source_hash,
                  pi.publication_profile_id, j.status AS job_status,
                  j.image_version_id AS job_version_id, j.publication_input_id AS job_input_id,
                  j.publication_input_hash AS job_input_hash
           FROM image_versions v JOIN photos p ON p.id=v.photo_id
           LEFT JOIN subjects s ON s.id=p.primary_subject_id
           LEFT JOIN publication_inputs pi ON pi.id=v.publication_input_id
           LEFT JOIN edit_jobs j ON j.id=v.job_id
           WHERE v.review_status='APPROVED' ORDER BY p.id"""
    ).fetchall()
    profile = db.execute("SELECT * FROM publication_profiles WHERE id=?", (TARGET,)).fetchone()
    if profile is None:
        raise ExportError("Website publication profile is missing")
    items = []
    for row in rows:
        item = dict(row)
        source = Path(item["original_path"])
        if not source.is_file() or sha256(source) != item["source_sha256"]:
            raise ExportError(f"Original is missing or changed for photo {item['photo_id']}")
        if (item["publication_profile_id"] != TARGET
                or item["input_source_hash"] != item["source_sha256"]
                or item["job_status"] != "SUCCEEDED"
                or item["job_version_id"] != item["version_id"]
                or item["job_input_id"] != item["publication_input_id"]):
            raise ExportError(f"Approved version lacks valid website job provenance: {item['version_id']}")
        try:
            publication_input, _ = verify_publication_input(db, root, item["publication_input_id"])
        except (OSError, ImageIntegrityError) as exc:
            raise ExportError(f"Approved version publication input is missing or changed: {item['version_id']}") from exc
        if publication_input["sha256"] != item["job_input_hash"]:
            raise ExportError(f"Approved version job input hash differs: {item['version_id']}")
        approved_event = db.execute(
            """SELECT 1 FROM review_events WHERE version_id=? AND actor='owner'
               AND previous_status='PENDING' AND next_status='APPROVED' LIMIT 1""",
            (item["version_id"],),
        ).fetchone()
        if not approved_event:
            raise ExportError(f"Approved version lacks an owner review event: {item['version_id']}")
        path = private_path(root, item["path"])
        if not path.is_file() or sha256(path) != item["version_sha256"]:
            raise ExportError(f"Approved version is missing or changed: {item['version_id']}")
        try:
            size = validate_publication(path, dict(profile))
        except (OSError, ImageIntegrityError) as exc:
            raise ExportError(f"Approved version violates website profile: {item['version_id']}") from exc
        if size != (item["width"], item["height"]) or item["mime"] != "image/jpeg":
            raise ExportError(f"Approved version dimensions or MIME differ from catalog: {item['version_id']}")
        tags = db.execute(
            """SELECT t.display_name FROM photo_tags pt JOIN tags t ON t.id=pt.tag_id
               WHERE pt.photo_id=? AND (pt.user_confirmed=1 OR pt.source='USER')
               ORDER BY t.kind, lower(t.display_name)""", (item["photo_id"],)
        ).fetchall()
        item["tags"] = [tag[0] for tag in tags]
        item["source_path"] = path
        items.append(item)
    return items


def preview_export(data_dir: Path) -> dict:
    root = Path(data_dir).resolve()
    db = connect(root)
    try:
        items = _approved(db, root)
        return {"target": TARGET, "approved_count": len(items), "items": [
            {"photo_id": item["photo_id"], "version_id": item["version_id"],
             "width": item["width"], "height": item["height"],
             "sha256": item["version_sha256"],
             "location_included": bool(item["city"] and item["country"])}
            for item in items]}
    finally:
        db.close()


def recent_exports(data_dir: Path, limit: int = 10) -> list[dict]:
    root = Path(data_dir).resolve()
    db = connect(root)
    try:
        rows = db.execute(
            """SELECT e.id,e.created_at,e.manifest_path,COUNT(i.photo_id) AS item_count
               FROM exports e LEFT JOIN export_items i ON i.export_id=e.id
               WHERE e.status='COMPLETE' GROUP BY e.id
               ORDER BY e.created_at DESC,e.id DESC LIMIT ?""", (limit,),
        ).fetchall()
        return [{"export_id": row["id"], "created_at": row["created_at"],
                 "item_count": row["item_count"],
                 "directory_path": str(export_path(root, row["manifest_path"]).parent)}
                for row in rows]
    finally:
        db.close()


def _cost_report(db: sqlite3.Connection, export_id: str, created_at: str) -> dict:
    report = {"export_id": export_id, "through": created_at, "currency": "USD", "operations": {}}
    for name, table, estimate, actual in (
        ("editing", "edit_jobs", "estimated_cost_usd", "actual_cost_usd"),
        ("analysis", "analysis_runs", "estimated_cost", "actual_cost"),
    ):
        rows = db.execute(f"SELECT {estimate}, {actual} FROM {table} WHERE created_at <= ?" if name == "editing"
                          else f"SELECT {estimate}, {actual} FROM {table} WHERE analyzed_at <= ?",
                          (created_at,)).fetchall()
        estimated = sum((Decimal(str(row[0])) for row in rows if row[0] is not None), Decimal("0"))
        actual_total = sum((Decimal(str(row[1])) for row in rows if row[1] is not None), Decimal("0"))
        report["operations"][name] = {
            "attempts": len(rows), "estimated_usd": str(estimated),
            "known_actual_usd": str(actual_total),
            "actual_cost_unknown_count": sum(row[1] is None for row in rows),
        }
    return report


def create_export(data_dir: Path) -> dict:
    """Publish a new directory; never rewrite an earlier export or an approved image."""
    root = Path(data_dir).resolve()
    db = connect(root)
    staging: Path | None = None
    try:
        db.execute("BEGIN IMMEDIATE")
        items = _approved(db, root)
        if not items:
            raise ExportError("No approved website versions are available")
        export_id = str(uuid4())
        created_at = utc_now()
        relative_dir = f"exports/{export_id}"
        export_root = export_path(root, f"exports/{export_id}").parent
        export_root.mkdir(parents=True, exist_ok=True)
        staging = export_root / f".preparing-{export_id}"
        staging.mkdir()
        (staging / "images").mkdir()
        (staging / "thumbnails").mkdir()
        manifest_items = []
        records = []
        for item in items:
            image_name = f"{item['photo_id']}.jpg"
            image_rel = f"images/{image_name}"
            thumb_rel = f"thumbnails/{image_name}"
            image_target = staging / image_rel
            with item["source_path"].open("rb") as source, image_target.open("xb") as output:
                shutil.copyfileobj(source, output)
                output.flush()
                os.fsync(output.fileno())
            if sha256(image_target) != item["version_sha256"]:
                raise ExportError(f"Export copy changed approved bytes: {item['version_id']}")
            with Image.open(image_target) as image:
                thumb = image.copy()
                thumb.thumbnail((320, 320), Image.Resampling.LANCZOS)
                thumb_bytes = BytesIO()
                thumb.save(thumb_bytes, "JPEG", quality=80)
            thumb_target = staging / thumb_rel
            thumb_target.write_bytes(thumb_bytes.getvalue())
            with Image.open(thumb_target) as check:
                check.load()
                if check.getexif() or check.info.get("icc_profile") or max(check.size) > 320:
                    raise ExportError("Export thumbnail contains metadata or exceeds 320 pixels")
            caption = (item["editorial_description"] or "").strip()
            subject = (item["subject"] or "").strip()
            location = ({"city": item["city"].strip(), "country": item["country"].strip()}
                        if item["city"] and item["country"] else None)
            manifest_items.append({
                "photo_id": item["photo_id"], "approved_version_id": item["version_id"],
                "approved_at": item["reviewed_at"], "image": image_rel,
                "sha256": item["version_sha256"], "width": item["width"],
                "height": item["height"], "format": "JPEG", "mime": "image/jpeg",
                "thumbnail": thumb_rel, "thumbnail_sha256": sha256(thumb_target),
                "title": subject or "Travel photo", "caption": caption,
                "alt_text": caption or subject or "Travel photo",
                "tags": item["tags"], "location": location,
            })
            records.append((export_id, item["photo_id"], item["version_id"],
                            f"{relative_dir}/{image_rel}", item["version_sha256"],
                            f"{relative_dir}/{thumb_rel}", sha256(thumb_target)))
        manifest = {"schema_version": 1, "export_id": export_id, "created_at": created_at,
                    "target": TARGET, "privacy_policy_version": PRIVACY_POLICY,
                    "items": manifest_items}
        (staging / "manifest.json").write_bytes(_json_bytes(manifest))
        (staging / "cost_report.json").write_bytes(_json_bytes(_cost_report(db, export_id, created_at)))
        final = export_path(root, relative_dir)
        if final.exists():
            raise ExportError("Export directory collision")
        staging.rename(final)
        staging = None
        db.execute(
            """INSERT INTO exports(id,created_at,target,manifest_path,cost_report_path,
               privacy_policy_version,status) VALUES (?,?,?,?,?,?,'COMPLETE')""",
            (export_id, created_at, TARGET, f"{relative_dir}/manifest.json",
             f"{relative_dir}/cost_report.json", PRIVACY_POLICY),
        )
        db.executemany(
            """INSERT INTO export_items(export_id,photo_id,image_version_id,derivative_path,
               derivative_sha256,thumbnail_path,thumbnail_sha256) VALUES (?,?,?,?,?,?,?)""", records,
        )
        db.commit()
        return {"export_id": export_id, "directory": relative_dir,
                "directory_path": str(final),
                "manifest": f"{relative_dir}/manifest.json", "cost_report": f"{relative_dir}/cost_report.json",
                "item_count": len(items)}
    except Exception:
        db.rollback()
        # A failed preparation remains as evidence for the read-only cleanup audit.
        raise
    finally:
        db.close()


def audit_artifacts(data_dir: Path) -> dict:
    """Report missing, changed, and unreferenced media; never delete anything."""
    root = Path(data_dir).resolve()
    db = connect(root)
    try:
        referenced: dict[Path, str] = {}
        for table, path_col, hash_col in (
            ("photos", "thumbnail_path", "thumbnail_sha256"),
            ("publication_inputs", "path", "sha256"),
            ("masks", "path", "sha256"),
            ("image_versions", "path", "sha256"),
            ("edit_jobs", "raw_path", "raw_sha256"),
            ("export_items", "derivative_path", "derivative_sha256"),
            ("export_items", "thumbnail_path", "thumbnail_sha256"),
        ):
            for row in db.execute(f"SELECT {path_col}, {hash_col} FROM {table} WHERE {path_col} IS NOT NULL"):
                resolver = export_path if table == "export_items" else private_path
                referenced[resolver(root, row[0])] = row[1]
        for row in db.execute("SELECT managed_original_path,sha256 FROM photos WHERE managed_original_path IS NOT NULL"):
            referenced[private_path(root, row[0])] = row[1]
        invalid_manifests, invalid_cost_reports = [], []
        for row in db.execute("SELECT id,manifest_path,cost_report_path FROM exports WHERE status='COMPLETE'"):
            referenced[export_path(root, row["manifest_path"])] = ""
            referenced[export_path(root, row["cost_report_path"])] = ""
            manifest_path = export_path(root, row["manifest_path"])
            cost_path = export_path(root, row["cost_report_path"])
            if manifest_path.is_file():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    expected = {item["image_version_id"]: item for item in db.execute(
                        "SELECT image_version_id,derivative_path,derivative_sha256,thumbnail_path,thumbnail_sha256 FROM export_items WHERE export_id=?",
                        (row["id"],),
                    )}
                    entries = manifest["items"]
                    if (manifest["export_id"] != row["id"] or manifest["target"] != TARGET
                            or len(entries) != len(expected)
                            or len({entry["approved_version_id"] for entry in entries}) != len(entries)
                            or any(entry["approved_version_id"] not in expected
                                   or f"exports/{row['id']}/{entry['image']}" != expected[entry["approved_version_id"]]["derivative_path"]
                                   or entry["sha256"] != expected[entry["approved_version_id"]]["derivative_sha256"]
                                   or f"exports/{row['id']}/{entry['thumbnail']}" != expected[entry["approved_version_id"]]["thumbnail_path"]
                                   or entry["thumbnail_sha256"] != expected[entry["approved_version_id"]]["thumbnail_sha256"]
                                   for entry in entries)):
                        invalid_manifests.append(row["manifest_path"])
                except (OSError, ValueError, KeyError, TypeError):
                    invalid_manifests.append(row["manifest_path"])
            if cost_path.is_file():
                try:
                    report = json.loads(cost_path.read_text(encoding="utf-8"))
                    if report["export_id"] != row["id"] or report["currency"] != "USD":
                        invalid_cost_reports.append(row["cost_report_path"])
                except (OSError, ValueError, KeyError, TypeError):
                    invalid_cost_reports.append(row["cost_report_path"])
        missing, changed = [], []
        for path, expected in referenced.items():
            relative = path.relative_to(root.parent if root.name == "catalog" and root.parent.name == "data" else root).as_posix()
            if not path.is_file():
                missing.append(relative)
            elif expected and sha256(path) != expected:
                changed.append(relative)
        source_issues = []
        for row in db.execute("SELECT id,original_path,sha256 FROM photos"):
            source = Path(row[1])
            if not source.is_file() or sha256(source) != row[2]:
                source_issues.append(row[0])
        orphaned = []
        for folder in ("thumbnails", "originals", "publication-inputs", "masks", "edited", "exports"):
            base = export_path(root, "exports/probe").parent if folder == "exports" else root / folder
            if base.is_dir():
                display_root = root.parent if root.name == "catalog" and root.parent.name == "data" else root
                orphaned.extend(path.relative_to(display_root).as_posix() for path in base.rglob("*")
                                if path.is_file() and path not in referenced)
        return {"referenced_files": len(referenced), "missing": sorted(missing),
                "changed": sorted(changed), "source_issues": sorted(source_issues),
                "orphaned": sorted(orphaned), "invalid_manifests": sorted(invalid_manifests),
                "invalid_cost_reports": sorted(invalid_cost_reports)}
    finally:
        db.close()
