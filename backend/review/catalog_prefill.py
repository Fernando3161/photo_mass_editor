"""Reviewable local catalog suggestions and private visited-city matching."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4

from backend.catalog.database import connect
from backend.catalog.ingestion import utc_now
from .local_model import MANIFEST, SETTINGS, ModelManager
from .ontology import load_ontology
from .service import ReviewConflict, ReviewNotFound, _photo, _slug, _tags, _upsert_subject

MAX_BATCH = 20
FIELDS = {"primary_subject", "content_tags", "condition_tags", "editorial_description", "preset_id", "city", "country"}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint(photo, cities, ontology_hash: str) -> str:
    city_version = [(row["id"], row["revision"]) for row in cities]
    return hashlib.sha256(json.dumps([photo["sha256"], photo["thumbnail_sha256"], MANIFEST["revision"], SETTINGS, ontology_hash, city_version], sort_keys=True).encode()).hexdigest()


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


SUBJECT_TAGS = {
    "people": ("people",), "architecture_and_history": (),
    "urban_and_daily_life": ("urban",), "nature_and_landscapes": ("landscape", "nature"),
    "animals_and_transport": (),
}
SPECIFIC_TAGS = {
    "building": ("architecture",), "religious building": ("architecture", "religion"),
    "palace": ("architecture", "heritage"), "castle or fortress": ("architecture", "heritage"),
    "tower": ("architecture",), "bridge": ("architecture", "infrastructure"),
    "monument": ("heritage",),
    "archaeological ruins": ("archaeology", "heritage", "architecture"),
    "sculpture": ("art",), "artwork": ("art",), "museum artifact": ("museum", "art"),
    "river": ("water",), "lake": ("water",), "waterfall": ("water",),
    "beach": ("coast", "water"), "coastline": ("coast", "water"),
    "cat": ("animals",), "dog": ("animals",), "other animal": ("animals",),
    "boat": ("transport",), "train": ("transport",), "vehicle": ("transport",),
    "food": ("food",), "market": ("markets",), "souvenir": ("souvenirs",),
}


def _proposal(photo, result: dict, location: dict, ontology: dict) -> tuple[dict, dict]:
    # Scores are model similarities, never confidence probabilities. Compare within each
    # independently scored vocabulary group and retain the margin in evidence.
    scores = {entry["label"]: float(entry["similarity"]) for entry in result["ranking"]}
    groups = {}
    for kind, concepts in ontology["concepts"].items():
        ranked = sorted(((name, scores[f"{kind}:{name}"]) for name, _, _ in concepts.values()
                         if f"{kind}:{name}" in scores), key=lambda item: item[1], reverse=True)
        groups[kind] = ranked
    subjects = groups["primary_subject"]
    median = sorted(value for _, value in subjects)[len(subjects) // 2] if subjects else 0
    subject_strength = subjects[0][1] - median if subjects else 0
    subject_margin = round(subjects[0][1] - subjects[1][1], 3) if len(subjects) > 1 else None
    noun = subjects[0][0] if subjects and subject_strength >= 2.0 and (
        subject_margin is None or subject_margin >= 1.0 or subject_strength >= 3.2 and subject_margin >= .3) else ""
    if noun == "museum artifact" and subject_margin is not None and subject_margin < 1.4:
        noun = ""
    if not noun and subjects and subject_strength >= 2.5 and subject_margin is not None and subject_margin < 1.0:
        # Two close specific labels in the same family can still justify a broad label.
        categories = ontology["concepts"]["primary_subject"]
        first_family = categories[subjects[0][0].casefold()][1]
        second_family = categories[subjects[1][0].casefold()][1]
        architecture_subjects = {"building", "religious building", "palace", "castle or fortress", "tower"}
        animal_subjects = {"cat", "dog", "other animal"}
        pair = {subjects[0][0], subjects[1][0]}
        fallback = ("building" if pair <= architecture_subjects else
                    "other animal" if pair <= animal_subjects else
                    subjects[0][0] if {name for name, _ in subjects[:3]} <= {"skyline", "street", "square"} else
                    "person" if first_family == "people" else "")
        noun = fallback if first_family == second_family and fallback and fallback.casefold() in categories else ""
    content_scores = groups["content_tags"]
    content_median = sorted(value for _, value in content_scores)[len(content_scores) // 2] if content_scores else 0
    tags = []
    allowed = {item[0].casefold() for item in content_scores}
    if noun:
        family = ontology["concepts"]["primary_subject"][noun.casefold()][1]
        for name in (*SUBJECT_TAGS.get(family, ()), *SPECIFIC_TAGS.get(noun, ())):
            if name.casefold() in allowed and name not in tags:
                tags.append(name)
    # Independent content evidence needs separation from nearby alternatives.
    # A supported subject can add its broad tags even when content prompts tie.
    if content_scores:
        lead, lead_score = content_scores[0]
        lead_gap = lead_score - content_scores[1][1] if len(content_scores) > 1 else lead_score - content_median
        if lead_score >= content_median + 2.5 and lead_gap >= (2.0 if noun else 1.0):
            for name, value in content_scores:
                if value >= max(content_median + 2.5, lead_score - 3.0) and name not in tags:
                    tags.append(name)
        for name, value in content_scores:
            if name in {"people", "animals", "water"} and value >= content_median + 2.5 and name not in tags:
                tags.append(name)
    tags = tags[:5]
    condition_scores = groups["condition_tags"]
    condition_median = sorted(value for _, value in condition_scores)[len(condition_scores) // 2] if condition_scores else 0
    condition = []
    measured_light = result.get("measurements", {}).get("mean_luminance")
    day_score = scores.get("condition_tags:daytime", 0)
    night_score = scores.get("condition_tags:nighttime", 0)
    outdoor_subjects = {"building", "religious building", "palace", "castle or fortress", "tower", "bridge", "monument", "archaeological ruins",
                        "street", "square", "skyline", "harbor", "mountain", "valley", "forest", "garden",
                        "beach", "coastline", "river", "lake", "waterfall", "desert"}
    outdoor = noun in outdoor_subjects or bool({"landscape", "nature", "coast"} & set(tags))
    if "nighttime" in ontology["concepts"]["condition_tags"] and night_score >= condition_median + 2.0 and night_score >= day_score + 1.0 and measured_light is not None and measured_light < .35:
        condition.append("nighttime")
    elif "daytime" in ontology["concepts"]["condition_tags"] and (day_score >= condition_median + 1.0 or outdoor and measured_light is not None and measured_light >= .42):
        condition.append("daytime")
    if condition_scores:
        top_condition, top_score = condition_scores[0]
        gap = top_score - condition_scores[1][1] if len(condition_scores) > 1 else top_score - condition_median
        if top_condition not in {"daytime", "nighttime"} and top_score >= condition_median + 4.0 and gap >= 2.0:
            condition.append(top_condition)
    architecture = "architecture" in tags or noun in {"building", "religious building", "palace", "castle or fortress", "tower", "bridge", "archaeological ruins"}
    people = "people" in tags or noun in {"person", "group", "crowd"}
    art = "art" in tags or noun in {"artwork", "sculpture", "museum artifact"}
    landscape = "landscape" in tags or "nature" in tags
    if architecture and "nighttime" in condition:
        preset, local_recipe, reason = "night-architecture", "night", "Architecture with a supported nighttime condition"
    elif art:
        preset, local_recipe, reason = "museum-artwork", "artwork", "Artwork or museum object is visible"
    elif noun in {"group", "crowd"}:
        preset, local_recipe, reason = "group-photo", "people", "Multiple people are visible"
    elif people:
        preset, local_recipe, reason = "portrait-gentle", "people", "People are visible"
    elif architecture:
        preset, local_recipe, reason = "architecture-clarity", "architecture", "Architectural content is visible"
    elif "food" in tags or noun == "food":
        preset, local_recipe, reason = "food", "natural", "Food is visible"
    elif landscape or noun in {"skyline", "harbor", "coastline", "valley"} and photo["width"] / max(1, photo["height"]) > 1.8:
        preset, local_recipe, reason = "panoramic-scene", "landscape", "Landscape or wide composition is visible"
    else:
        preset, local_recipe, reason = "natural-balance", "natural", "No specialized rule is well supported"
    other = " with people in view" if people and noun not in {"person", "group", "crowd"} else ""
    lighting = "Daytime " if "daytime" in condition else "Nighttime " if "nighttime" in condition else ""
    if noun:
        label = "animal" if noun == "other animal" else noun
        article = "" if noun in {"archaeological ruins", "artwork", "food"} else "an " if label[0] in "aeiou" else "a "
        description = f"{lighting}travel photograph of {article}{label}{other}."
    elif tags:
        description = f"{lighting}travel photograph showing {' and '.join(tags[:2])}."
    else:
        description = ""
    proposal = {"primary_subject": noun, "content_tags": tags, "condition_tags": condition,
                "editorial_description": description, "preset_id": preset,
                "city": location["city"] or "", "country": location["country"] or ""}
    evidence = {"top_labels": [{"label": name, "similarity": value} for name, value in subjects[:5]],
                "content_scores": content_scores, "conditions": dict(condition_scores), "subject_margin": subject_margin,
                "preset_reason": reason, "local_recipe": local_recipe, "ontology_sha256": ontology["sha256"],
                "location": location,
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
        ontology = load_ontology()
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
            fingerprint = _fingerprint(photo, cities, ontology["sha256"])
            existing = db.execute("SELECT * FROM catalog_suggestions WHERE photo_id=? AND fingerprint=?", (photo_id, fingerprint)).fetchone()
            if existing:
                results.append(_public_suggestion(existing) | {"cached": True, "original_filename": photo["original_filename"]})
                continue
            thumbnail = root / photo["thumbnail_path"]
            if not thumbnail.is_file() or _hash(thumbnail) != photo["thumbnail_sha256"]:
                raise ReviewConflict("Verified thumbnail is missing or changed")
            inference = manager.classify(thumbnail, offline=offline)
            location = match_city(photo, cities)
            proposed, evidence = _proposal(photo, inference, location, ontology)
            identity = str(uuid4())
            db.execute("INSERT INTO catalog_suggestions(id,photo_id,source_sha256,fingerprint,model_id,model_revision,settings_json,evidence_json,proposed_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (identity, photo_id, photo["sha256"], fingerprint, MANIFEST["model_id"], MANIFEST["revision"],
                        json.dumps(SETTINGS | {"ontology_sha256": ontology["sha256"]}), json.dumps(evidence), json.dumps(proposed), utc_now()))
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


def decide(root: Path, suggestion_id: str, fields: list[str], expected_revision: int, dismiss: bool = False,
           overrides: dict | None = None) -> dict:
    if set(fields) - FIELDS or not fields and not dismiss:
        raise ValueError("Choose valid fields to accept")
    if overrides and set(overrides) - set(fields):
        raise ValueError("Only selected suggestion fields can be edited")
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
        if _fingerprint(current_photo, cities, load_ontology()["sha256"]) != row["fingerprint"]:
            raise ReviewConflict("Suggestion is stale after city or model settings changed; rerun recognition")
        after = dict(before)
        proposed = json.loads(row["proposed_json"])
        if overrides:
            for field, value in overrides.items():
                if field in {"content_tags", "condition_tags"}:
                    if not isinstance(value, list) or any(not isinstance(tag, str) for tag in value):
                        raise ValueError(f"{field} must be a list of labels")
                    proposed[field] = list(dict.fromkeys(tag.strip() for tag in value if tag.strip()))
                elif not isinstance(value, str):
                    raise ValueError(f"{field} must be text")
                else:
                    proposed[field] = value.strip()
        if proposed.get("preset_id") and "preset_id" in fields and not db.execute("SELECT 1 FROM presets WHERE id=?", (proposed["preset_id"],)).fetchone():
            raise ValueError("Unknown draft preset")
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
        applied = {"before": before, "after": saved, "fields": applied_fields, "overrides": overrides or {}} if applied_fields else None
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
