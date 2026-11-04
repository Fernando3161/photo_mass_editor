"""Reviewable local catalog suggestions and private visited-city matching."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4

from backend.catalog.database import connect
from backend.catalog.ingestion import utc_now
from .local_model import LABELS, MANIFEST, SETTINGS, ModelManager
from .service import ReviewConflict, ReviewNotFound, _photo, _slug, _tags, _upsert_subject

MAX_BATCH = 20
FIELDS = {"primary_subject", "content_tags", "condition_tags", "editorial_description", "preset_id", "city", "country"}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint(photo, cities) -> str:
    city_version = [(row["id"], row["revision"]) for row in cities]
    return hashlib.sha256(json.dumps([photo["sha256"], photo["thumbnail_sha256"], MANIFEST["revision"], SETTINGS, city_version], sort_keys=True).encode()).hexdigest()


def _distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a, b = math.radians(lat1), math.radians(lat2)
    x = math.sin((b - a) / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(x)))


def match_city(photo, cities) -> dict:
    if photo["private_lat"] is None or photo["private_lon"] is None:
        return {"status": "NO_GPS", "city": None, "country": None, "distance_km": None}
    ranked = sorted(
        ((_distance(photo["private_lat"], photo["private_lon"], city["private_lat"], city["private_lon"]), city) for city in cities),
        key=lambda item: item[0],
    )
    valid = [(distance, city) for distance, city in ranked if distance <= city["radius_km"]]
    if not valid:
        return {"status": "UNMATCHED", "city": None, "country": None, "distance_km": round(ranked[0][0], 1) if ranked else None}
    distance, city = valid[0]
    if len(valid) > 1 and valid[1][0] - distance < max(5.0, distance * 0.25):
        return {"status": "AMBIGUOUS", "city": None, "country": None, "distance_km": round(distance, 1)}
    return {"status": "MATCH", "city": city["city"], "country": city["country"], "distance_km": round(distance, 1)}


def list_cities(root: Path) -> list[dict]:
    db = connect(root)
    try:
        # Coordinates deliberately stay server-side.
        return [dict(row) for row in db.execute("SELECT id, city, country, radius_km, revision FROM visited_cities ORDER BY country, city")]
    finally:
        db.close()


def save_city(root: Path, city: str, country: str, lat: float, lon: float, radius: float, city_id: str | None = None) -> dict:
    db = connect(root)
    try:
        identity = city_id or str(uuid4())
        if city_id:
            changed = db.execute("UPDATE visited_cities SET city=?, country=?, private_lat=?, private_lon=?, radius_km=?, revision=revision+1, updated_at=? WHERE id=?",
                                 (city.strip(), country.strip(), lat, lon, radius, utc_now(), city_id))
            if not changed.rowcount:
                raise ReviewNotFound(city_id)
        else:
            db.execute("INSERT INTO visited_cities VALUES (?,?,?,?,?,?,1,?)", (identity, city.strip(), country.strip(), lat, lon, radius, utc_now()))
        db.commit()
        return dict(db.execute("SELECT id, city, country, radius_km, revision FROM visited_cities WHERE id=?", (identity,)).fetchone())
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def delete_city(root: Path, city_id: str) -> None:
    db = connect(root)
    try:
        if not db.execute("DELETE FROM visited_cities WHERE id=?", (city_id,)).rowcount:
            raise ReviewNotFound(city_id)
        db.commit()
    finally:
        db.close()


def _snapshot(db, photo_id: str) -> dict:
    photo = db.execute("SELECT p.*, s.display_name AS primary_subject FROM photos p LEFT JOIN subjects s ON s.id=p.primary_subject_id WHERE p.id=?", (photo_id,)).fetchone()
    if photo is None:
        raise ReviewNotFound(photo_id)
    tags = _tags(db, photo_id)
    draft = db.execute("SELECT preset_id FROM review_drafts WHERE photo_id=?", (photo_id,)).fetchone()
    return {
        "revision": photo["revision"], "source_sha256": photo["sha256"],
        "primary_subject": photo["primary_subject"] or "",
        "content_tags": [tag["display_name"] for tag in tags if tag["kind"] == "CONTENT"],
        "condition_tags": [tag["display_name"] for tag in tags if tag["kind"] == "CONDITION"],
        "editorial_description": photo["editorial_description"],
        "city": photo["city"], "country": photo["country"],
        "preset_id": draft["preset_id"] if draft else None,
    }


def _sync_tags(db, photo_id: str, after: dict) -> None:
    """Apply only the accepted tag difference; preserve other tags' provenance."""
    for kind, field in (("CONTENT", "content_tags"), ("CONDITION", "condition_tags")):
        existing = list(db.execute(
            "SELECT t.id, t.display_name FROM photo_tags pt JOIN tags t ON t.id=pt.tag_id WHERE pt.photo_id=? AND t.kind=?",
            (photo_id, kind),
        ))
        desired = {name.strip().casefold(): name.strip() for name in after[field] if name.strip()}
        for row in existing:
            if row["display_name"].casefold() not in desired:
                db.execute("DELETE FROM photo_tags WHERE photo_id=? AND tag_id=?", (photo_id, row["id"]))
        known = {row["display_name"].casefold() for row in existing}
        for key, name in desired.items():
            if key in known:
                continue
            slug = _slug(name)
            tag = db.execute("SELECT id, kind FROM tags WHERE slug=?", (slug,)).fetchone()
            if tag and tag["kind"] != kind:
                slug = f"{kind.lower()}-{slug}"
                tag = db.execute("SELECT id, kind FROM tags WHERE slug=?", (slug,)).fetchone()
            if tag:
                tag_id = tag["id"]
            else:
                tag_id = str(uuid4())
                db.execute("INSERT INTO tags(id,slug,display_name,kind) VALUES (?,?,?,?)", (tag_id, slug, name, kind))
            db.execute("INSERT INTO photo_tags(photo_id,tag_id,source,user_confirmed,confidence) VALUES (?,?,'USER',1,NULL)", (photo_id, tag_id))


def _write(db, photo_id: str, before: dict, after: dict) -> dict:
    if before == after:
        return before
    subject = _upsert_subject(db, after["primary_subject"])
    changed = db.execute("UPDATE photos SET primary_subject_id=?, editorial_description=?, city=?, country=?, revision=revision+1 WHERE id=? AND revision=?",
                         (subject, after["editorial_description"], after["city"], after["country"], photo_id, before["revision"]))
    if changed.rowcount != 1:
        raise ReviewConflict("Photo changed while applying suggestion")
    _sync_tags(db, photo_id, after)
    draft = db.execute("SELECT id FROM review_drafts WHERE photo_id=?", (photo_id,)).fetchone()
    now = utc_now()
    if draft:
        db.execute("UPDATE review_drafts SET preset_id=?, revision=revision+1, compiled_prompt_stale=1, updated_at=?, saved_at=? WHERE photo_id=?",
                   (after["preset_id"], now, now, photo_id))
    else:
        db.execute("INSERT INTO review_drafts(id,photo_id,preset_id,publication_profile_id,updated_at,saved_at,revision,compiled_prompt_stale) VALUES (?,?,?,?,?,?,1,1)",
                   (str(uuid4()), photo_id, after["preset_id"], "website-standard-v1", now, now))
    db.execute("UPDATE compiled_prompts SET approved_for_job=0, approved_at=NULL WHERE photo_id=? AND approved_for_job=1", (photo_id,))
    return _snapshot(db, photo_id)


def _proposal(photo, result: dict, location: dict) -> tuple[dict, dict]:
    ranking = result["ranking"]
    content = [entry for entry in ranking if entry["label"] in LABELS]
    first = content[0]
    second = content[1]
    # CLIP scores are relative similarities, not calibrated probabilities.
    clear = first["similarity"] - second["similarity"] >= 1.5
    noun = first["label"].removeprefix("a ").removeprefix("an ") if clear else ""
    tags = [noun] if noun else []
    condition = []
    condition_scores = {entry["label"]: entry["similarity"] for entry in ranking if entry["label"] in SETTINGS["conditions"]}
    for candidate, counterpart, name in (
        ("a night photograph", "a daytime photograph", "night"),
        ("a backlit photograph", "an evenly lit photograph", "backlit"),
        ("a blurry photograph", "a sharp photograph", "blurred"),
        ("a hazy photograph", "a clear photograph", "hazy"),
    ):
        if candidate in condition_scores and counterpart in condition_scores and condition_scores[candidate] > condition_scores[counterpart] + 1.5:
            condition.append(name)
    preset = "architecture-clarity" if noun in {"opera house", "parliament building", "church", "cathedral", "museum", "palace", "castle", "bridge", "monument", "building facade"} else "natural-balance"
    description = f"Travel photograph of {noun}." if noun else ""
    proposal = {"primary_subject": noun, "content_tags": tags, "condition_tags": condition,
                "editorial_description": description, "preset_id": preset,
                "city": location["city"] or "", "country": location["country"] or ""}
    evidence = {"top_labels": content[:5], "conditions": condition_scores, "location": location,
                "measurements": result.get("measurements", {}),
                "exif": {"capture_datetime_raw": photo["capture_datetime_raw"], "camera": photo["camera"]},
                "filename_hint": photo["original_filename"],
                "warning": "Relative model similarity, not a probability. Verify visually; no exact landmark or location inferred."}
    return proposal, evidence


def suggest(root: Path, photo_ids: list[str], manager: ModelManager, *, authorized: bool, offline: bool = False) -> list[dict]:
    if not authorized:
        raise PermissionError("Authorize this local recognition run")
    if not photo_ids or len(photo_ids) > MAX_BATCH or len(set(photo_ids)) != len(photo_ids):
        raise ValueError("Select 1 to 20 distinct photos")
    db = connect(root)
    try:
        cities = db.execute("SELECT * FROM visited_cities ORDER BY id").fetchall()
        results = []
        for photo_id in photo_ids:
            photo = db.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
            if photo is None:
                raise ReviewNotFound(photo_id)
            source = Path(photo["original_path"])
            if not source.is_file() and photo["managed_original_path"]:
                source = root / photo["managed_original_path"]
            if not source.is_file() or _hash(source) != photo["sha256"]:
                raise ReviewConflict("Original or managed source is missing or changed")
            fingerprint = _fingerprint(photo, cities)
            existing = db.execute("SELECT * FROM catalog_suggestions WHERE photo_id=? AND fingerprint=?", (photo_id, fingerprint)).fetchone()
            if existing:
                results.append(_public_suggestion(existing) | {"cached": True, "original_filename": photo["original_filename"]})
                continue
            thumbnail = root / photo["thumbnail_path"]
            if not thumbnail.is_file() or _hash(thumbnail) != photo["thumbnail_sha256"]:
                raise ReviewConflict("Verified thumbnail is missing or changed")
            inference = manager.classify(thumbnail, offline=offline)
            location = match_city(photo, cities)
            proposed, evidence = _proposal(photo, inference, location)
            identity = str(uuid4())
            db.execute("INSERT INTO catalog_suggestions(id,photo_id,source_sha256,fingerprint,model_id,model_revision,settings_json,evidence_json,proposed_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (identity, photo_id, photo["sha256"], fingerprint, MANIFEST["model_id"], MANIFEST["revision"],
                        json.dumps(SETTINGS), json.dumps(evidence), json.dumps(proposed), utc_now()))
            db.commit()
            results.append(_public_suggestion(db.execute("SELECT * FROM catalog_suggestions WHERE id=?", (identity,)).fetchone()) | {"cached": False, "original_filename": photo["original_filename"]})
        return results
    finally:
        db.close()


def _public_suggestion(row) -> dict:
    return {"id": row["id"], "photo_id": row["photo_id"], "status": row["status"],
            "created_at": row["created_at"], "model_id": row["model_id"], "model_revision": row["model_revision"],
            "proposed": json.loads(row["proposed_json"]), "evidence": json.loads(row["evidence_json"]),
            "applied": json.loads(row["applied_json"]) if row["applied_json"] else None}


def suggestions(root: Path, photo_id: str) -> list[dict]:
    db = connect(root)
    try:
        if not db.execute("SELECT 1 FROM photos WHERE id=?", (photo_id,)).fetchone():
            raise ReviewNotFound(photo_id)
        return [_public_suggestion(row) for row in db.execute("SELECT * FROM catalog_suggestions WHERE photo_id=? ORDER BY created_at DESC", (photo_id,))]
    finally:
        db.close()


def decide(root: Path, suggestion_id: str, fields: list[str], expected_revision: int, dismiss: bool = False) -> dict:
    if set(fields) - FIELDS or not fields and not dismiss:
        raise ValueError("Choose valid fields to accept")
    db = connect(root)
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM catalog_suggestions WHERE id=?", (suggestion_id,)).fetchone()
        if row is None:
            raise ReviewNotFound(suggestion_id)
        if row["status"] != "PENDING":
            raise ReviewConflict("Suggestion already decided")
        before = _snapshot(db, row["photo_id"])
        if before["revision"] != expected_revision or before["source_sha256"] != row["source_sha256"]:
            raise ReviewConflict("Photo or source changed; reload before accepting")
        current_photo = db.execute("SELECT sha256, thumbnail_sha256 FROM photos WHERE id=?", (row["photo_id"],)).fetchone()
        cities = db.execute("SELECT id, revision FROM visited_cities ORDER BY id").fetchall()
        if _fingerprint(current_photo, cities) != row["fingerprint"]:
            raise ReviewConflict("Suggestion is stale after city or model settings changed; rerun recognition")
        after = dict(before)
        proposed = json.loads(row["proposed_json"])
        applied_fields = []
        for field in fields:
            if field in {"city", "country"} and (before["city"] or before["country"] or not proposed["city"] or not proposed["country"]):
                continue
            if field in {"content_tags", "condition_tags"}:
                additions = [tag for tag in proposed[field] if tag.lower() not in {t.lower() for t in before[field]}]
                if additions:
                    after[field] = before[field] + additions
                    applied_fields.append(field)
            elif not before[field] and proposed[field]:
                after[field] = proposed[field]
                applied_fields.append(field)
        if "city" in applied_fields or "country" in applied_fields:
            after["city"], after["country"] = proposed["city"], proposed["country"]
            applied_fields = list(set(applied_fields) | {"city", "country"})
        saved = _write(db, row["photo_id"], before, after) if applied_fields else before
        applied = {"before": before, "after": saved, "fields": applied_fields} if applied_fields else None
        db.execute("UPDATE catalog_suggestions SET status=?, applied_json=?, decided_at=? WHERE id=?",
                   ("DISMISSED" if dismiss or not applied_fields else "ACCEPTED", json.dumps(applied) if applied else None, utc_now(), suggestion_id))
        db.commit()
        return {"suggestion": _public_suggestion(db.execute("SELECT * FROM catalog_suggestions WHERE id=?", (suggestion_id,)).fetchone()), "photo": _photo(db, row["photo_id"])}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def undo(root: Path, suggestion_id: str) -> dict:
    db = connect(root)
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM catalog_suggestions WHERE id=?", (suggestion_id,)).fetchone()
        if row is None:
            raise ReviewNotFound(suggestion_id)
        if row["status"] != "ACCEPTED":
            raise ReviewConflict("Only accepted suggestions can be undone")
        applied = json.loads(row["applied_json"])
        current = _snapshot(db, row["photo_id"])
        if current != applied["after"]:
            raise ReviewConflict("Metadata changed after acceptance; undo manually to preserve later edits")
        _write(db, row["photo_id"], current, applied["before"])
        db.execute("UPDATE catalog_suggestions SET status='UNDONE', decided_at=? WHERE id=?", (utc_now(), suggestion_id))
        db.commit()
        return {"suggestion": _public_suggestion(db.execute("SELECT * FROM catalog_suggestions WHERE id=?", (suggestion_id,)).fetchone()), "photo": _photo(db, row["photo_id"])}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def bulk_location(root: Path, photo_ids: list[str], city_id: str, *, apply: bool = False, expected_revisions: dict[str, int] | None = None) -> dict:
    if not photo_ids or len(photo_ids) > MAX_BATCH or len(set(photo_ids)) != len(photo_ids):
        raise ValueError("Select 1 to 20 distinct photos")
    db = connect(root)
    try:
        db.execute("BEGIN IMMEDIATE")
        city = db.execute("SELECT * FROM visited_cities WHERE id=?", (city_id,)).fetchone()
        if city is None:
            raise ReviewNotFound(city_id)
        items = []
        for photo_id in photo_ids:
            before = _snapshot(db, photo_id)
            if apply and (expected_revisions is None or expected_revisions.get(photo_id) != before["revision"]):
                raise ReviewConflict("Bulk location preview is stale; preview again")
            eligible = not before["city"] and not before["country"]
            items.append({"photo_id": photo_id, "eligible": eligible, "reason": "Already has editorial location" if not eligible else "Empty location", "revision": before["revision"]})
        if not apply:
            db.rollback()
            return {"city": city["city"], "country": city["country"], "items": items}
        changes = []
        for item in items:
            if item["eligible"]:
                before = _snapshot(db, item["photo_id"])
                after = dict(before) | {"city": city["city"], "country": city["country"]}
                saved = _write(db, item["photo_id"], before, after)
                changes.append({"photo_id": item["photo_id"], "before": before, "after": saved})
        identity = str(uuid4())
        db.execute("INSERT INTO catalog_location_batches VALUES (?,?,?,?,?,NULL)",
                   (identity, city["city"], city["country"], json.dumps(changes), utc_now()))
        db.commit()
        return {"id": identity, "city": city["city"], "country": city["country"], "items": items, "applied_count": len(changes)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def undo_bulk_location(root: Path, batch_id: str) -> dict:
    db = connect(root)
    try:
        db.execute("BEGIN IMMEDIATE")
        batch = db.execute("SELECT * FROM catalog_location_batches WHERE id=?", (batch_id,)).fetchone()
        if batch is None:
            raise ReviewNotFound(batch_id)
        if batch["undone_at"]:
            raise ReviewConflict("Location batch already undone")
        changes = json.loads(batch["applied_json"])
        for change in changes:
            if _snapshot(db, change["photo_id"]) != change["after"]:
                raise ReviewConflict("A photo changed after bulk assignment; no locations were undone")
        for change in changes:
            _write(db, change["photo_id"], change["after"], change["before"])
        db.execute("UPDATE catalog_location_batches SET undone_at=? WHERE id=?", (utc_now(), batch_id))
        db.commit()
        return {"id": batch_id, "undone_count": len(changes)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
