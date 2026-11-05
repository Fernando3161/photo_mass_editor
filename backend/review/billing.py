"""Import owner-supplied itemized billing data without changing immutable request receipts."""

from __future__ import annotations

import csv
from pathlib import Path
from uuid import uuid4

from backend.catalog.database import connect
from backend.catalog.ingestion import utc_now
from .costs import billed_amount


TABLES = {"editing": "edit_jobs", "analysis": "analysis_runs", "refinement": "prompt_refinements"}


def import_billing(data_dir: Path, csv_path: Path) -> dict:
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)
    with csv_path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"operation", "receipt_id", "provider_request_id", "billed_usd"}.issubset(reader.fieldnames):
            raise ValueError("Billing CSV needs operation,receipt_id,provider_request_id,billed_usd columns")
        entries = list(reader)
    if not entries:
        raise ValueError("Billing CSV contains no rows")
    db = connect(data_dir)
    try:
        db.execute("BEGIN IMMEDIATE")
        seen = set()
        for item in entries:
            operation, receipt = item["operation"].strip(), item["receipt_id"].strip()
            if operation not in TABLES or not receipt or (operation, receipt) in seen:
                raise ValueError("Unknown or repeated billing receipt")
            seen.add((operation, receipt))
            row = db.execute(f"SELECT request_id FROM {TABLES[operation]} WHERE id=?", (receipt,)).fetchone()
            if row is None or not row["request_id"] or row["request_id"] != item["provider_request_id"].strip():
                raise ValueError("Billing request identity does not match the private receipt")
            if db.execute("SELECT 1 FROM billing_reconciliations WHERE operation=? AND receipt_id=?",
                          (operation, receipt)).fetchone():
                raise ValueError("Billing receipt has already been reconciled")
            db.execute("""INSERT INTO billing_reconciliations
                (id,operation,receipt_id,provider_request_id,billed_usd,source_label,imported_at)
                VALUES (?,?,?,?,?,?,?)""", (str(uuid4()), operation, receipt, row["request_id"],
                billed_amount(item["billed_usd"]), csv_path.name, utc_now()))
        db.commit()
        return {"reconciled": len(entries), "source_label": csv_path.name}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
