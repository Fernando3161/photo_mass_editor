"""Per-photo generative prompt preparation with explicit selection review."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.catalog.database import connect
from .prompts import PromptConflict, _snapshot, approve_prompt, compile_text, create_compiled_prompt


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def preview(data_dir: Path, photo_ids: list[str], shared_instruction: str = "") -> dict:
    if not 1 <= len(photo_ids) <= 200 or len(set(photo_ids)) != len(photo_ids):
        raise ValueError("Choose 1 to 200 distinct photos")
    if len(shared_instruction) > 2000:
        raise ValueError("Shared instruction is too long")
    db = connect(data_dir)
    try:
        items = []
        for photo_id in photo_ids:
            try:
                snapshot, photo, draft = _snapshot(db, photo_id, shared_instruction)
                proposed, conflicts = compile_text(snapshot)
                if conflicts:
                    raise PromptConflict(conflicts)
                prior = db.execute("SELECT compiled_text FROM compiled_prompts WHERE photo_id=? ORDER BY version_number DESC LIMIT 1", (photo_id,)).fetchone()
                items.append({"photo_id": photo_id, "eligible": True, "proposed_text": proposed,
                              "previous_text": prior[0] if prior else "", "photo_revision": photo["revision"],
                              "draft_revision": draft["revision"], "profile_id": snapshot["publication_profile"]["id"],
                              "rule_config_sha256": snapshot["rule_suggestions"]["config_sha256"],
                              "ontology_sha256": snapshot["rule_suggestions"]["ontology_sha256"],
                              "source_hash": photo["sha256"], "allowance": snapshot["ai_allowance"],
                              "semantic_change_consent": snapshot["semantic_change_consent"]})
            except (KeyError, ValueError, PromptConflict) as exc:
                items.append({"photo_id": photo_id, "eligible": False, "reason": str(exc) if not isinstance(exc, KeyError) else "Photo not found"})
        signature = _hash([items, shared_instruction])
        for item in items:
            item.pop("source_hash", None)
        return {"items": items, "signature": signature}
    finally:
        db.close()


def compile_selected(data_dir: Path, photo_ids: list[str], shared_instruction: str,
                     preview_signature: str, acknowledged_ids: list[str]) -> list[dict]:
    plan = preview(data_dir, photo_ids, shared_instruction)
    eligible = {item["photo_id"] for item in plan["items"] if item["eligible"]}
    selected = set(acknowledged_ids)
    if (plan["signature"] != preview_signature or not selected or not selected <= eligible
            or len(selected) != len(acknowledged_ids)):
        raise ValueError("Prompt preview changed or selected per-photo diffs were not eligible")
    db = connect(data_dir)
    try:
        db.execute("BEGIN IMMEDIATE")
        for item in plan["items"]:
            if item["photo_id"] not in selected:
                continue
            snapshot, photo, draft = _snapshot(db, item["photo_id"], shared_instruction)
            current_text, conflicts = compile_text(snapshot)
            if (conflicts or current_text != item["proposed_text"]
                    or photo["revision"] != item["photo_revision"]
                    or draft["revision"] != item["draft_revision"]
                    or snapshot["rule_suggestions"]["config_sha256"] != item["rule_config_sha256"]
                    or snapshot["rule_suggestions"]["ontology_sha256"] != item["ontology_sha256"]
                    or snapshot["publication_profile"]["id"] != item["profile_id"]):
                raise ValueError("A photo or draft changed after prompt preview")
        result = [create_compiled_prompt(db, photo_id, shared_instruction) for photo_id in photo_ids if photo_id in selected]
        db.commit()
        return [{**prompt, "approval_hash": _hash([prompt["id"], prompt["compiled_text"], prompt["input_snapshot"]])} for prompt in result]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def approve_selected(data_dir: Path, expected: dict[str, str]) -> list[dict]:
    if not 1 <= len(expected) <= 200:
        raise ValueError("Choose 1 to 200 prompts")
    db = connect(data_dir)
    try:
        db.execute("BEGIN IMMEDIATE")
        prompts = []
        photos = set()
        for prompt_id, expected_hash in expected.items():
            row = db.execute("SELECT id,photo_id,compiled_text,input_snapshot_json FROM compiled_prompts WHERE id=?", (prompt_id,)).fetchone()
            if row is None or row["photo_id"] in photos:
                raise ValueError("Each prompt must belong to a distinct photo")
            photos.add(row["photo_id"])
            snapshot = json.loads(row["input_snapshot_json"])
            snapshot.pop("source_hash", None)
            if _hash([prompt_id, row["compiled_text"], snapshot]) != expected_hash:
                raise ValueError("A prompt changed after the approval preview")
            prompts.append(approve_prompt(db, prompt_id))
        db.commit()
        return prompts
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
