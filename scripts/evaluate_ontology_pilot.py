"""Read-only local pilot comparison; output stays in ignored private evidence."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.review.catalog_prefill import _hash, _proposal, match_city  # noqa: E402
from backend.review.local_model import ModelManager  # noqa: E402
from backend.review.ontology import load_ontology  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=ROOT / "data/catalog")
    parser.add_argument("--output", type=Path, default=ROOT / "data/evidence/ontology-pilot.json")
    parser.add_argument("--reuse-scores", action="store_true", help="Reapply scoring to previously saved local model similarities")
    args = parser.parse_args()
    database = args.catalog / "catalog.sqlite"
    if not database.is_file():
        parser.error(f"Missing pilot catalog: {database}")
    ontology = load_ontology()
    prior = json.loads(args.output.read_text(encoding="utf-8")) if args.reuse_scores and args.output.is_file() else None
    if args.reuse_scores and (prior is None or prior.get("ontology_sha256") != ontology["sha256"]):
        parser.error("No matching saved ontology scores; run local inference first")
    previous_items = {item["photo_id"]: item for item in prior["items"]} if prior else {}
    manager = ModelManager(ROOT) if not args.reuse_scores else None
    if manager:
        manager.ensure(offline=True)
    db = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        photos = db.execute("SELECT * FROM photos ORDER BY imported_at, id").fetchall()
        cities = db.execute("SELECT * FROM visited_cities ORDER BY id").fetchall()
        if not photos:
            parser.error("Pilot catalog has no photos")
        items = []
        for photo in photos:
            thumbnail = args.catalog / photo["thumbnail_path"]
            if not thumbnail.is_file() or _hash(thumbnail) != photo["thumbnail_sha256"]:
                raise RuntimeError(f"Missing or changed thumbnail for photo {photo['id']}")
            old = db.execute("SELECT proposed_json FROM catalog_suggestions WHERE photo_id=? ORDER BY created_at DESC LIMIT 1", (photo["id"],)).fetchone()
            start = time.perf_counter()
            if args.reuse_scores:
                previous = previous_items.get(photo["id"])
                if not previous or "ranking" not in previous:
                    parser.error(f"Missing saved similarities for photo {photo['id']}")
                with Image.open(thumbnail) as opened:
                    sample = ImageOps.pad(opened.convert("RGB"), (224, 224), color=(128, 128, 128))
                    means = ImageStat.Stat(sample).mean
                result = {"ranking": previous["ranking"], "measurements": previous.get("measurements") or
                          {"mean_luminance": round((.2126 * means[0] + .7152 * means[1] + .0722 * means[2]) / 255, 3)}}
                elapsed = previous["inference_seconds"]
            else:
                result = manager.classify(thumbnail, offline=True)
                elapsed = round(time.perf_counter() - start, 3)
            proposal, evidence = _proposal(photo, result, match_city(photo, cities), ontology)
            items.append({"photo_id": photo["id"], "old": json.loads(old[0]) if old else None,
                          "new": proposal, "local_recipe": evidence["local_recipe"],
                          "subject_margin": evidence["subject_margin"], "ranking": result["ranking"],
                          "measurements": result["measurements"], "inference_seconds": elapsed})
        def summary(key):
            proposals = [item[key] for item in items if item[key]]
            return {"subject_coverage": sum(bool(item["primary_subject"]) for item in proposals),
                    "content_coverage": sum(bool(item["content_tags"]) for item in proposals),
                    "condition_coverage": sum(bool(item["condition_tags"]) for item in proposals),
                    "preset_counts": dict(Counter(item["preset_id"] for item in proposals)),
                    "mean_content_tags": round(sum(len(item["content_tags"]) for item in proposals) / len(proposals), 2) if proposals else 0}
        report = {"photo_count": len(items), "ontology_sha256": ontology["sha256"], "old": summary("old"),
                  "new": summary("new"), "mean_inference_seconds": round(sum(item["inference_seconds"] for item in items) / len(items), 3),
                  "owner_accuracy_review": "NOT_RUN; inspect each old/new proposal against the photograph",
                  "items": items}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        cell_w, cell_h, columns = 280, 270, 4
        sheet = Image.new("RGB", (cell_w * columns, cell_h * ((len(items) + columns - 1) // columns)), "white")
        draw = ImageDraw.Draw(sheet)
        for index, (photo, item) in enumerate(zip(photos, items)):
            x, y = (index % columns) * cell_w, (index // columns) * cell_h
            with Image.open(args.catalog / photo["thumbnail_path"]) as opened:
                sample = ImageOps.contain(opened.convert("RGB"), (cell_w - 16, 185))
                sheet.paste(sample, (x + (cell_w - sample.width) // 2, y + 4))
            draw.text((x + 6, y + 190), f"{index + 1}. {photo['original_filename'][:31]}", fill="black")
            draw.text((x + 6, y + 207), f"Old: {(item['old'] or {}).get('primary_subject') or '-'}", fill="black")
            draw.text((x + 6, y + 224), f"New: {item['new']['primary_subject'] or '-'} | {item['new']['preset_id']}", fill="black")
            draw.text((x + 6, y + 241), ", ".join(item["new"]["content_tags"])[:42], fill="black")
        contact = args.output.with_suffix(".png")
        sheet.save(contact)
        print(json.dumps({key: value for key, value in report.items() if key != "items"}, indent=2))
        print(f"Private per-photo evidence: {args.output}")
        print(f"Private visual review sheet: {contact}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
