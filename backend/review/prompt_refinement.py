"""Opt-in text-only prompt proposals. No image path or bytes cross this boundary."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Protocol
from urllib.request import Request, urlopen
from uuid import uuid4

from backend.catalog.database import connect
from backend.catalog.ingestion import utc_now
from .prompts import PromptConflict, get_prompt, required_prompt_lines, revise_prompt, validate_prompt_text


TEMPLATE_VERSION = "v2-refine-text-v1"
MODEL = "gpt-6-luna"
MAX_OUTPUT_TOKENS = 700
# Standard API rates observed 2026-11-04. Planning only; provider billing can differ.
INPUT_PER_MILLION = Decimal("0.10")
OUTPUT_PER_MILLION = Decimal("0.50")
INSTRUCTIONS = (
    "Rewrite the supplied deterministic image-edit instruction into a concise, precise instruction. "
    "Use only the supplied text. Do not invent scene facts or add, remove, or replace scene content "
    "unless the owner explicitly requested it with the recorded consent. Preserve every line beginning "
    "Publication target:, Owner instructions:, Approved constraints:, Selection instruction:, "
    "Application AI allowance:, and Do not introduce semantic changes exactly. "
    "Keep the source preservation and separate-version requirements. Return only the complete proposed prompt."
)


@dataclass(frozen=True)
class RefinementResult:
    text: str
    raw_response: dict[str, Any]
    usage: dict[str, Any] | None = None
    actual_cost_usd: Decimal | None = None


class RefinementProvider(Protocol):
    name: str
    model: str
    template_version: str

    def refine(self, baseline: str) -> RefinementResult: ...


class OpenAITextRefiner:
    name = "openai"
    model = MODEL
    template_version = TEMPLATE_VERSION

    def refine(self, baseline: str) -> RefinementResult:
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not configured on the server")
        body = {"model": self.model, "instructions": INSTRUCTIONS, "input": baseline,
                "max_output_tokens": MAX_OUTPUT_TOKENS, "reasoning": {"effort": "none"}, "store": False}
        request = Request("https://api.openai.com/v1/responses", json.dumps(body).encode(),
                          {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=90) as response:
            raw = json.load(response)
        if raw.get("status") != "completed":
            raise RuntimeError("Text provider did not complete the refinement")
        texts = [part.get("text", "") for item in raw.get("output", [])
                 for part in item.get("content", []) if part.get("type") == "output_text"]
        text = "\n".join(value for value in texts if value).strip()
        if not text:
            raise RuntimeError("Text provider returned no proposal")
        return RefinementResult(text, raw, raw.get("usage"))


def _current(db: sqlite3.Connection, prompt_id: str) -> sqlite3.Row:
    row = db.execute("SELECT * FROM compiled_prompts WHERE id=?", (prompt_id,)).fetchone()
    if row is None:
        raise KeyError(prompt_id)
    current = db.execute(
        "SELECT p.sha256, p.revision photo_revision, d.revision draft_revision, "
        "d.publication_profile_id, d.compiled_prompt_stale "
        "FROM photos p JOIN review_drafts d ON d.photo_id=p.id WHERE p.id=?", (row["photo_id"],)
    ).fetchone()
    latest = db.execute("SELECT id FROM compiled_prompts WHERE photo_id=? ORDER BY version_number DESC LIMIT 1",
                        (row["photo_id"],)).fetchone()
    if (current is None or latest["id"] != row["id"] or current["sha256"] != row["source_hash"]
            or current["photo_revision"] != row["photo_revision"]
            or current["draft_revision"] != row["draft_revision"]
            or current["publication_profile_id"] != row["publication_profile_id"]
            or current["compiled_prompt_stale"]):
        raise PromptConflict(["The prompt is no longer current; compile a new baseline"])
    validate_prompt_text(json.loads(row["input_snapshot_json"]), row["compiled_text"])
    return row


def _request(row: sqlite3.Row, model: str = MODEL, template_version: str = TEMPLATE_VERSION) -> dict[str, Any]:
    # The cloud request is text-only. Private GPS, paths, source hash and original bytes stay local.
    return {"instructions": INSTRUCTIONS, "baseline": row["compiled_text"],
            "model": model, "template_version": template_version, "max_output_tokens": MAX_OUTPUT_TOKENS}


def _planning_cost(request: dict[str, Any]) -> str:
    # UTF-8 byte count bounds text token count conservatively, plus protocol overhead.
    input_bound = len((request["instructions"] + request["baseline"]).encode()) + 256
    amount = (Decimal(input_bound) * INPUT_PER_MILLION +
              Decimal(MAX_OUTPUT_TOKENS) * OUTPUT_PER_MILLION) / Decimal(1_000_000)
    return str(amount.quantize(Decimal("0.000001")))


def estimate(data_dir: Path, prompt_id: str, provider: RefinementProvider | None = None) -> dict[str, Any]:
    selected = provider or OpenAITextRefiner()
    db = connect(data_dir)
    try:
        row = _current(db, prompt_id)
        request = _request(row, selected.model, selected.template_version)
        return {"prompt_id": prompt_id, "model": selected.model, "provider": selected.name,
                "template_version": selected.template_version, "estimated_cost_usd": _planning_cost(request),
                "note": "Conservative text-token planning estimate, not a provider billing cap. Text only; no image upload."}
    finally:
        db.close()


def _public(row: sqlite3.Row) -> dict[str, Any]:
    item = {key: row[key] for key in ("id", "photo_id", "base_prompt_id", "provider", "model",
            "template_version", "proposed_text", "status", "estimated_cost_usd", "actual_cost_usd",
            "error", "created_at", "completed_at")}
    if row["status"] == "SUCCEEDED":
        item["adoption_text"], restored = adoption_draft(
            json.loads(row["input_snapshot_json"]), row["proposed_text"])
        item["restored_requirements"] = len(restored)
    else:
        item["adoption_text"] = None
        item["restored_requirements"] = 0
    return item


def adoption_draft(snapshot: dict[str, Any], proposed_text: str) -> tuple[str, list[str]]:
    missing = [line for line in required_prompt_lines(snapshot) if line not in proposed_text]
    candidate = proposed_text.strip()
    if missing:
        candidate += "\n" + "\n".join(missing)
    return candidate, missing


def history(data_dir: Path, photo_id: str) -> list[dict[str, Any]]:
    db = connect(data_dir)
    try:
        if db.execute("SELECT 1 FROM photos WHERE id=?", (photo_id,)).fetchone() is None:
            raise KeyError(photo_id)
        return [_public(row) for row in db.execute(
            "SELECT * FROM prompt_refinements WHERE photo_id=? ORDER BY created_at DESC", (photo_id,))]
    finally:
        db.close()


def run(data_dir: Path, prompt_id: str, provider: RefinementProvider, *, authorized: bool,
        budget_usd: Decimal | None = None) -> dict[str, Any]:
    if not authorized:
        raise PermissionError("Authorize this paid text refinement run")
    db = connect(data_dir)
    try:
        row = _current(db, prompt_id)
        request = _request(row, provider.model, provider.template_version)
        planned = Decimal(_planning_cost(request))
        if budget_usd is None or budget_usd < planned:
            raise ValueError("The current-run planning budget must cover the estimate")
        identity = str(uuid4())
        db.execute("""INSERT INTO prompt_refinements
            (id,photo_id,base_prompt_id,source_hash,publication_profile_id,input_snapshot_json,
             provider,model,template_version,settings_json,request_json,status,estimated_cost_usd,created_at)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,'RUNNING',?,?)""",
            (identity, row["photo_id"], prompt_id, row["source_hash"], row["publication_profile_id"],
             row["input_snapshot_json"], provider.name, provider.model, provider.template_version,
             json.dumps({"max_output_tokens": MAX_OUTPUT_TOKENS}), json.dumps(request), float(planned), utc_now()))
        db.commit()
        try:
            result = provider.refine(request["baseline"])
            if not result.text.strip() or len(result.text) > 10000:
                raise ValueError("Provider proposal is empty or too long")
            db.execute("""UPDATE prompt_refinements SET response_json=?, proposed_text=?, status='SUCCEEDED',
                usage_json=?, actual_cost_usd=?, completed_at=? WHERE id=?""",
                (json.dumps(result.raw_response), result.text.strip(), json.dumps(result.usage),
                 float(result.actual_cost_usd) if result.actual_cost_usd is not None else None, utc_now(), identity))
        except Exception as exc:
            db.execute("UPDATE prompt_refinements SET status='FAILED',error=?,completed_at=? WHERE id=?",
                       (str(exc), utc_now(), identity))
            db.commit()
            raise
        db.commit()
        return _public(db.execute("SELECT * FROM prompt_refinements WHERE id=?", (identity,)).fetchone())
    finally:
        db.close()


def adopt(data_dir: Path, refinement_id: str, compiled_text: str | None = None) -> dict[str, Any]:
    db = connect(data_dir)
    try:
        db.execute("BEGIN IMMEDIATE")
        proposal = db.execute("SELECT * FROM prompt_refinements WHERE id=?", (refinement_id,)).fetchone()
        if proposal is None:
            raise KeyError(refinement_id)
        if proposal["status"] != "SUCCEEDED":
            raise PromptConflict(["Only a completed proposal can become a prompt version"])
        base = _current(db, proposal["base_prompt_id"])
        if base["source_hash"] != proposal["source_hash"] or base["publication_profile_id"] != proposal["publication_profile_id"]:
            raise PromptConflict(["The source or publication profile changed"])
        snapshot = json.loads(base["input_snapshot_json"])
        candidate = compiled_text if compiled_text is not None else adoption_draft(snapshot, proposal["proposed_text"])[0]
        if not candidate.strip() or len(candidate) > 10000:
            raise PromptConflict(["The adoption draft is empty or too long"])
        validate_prompt_text(snapshot, candidate)
        version = revise_prompt(db, base["id"], candidate)
        db.execute("UPDATE compiled_prompts SET refinement_id=? WHERE id=?", (refinement_id, version["id"]))
        db.commit()
        return get_prompt(db, version["id"])
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
