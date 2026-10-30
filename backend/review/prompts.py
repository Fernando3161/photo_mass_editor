"""Deterministic prompt assembly, conflict detection, and immutable prompt versions."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any
from uuid import uuid4

from backend.catalog.ingestion import utc_now


POLICY_VERSION = "authentic-travel-v1"
COMPILER_VERSION = "phase03-deterministic-v1"
TARGETS = ("sky", "people", "person", "face", "building", "architecture", "background", "statue", "sculpture")


class PromptConflict(RuntimeError):
    def __init__(self, conflicts: list[str]):
        super().__init__("; ".join(conflicts))
        self.conflicts = conflicts


def detect_conflicts(*texts: str, allowance: int, semantic_change_consent: bool) -> list[str]:
    combined = " ".join(texts).lower()
    conflicts: list[str] = []
    for target in TARGETS:
        preserve = re.search(rf"\b(preserve|keep|retain|unchanged)\b[^.!?]{{0,50}}\b{re.escape(target)}\b", combined)
        change = re.search(rf"\b(remove|replace|invent|change|alter)\b[^.!?]{{0,50}}\b{re.escape(target)}\b", combined)
        if preserve and change:
            conflicts.append(f"Conflicting instructions for {target}: preserve and change are both requested")
    if allowance > 3 and not semantic_change_consent:
        conflicts.append("AI allowance above 3 requires explicit semantic-change consent")
    return conflicts


def _snapshot(db: sqlite3.Connection, photo_id: str) -> tuple[dict[str, Any], sqlite3.Row, sqlite3.Row]:
    photo = db.execute(
        "SELECT id, sha256, revision, primary_subject_id FROM photos WHERE id = ?", (photo_id,)
    ).fetchone()
    if photo is None:
        raise KeyError(photo_id)
    draft = db.execute(
        """SELECT d.*, p.name AS preset_name, p.version AS preset_version,
                  p.structured_instructions AS preset_instructions
           FROM review_drafts d LEFT JOIN presets p ON p.id=d.preset_id
           WHERE d.photo_id=?""",
        (photo_id,),
    ).fetchone()
    if draft is None:
        raise ValueError("Save the editing draft before compiling a prompt")
    subject = db.execute(
        "SELECT display_name FROM subjects WHERE id=?", (photo["primary_subject_id"],)
    ).fetchone()
    tags = [dict(row) for row in db.execute(
        """SELECT t.display_name, t.kind, pt.source, pt.user_confirmed
           FROM photo_tags pt JOIN tags t ON t.id=pt.tag_id
           WHERE pt.photo_id=? ORDER BY t.kind, lower(t.display_name)""",
        (photo_id,),
    )]
    snapshot = {
        "source_hash": photo["sha256"],
        "primary_subject": subject["display_name"] if subject else None,
        "tags": tags,
        "preset": {
            "id": draft["preset_id"],
            "name": draft["preset_name"],
            "version": draft["preset_version"],
            "instructions": draft["preset_instructions"],
        },
        "ai_allowance": draft["ai_allowance"],
        "semantic_change_consent": bool(draft["semantic_change_consent"]),
        "ai_suggestion": draft["ai_suggestion_editable"],
        "user_instructions": draft["user_instructions"],
        "approved_constraints": draft["approved_constraints"],
        "analysis_run_id": draft["analysis_run_id"],
    }
    return snapshot, photo, draft


def compile_text(snapshot: dict[str, Any]) -> tuple[str, list[str]]:
    conflicts = detect_conflicts(
        snapshot["preset"]["instructions"] or "",
        snapshot["ai_suggestion"],
        snapshot["user_instructions"],
        snapshot["approved_constraints"],
        allowance=snapshot["ai_allowance"],
        semantic_change_consent=snapshot["semantic_change_consent"],
    )
    if conflicts:
        return "", conflicts
    tags = ", ".join(tag["display_name"] for tag in snapshot["tags"]) or "none recorded"
    parts = [
        "Edit this travel photograph while preserving documentary authenticity.",
        "Prefer deterministic tonal, color, lens, perspective, crop, sharpening, and denoise corrections.",
        f"Primary subject: {snapshot['primary_subject'] or 'not specified'}.",
        f"Observed tags: {tags}.",
    ]
    if snapshot["preset"]["instructions"]:
        parts.append(f"Selected preset v{snapshot['preset']['version']}: {snapshot['preset']['instructions']}")
    if snapshot["ai_suggestion"].strip():
        parts.append(f"Editable analysis suggestion: {snapshot['ai_suggestion'].strip()}")
    if snapshot["user_instructions"].strip():
        parts.append(f"Owner instructions: {snapshot['user_instructions'].strip()}")
    if snapshot["approved_constraints"].strip():
        parts.append(f"Approved constraints: {snapshot['approved_constraints'].strip()}")
    parts.append(f"Application AI allowance: {snapshot['ai_allowance']} of 10.")
    if not snapshot["semantic_change_consent"]:
        parts.append("Do not introduce semantic changes or new scene content.")
    parts.append("Return a separate edited version; never alter the source file.")
    return "\n".join(parts), []


def create_compiled_prompt(db: sqlite3.Connection, photo_id: str) -> dict[str, Any]:
    snapshot, photo, draft = _snapshot(db, photo_id)
    text, conflicts = compile_text(snapshot)
    if conflicts:
        raise PromptConflict(conflicts)
    version = db.execute(
        "SELECT COALESCE(MAX(version_number), 0) + 1 FROM compiled_prompts WHERE photo_id=?", (photo_id,)
    ).fetchone()[0]
    prompt_id = str(uuid4())
    now = utc_now()
    db.execute(
        """INSERT INTO compiled_prompts(
               id, photo_id, version_number, source_hash, photo_revision, draft_revision,
               policy_version, compiler_version, input_snapshot_json, compiled_text,
               user_modified, approved_for_job, generated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)""",
        (prompt_id, photo_id, version, photo["sha256"], photo["revision"], draft["revision"],
         POLICY_VERSION, COMPILER_VERSION, json.dumps(snapshot, sort_keys=True), text, now),
    )
    db.execute("UPDATE review_drafts SET compiled_prompt_stale=0 WHERE photo_id=?", (photo_id,))
    return get_prompt(db, prompt_id)


def get_prompt(db: sqlite3.Connection, prompt_id: str) -> dict[str, Any]:
    row = db.execute("SELECT * FROM compiled_prompts WHERE id=?", (prompt_id,)).fetchone()
    if row is None:
        raise KeyError(prompt_id)
    item = dict(row)
    item["input_snapshot"] = json.loads(item.pop("input_snapshot_json"))
    item["input_snapshot"].pop("source_hash", None)
    item.pop("source_hash", None)
    return item


def revise_prompt(db: sqlite3.Connection, prompt_id: str, compiled_text: str) -> dict[str, Any]:
    prior = db.execute("SELECT * FROM compiled_prompts WHERE id=?", (prompt_id,)).fetchone()
    if prior is None:
        raise KeyError(prompt_id)
    version = db.execute(
        "SELECT COALESCE(MAX(version_number), 0) + 1 FROM compiled_prompts WHERE photo_id=?",
        (prior["photo_id"],),
    ).fetchone()[0]
    new_id = str(uuid4())
    db.execute(
        """INSERT INTO compiled_prompts(
               id, photo_id, version_number, parent_prompt_id, source_hash, photo_revision,
               draft_revision, policy_version, compiler_version, input_snapshot_json,
               compiled_text, user_modified, approved_for_job, generated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?)""",
        (new_id, prior["photo_id"], version, prior["id"], prior["source_hash"],
         prior["photo_revision"], prior["draft_revision"], prior["policy_version"],
         prior["compiler_version"], prior["input_snapshot_json"], compiled_text.strip(), utc_now()),
    )
    return get_prompt(db, new_id)


def approve_prompt(db: sqlite3.Connection, prompt_id: str) -> dict[str, Any]:
    prompt = db.execute("SELECT * FROM compiled_prompts WHERE id=?", (prompt_id,)).fetchone()
    if prompt is None:
        raise KeyError(prompt_id)
    current = db.execute(
        """SELECT p.sha256, p.revision AS photo_revision, d.revision AS draft_revision,
                  d.compiled_prompt_stale
           FROM photos p JOIN review_drafts d ON d.photo_id=p.id WHERE p.id=?""",
        (prompt["photo_id"],),
    ).fetchone()
    if (current is None or current["sha256"] != prompt["source_hash"]
            or current["photo_revision"] != prompt["photo_revision"]
            or current["draft_revision"] != prompt["draft_revision"]
            or current["compiled_prompt_stale"]):
        raise PromptConflict(["The photo or editing draft changed; compile a new prompt before approval"])
    db.execute("UPDATE compiled_prompts SET approved_for_job=0, approved_at=NULL WHERE photo_id=?", (prompt["photo_id"],))
    db.execute(
        "UPDATE compiled_prompts SET approved_for_job=1, approved_at=? WHERE id=?", (utc_now(), prompt_id)
    )
    return get_prompt(db, prompt_id)


def prompt_history(db: sqlite3.Connection, photo_id: str) -> list[dict[str, Any]]:
    return [get_prompt(db, row["id"]) for row in db.execute(
        "SELECT id FROM compiled_prompts WHERE photo_id=? ORDER BY version_number DESC", (photo_id,)
    )]
