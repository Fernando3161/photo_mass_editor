"""Deterministic prompt assembly, conflict detection, and immutable prompt versions."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any
from uuid import uuid4

from backend.catalog.ingestion import utc_now
from .prompt_rules import compose, load_rules


POLICY_VERSION = "authentic-travel-v1"
COMPILER_VERSION = "ontology-rules-v1"
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
    semantic_request = re.search(r"\b(remove|replace|invent|add|insert)\b[^.!?]{0,50}\b(people|person|face|sky|building|architecture|background|statue|sculpture|object)\b", combined)
    if semantic_request and (allowance == 0 or not semantic_change_consent):
        conflicts.append("Requested scene changes require nonzero allowance and explicit semantic-change consent")
    return conflicts


def _snapshot(db: sqlite3.Connection, photo_id: str, shared_instruction: str = "",
              allow_missing_draft: bool = False) -> tuple[dict[str, Any], sqlite3.Row, sqlite3.Row | dict]:
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
        if not allow_missing_draft:
            raise ValueError("Save the editing draft before compiling a prompt")
        draft = {"publication_profile_id": "website-standard-v1", "preset_id": None,
                 "preset_name": None, "preset_version": None, "preset_instructions": None,
                 "ai_allowance": 0, "semantic_change_consent": 0, "ai_suggestion_editable": "",
                 "user_instructions": "", "approved_constraints": "", "analysis_run_id": None,
                 "rule_suggestions_enabled": 1, "rule_selected_ids_json": None,
                 "rule_instructions_override": None}
    profile = db.execute(
        """SELECT id, version, name, image_format, file_extension, mime, max_long_edge,
                  quality, color_space, preserve_aspect_ratio, allow_upscale, strip_metadata
           FROM publication_profiles WHERE id=? AND active=1""",
        (draft["publication_profile_id"],),
    ).fetchone()
    if profile is None:
        raise ValueError("Select an active publication profile before compiling a prompt")
    subject = db.execute(
        "SELECT display_name FROM subjects WHERE id=?", (photo["primary_subject_id"],)
    ).fetchone()
    tags = [dict(row) for row in db.execute(
        """SELECT t.display_name, t.kind, pt.source, pt.user_confirmed
           FROM photo_tags pt JOIN tags t ON t.id=pt.tag_id
           WHERE pt.photo_id=? ORDER BY t.kind, lower(t.display_name)""",
        (photo_id,),
    )]
    rules = compose(subject["display_name"] if subject else None,
                    [tag["display_name"] for tag in tags if tag["kind"] == "CONTENT"],
                    [tag["display_name"] for tag in tags if tag["kind"] == "CONDITION"],
                    json.loads(draft["rule_selected_ids_json"]) if draft["rule_selected_ids_json"] is not None else None,
                    bool(draft["rule_suggestions_enabled"]), bool(draft["semantic_change_consent"]))
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
        "rule_suggestions": rules,
        "rule_instructions": (draft["rule_instructions_override"] if draft["rule_instructions_override"] is not None
                              else rules["instructions"]) if draft["rule_suggestions_enabled"] else "",
        "rule_instructions_override": draft["rule_instructions_override"],
        "user_instructions": draft["user_instructions"],
        "approved_constraints": draft["approved_constraints"],
        "shared_instruction": shared_instruction,
        "analysis_run_id": draft["analysis_run_id"],
        "publication_profile": {
            **dict(profile),
            "preserve_aspect_ratio": bool(profile["preserve_aspect_ratio"]),
            "allow_upscale": bool(profile["allow_upscale"]),
            "strip_metadata": bool(profile["strip_metadata"]),
        },
    }
    return snapshot, photo, draft


def compile_text(snapshot: dict[str, Any]) -> tuple[str, list[str]]:
    conflicts = list(snapshot.get("rule_suggestions", {}).get("conflicts", [])) + detect_conflicts(
        snapshot["preset"]["instructions"] or "",
        snapshot.get("rule_instructions", ""),
        snapshot.get("rule_suggestions", {}).get("constraints", ""),
        snapshot["ai_suggestion"],
        snapshot["user_instructions"],
        snapshot["approved_constraints"],
        snapshot.get("shared_instruction", ""),
        allowance=snapshot["ai_allowance"],
        semantic_change_consent=snapshot["semantic_change_consent"],
    )
    if conflicts:
        return "", conflicts
    tags = ", ".join(tag["display_name"] for tag in snapshot["tags"]) or "none recorded"
    parts = [
        "Edit this travel photograph while preserving documentary authenticity.",
        "Use only the deterministic publication input derived from the immutable original; never use or modify the original as the generative editing input.",
        (f"Publication target: {snapshot['publication_profile']['image_format']}, "
         f"maximum long edge {snapshot['publication_profile']['max_long_edge']} px, "
         f"{snapshot['publication_profile']['color_space']}, quality "
         f"{snapshot['publication_profile']['quality']}, preserve aspect ratio, do not upscale, "
         "and strip private metadata."),
        "Prefer deterministic tonal, color, lens, perspective, crop, sharpening, and denoise corrections.",
        f"Primary subject: {snapshot['primary_subject'] or 'not specified'}.",
        f"Observed tags: {tags}.",
    ]
    if snapshot["preset"]["instructions"]:
        parts.append(f"Selected preset v{snapshot['preset']['version']}: {snapshot['preset']['instructions']}")
    if snapshot.get("rule_instructions", "").strip():
        parts.append(f"Suggested editing instructions: {snapshot['rule_instructions'].strip()}")
    if snapshot.get("rule_suggestions", {}).get("constraints", "").strip():
        parts.append(f"Rule-based constraints: {snapshot['rule_suggestions']['constraints'].strip()}")
    if snapshot["ai_suggestion"].strip():
        parts.append(f"Editable analysis suggestion: {snapshot['ai_suggestion'].strip()}")
    if snapshot["user_instructions"].strip():
        parts.append(f"Owner instructions: {snapshot['user_instructions'].strip()}")
    if snapshot["approved_constraints"].strip():
        parts.append(f"Approved constraints: {snapshot['approved_constraints'].strip()}")
    if snapshot.get("shared_instruction", "").strip():
        parts.append(f"Selection instruction: {snapshot['shared_instruction'].strip()}")
    parts.append(f"Application AI allowance: {snapshot['ai_allowance']} of 10.")
    if not snapshot["semantic_change_consent"]:
        parts.append("Do not introduce semantic changes or new scene content.")
    parts.append("Return a separate edited version; never alter the source file.")
    return "\n".join(parts), []


def create_compiled_prompt(db: sqlite3.Connection, photo_id: str, shared_instruction: str = "") -> dict[str, Any]:
    snapshot, photo, draft = _snapshot(db, photo_id, shared_instruction)
    text, conflicts = compile_text(snapshot)
    if conflicts:
        raise PromptConflict(conflicts)
    latest = db.execute("SELECT * FROM compiled_prompts WHERE photo_id=? ORDER BY version_number DESC LIMIT 1", (photo_id,)).fetchone()
    if (latest and not latest["user_modified"] and latest["compiled_text"] == text
            and json.loads(latest["input_snapshot_json"]) == snapshot
            and latest["photo_revision"] == photo["revision"] and latest["draft_revision"] == draft["revision"]
            and not draft["compiled_prompt_stale"]):
        return get_prompt(db, latest["id"])
    version = db.execute(
        "SELECT COALESCE(MAX(version_number), 0) + 1 FROM compiled_prompts WHERE photo_id=?", (photo_id,)
    ).fetchone()[0]
    prompt_id = str(uuid4())
    now = utc_now()
    db.execute(
        """INSERT INTO compiled_prompts(
               id, photo_id, version_number, source_hash, photo_revision, draft_revision,
               policy_version, compiler_version, publication_profile_id,
               publication_profile_snapshot_json, input_snapshot_json, compiled_text,
               user_modified, approved_for_job, generated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)""",
        (prompt_id, photo_id, version, photo["sha256"], photo["revision"], draft["revision"],
         POLICY_VERSION, COMPILER_VERSION, draft["publication_profile_id"],
         json.dumps(snapshot["publication_profile"], sort_keys=True),
         json.dumps(snapshot, sort_keys=True), text, now),
    )
    db.execute("UPDATE compiled_prompts SET approved_for_job=0,approved_at=NULL WHERE photo_id=? AND id<>?", (photo_id, prompt_id))
    db.execute("UPDATE review_drafts SET compiled_prompt_stale=0 WHERE photo_id=?", (photo_id,))
    return get_prompt(db, prompt_id)


def preview_with_form(db: sqlite3.Connection, photo_id: str, form: dict) -> dict[str, Any]:
    """Compile an ephemeral owner-editable form without changing catalog or prompt history."""
    snapshot, photo, _ = _snapshot(db, photo_id, allow_missing_draft=True)
    if photo["revision"] != form["expected_revision"]:
        raise ValueError("Photo changed; reload before previewing")
    preset_id = form.get("preset_id")
    preset = db.execute("SELECT id,name,version,structured_instructions FROM presets WHERE id=?", (preset_id,)).fetchone() if preset_id else None
    if preset_id and preset is None:
        raise ValueError("Unknown draft preset")
    profile = db.execute("SELECT * FROM publication_profiles WHERE id=? AND active=1", (form["publication_profile_id"],)).fetchone()
    if profile is None:
        raise ValueError("Select an active publication profile")
    snapshot["primary_subject"] = form["primary_subject"] or None
    snapshot["tags"] = [{"display_name": tag, "kind": kind, "source": "AI", "user_confirmed": 0}
                        for kind, field in (("CONTENT", "content_tags"), ("CONDITION", "condition_tags"))
                        for tag in form[field] if tag.strip()]
    snapshot["preset"] = {"id": preset_id, "name": preset["name"] if preset else None,
                          "version": preset["version"] if preset else None,
                          "instructions": preset["structured_instructions"] if preset else None}
    snapshot["publication_profile"] = dict(profile)
    for key in ("ai_allowance", "semantic_change_consent", "ai_suggestion_editable", "user_instructions", "approved_constraints"):
        snapshot["ai_suggestion" if key == "ai_suggestion_editable" else key] = form[key]
    rules = compose(snapshot["primary_subject"],
                    [tag["display_name"] for tag in snapshot["tags"] if tag["kind"] == "CONTENT"],
                    [tag["display_name"] for tag in snapshot["tags"] if tag["kind"] == "CONDITION"],
                    form.get("rule_selected_ids"), form.get("rule_suggestions_enabled", True),
                    form["semantic_change_consent"])
    snapshot["rule_suggestions"] = rules
    snapshot["rule_instructions_override"] = form.get("rule_instructions_override")
    snapshot["rule_instructions"] = (form["rule_instructions_override"] if form.get("rule_instructions_override") is not None
                                    else rules["instructions"]) if form.get("rule_suggestions_enabled", True) else ""
    value, conflicts = compile_text(snapshot)
    return {"proposed_text": value, "conflicts": conflicts, "profile_id": profile["id"], "unapproved": True,
            "rule_suggestions": rules, "rule_instructions": snapshot["rule_instructions"]}


def get_prompt(db: sqlite3.Connection, prompt_id: str) -> dict[str, Any]:
    row = db.execute("SELECT * FROM compiled_prompts WHERE id=?", (prompt_id,)).fetchone()
    if row is None:
        raise KeyError(prompt_id)
    item = dict(row)
    item["input_snapshot"] = json.loads(item.pop("input_snapshot_json"))
    item["publication_profile_snapshot"] = json.loads(item.pop("publication_profile_snapshot_json"))
    if item["approved_for_job"]:
        active = load_rules()
        saved = item["input_snapshot"].get("rule_suggestions", {})
        if saved.get("config_sha256") != active["sha256"] or saved.get("ontology_sha256") != active["ontology_sha256"]:
            item["approved_for_job"] = 0
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
               draft_revision, policy_version, compiler_version, publication_profile_id,
               publication_profile_snapshot_json, input_snapshot_json,
               compiled_text, user_modified, approved_for_job, generated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?)""",
        (new_id, prior["photo_id"], version, prior["id"], prior["source_hash"],
         prior["photo_revision"], prior["draft_revision"], prior["policy_version"],
         prior["compiler_version"], prior["publication_profile_id"],
         prior["publication_profile_snapshot_json"], prior["input_snapshot_json"],
         compiled_text.strip(), utc_now()),
    )
    db.execute("UPDATE compiled_prompts SET approved_for_job=0,approved_at=NULL WHERE photo_id=? AND id<>?", (prior["photo_id"], new_id))
    return get_prompt(db, new_id)


def required_prompt_lines(snapshot: dict[str, Any]) -> list[str]:
    baseline, conflicts = compile_text(snapshot)
    if conflicts:
        raise PromptConflict(conflicts)
    required = [line for line in baseline.splitlines() if line.startswith((
        "Use only the deterministic publication input", "Publication target:",
        "Owner instructions:", "Approved constraints:",
        "Rule-based constraints:",
        "Application AI allowance:", "Do not introduce semantic changes",
        "Selection instruction:", "Return a separate edited version"))]
    required.extend(snapshot.get("rule_suggestions", {}).get("constraints", "").splitlines())
    return list(dict.fromkeys(required))


def validate_prompt_text(snapshot: dict[str, Any], candidate: str) -> None:
    required = required_prompt_lines(snapshot)
    conflicts = []
    conflicts += detect_conflicts(candidate, snapshot["approved_constraints"],
                                  allowance=snapshot["ai_allowance"],
                                  semantic_change_consent=snapshot["semantic_change_consent"])
    if any(line not in candidate for line in required):
        conflicts.append("The edited prompt removed a required profile, instruction, allowance, or constraint")
    if conflicts:
        raise PromptConflict(list(dict.fromkeys(conflicts)))


def approve_prompt(db: sqlite3.Connection, prompt_id: str) -> dict[str, Any]:
    prompt = db.execute("SELECT * FROM compiled_prompts WHERE id=?", (prompt_id,)).fetchone()
    if prompt is None:
        raise KeyError(prompt_id)
    current = db.execute(
        """SELECT p.sha256, p.revision AS photo_revision, d.revision AS draft_revision,
                  d.compiled_prompt_stale, d.publication_profile_id
           FROM photos p JOIN review_drafts d ON d.photo_id=p.id WHERE p.id=?""",
        (prompt["photo_id"],),
    ).fetchone()
    if (current is None or current["sha256"] != prompt["source_hash"]
            or current["photo_revision"] != prompt["photo_revision"]
            or current["draft_revision"] != prompt["draft_revision"]
            or current["publication_profile_id"] != prompt["publication_profile_id"]
            or current["compiled_prompt_stale"]):
        raise PromptConflict(["The photo or editing draft changed; compile a new prompt before approval"])
    saved_snapshot = json.loads(prompt["input_snapshot_json"])
    active_rules = load_rules()
    if (saved_snapshot.get("rule_suggestions", {}).get("config_sha256") != active_rules["sha256"]
            or saved_snapshot.get("rule_suggestions", {}).get("ontology_sha256") != active_rules["ontology_sha256"]):
        raise PromptConflict(["Editing rules or ontology changed; compile a new prompt before approval"])
    validate_prompt_text(saved_snapshot, prompt["compiled_text"])
    db.execute("UPDATE compiled_prompts SET approved_for_job=0, approved_at=NULL WHERE photo_id=?", (prompt["photo_id"],))
    db.execute(
        "UPDATE compiled_prompts SET approved_for_job=1, approved_at=? WHERE id=?", (utc_now(), prompt_id)
    )
    return get_prompt(db, prompt_id)


def prompt_history(db: sqlite3.Connection, photo_id: str) -> list[dict[str, Any]]:
    return [get_prompt(db, row["id"]) for row in db.execute(
        "SELECT id FROM compiled_prompts WHERE photo_id=? ORDER BY version_number DESC", (photo_id,)
    )]
