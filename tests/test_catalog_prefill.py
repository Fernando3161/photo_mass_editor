"""Phase 05 tests use synthetic thumbnails and a local fake recognizer only."""

import hashlib
import io
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.catalog.database import connect
from backend.catalog.ingestion import import_photo, sha256
from backend.review.app import create_app
from backend.review.catalog_prefill import match_city
from backend.review.local_model import MANIFEST, ModelManager, ModelUnavailable


class FakeRecognizer:
    def __init__(self):
        self.calls = []

    def status(self):
        return {"state": "ready", "file": "", "downloaded": 0, "total": 0, "error": "", "cached": True}

    def classify(self, path, *, offline=False):
        self.calls.append((path, offline))
        return {"ranking": [
            {"label": "an opera house", "similarity": 31.0},
            {"label": "a parliament building", "similarity": 22.0},
            {"label": "a night photograph", "similarity": 21.0},
            {"label": "a daytime photograph", "similarity": 20.0},
        ], "measurements": {"mean_luminance": 0.5}}


class CatalogPrefillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / "catalog"
        self.source = self.root / "source.jpg"
        Image.new("RGB", (80, 60), "#656565").save(self.source)
        self.original_hash = sha256(self.source)
        self.photo_id = import_photo(self.data, self.source)["id"]
        self.fake = FakeRecognizer()
        self.client = TestClient(create_app(self.data, local_recognizer=self.fake))

    def city(self, name="Budapest", lat=47.507, lon=19.045, radius=25):
        response = self.client.post("/api/catalog/cities", json={"city": name, "country": "Hungary", "latitude": lat, "longitude": lon, "radius_km": radius})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def run_prefill(self):
        return self.client.post("/api/catalog/suggestions/run", json={"photo_ids": [self.photo_id], "authorized": True})

    def test_new_local_candidates_are_reviewable_search_terms_only(self):
        self.fake.classify = lambda path, offline=False: {"ranking": [
            {"label": "a waterfall", "similarity": 31.0},
            {"label": "a river", "similarity": 25.0},
            {"label": "a hazy photograph", "similarity": 22.0},
            {"label": "a clear photograph", "similarity": 18.0},
        ], "measurements": {}}
        suggestion = self.run_prefill()
        self.assertEqual(suggestion.status_code, 200, suggestion.text)
        proposed = suggestion.json()["results"][0]["proposed"]
        self.assertEqual(proposed["primary_subject"], "waterfall")
        self.assertIn("hazy", proposed["condition_tags"])
        listed = self.client.get("/api/photos").json()[0]
        self.assertIn("waterfall", listed["suggested_search_terms"])
        self.assertIsNone(listed["primary_subject"])
        self.assertEqual(listed["tags"], [])

    def test_city_match_missing_invalid_radius_and_ambiguity(self):
        city = {"city": "Budapest", "country": "Hungary", "private_lat": 47.507, "private_lon": 19.045, "radius_km": 25}
        self.assertEqual(match_city({"private_lat": None, "private_lon": None}, [city])["status"], "NO_GPS")
        self.assertEqual(match_city({"private_lat": 0, "private_lon": 0}, [city])["status"], "UNMATCHED")
        matched = match_city({"private_lat": 47.51, "private_lon": 19.05}, [city])
        self.assertEqual((matched["status"], matched["city"]), ("MATCH", "Budapest"))
        rival = city | {"city": "Other", "private_lat": 47.508}
        self.assertEqual(match_city({"private_lat": 47.507, "private_lon": 19.045}, [city, rival])["status"], "AMBIGUOUS")

    def test_suggestion_permission_cache_accept_undo_and_provenance(self):
        denied = self.client.post("/api/catalog/suggestions/run", json={"photo_ids": [self.photo_id]})
        self.assertEqual(denied.status_code, 403)
        first = self.run_prefill()
        self.assertEqual(first.status_code, 200, first.text)
        suggestion = first.json()["results"][0]
        self.assertEqual(suggestion["proposed"]["primary_subject"], "opera house")
        self.assertEqual(suggestion["evidence"]["location"]["status"], "NO_GPS")
        self.assertEqual(len(self.fake.calls), 1)
        self.assertEqual(self.fake.calls[0][0].suffix, ".png")
        cached = self.run_prefill().json()["results"][0]
        self.assertTrue(cached["cached"])
        self.assertEqual(len(self.fake.calls), 1)
        accepted = self.client.post(f"/api/catalog/suggestions/{suggestion['id']}/decide", json={"fields": ["primary_subject", "content_tags", "preset_id"], "expected_revision": 0})
        self.assertEqual(accepted.status_code, 200, accepted.text)
        item = accepted.json()["photo"]
        self.assertEqual(item["primary_subject"], "opera house")
        self.assertEqual(item["draft"]["preset_id"], "architecture-clarity")
        self.assertEqual(item["draft"]["ai_allowance"], 0)
        self.assertFalse(item["draft"]["semantic_change_consent"])
        self.assertTrue(item["draft"]["compiled_prompt_stale"])
        self.assertEqual(item["draft"]["publication_profile_id"], "website-standard-v1")
        self.assertEqual(self.client.post(f"/api/catalog/suggestions/{suggestion['id']}/decide", json={"fields": ["city"], "expected_revision": 0}).status_code, 409)
        undone = self.client.post(f"/api/catalog/suggestions/{suggestion['id']}/undo")
        self.assertEqual(undone.status_code, 200, undone.text)
        self.assertIsNone(undone.json()["photo"]["primary_subject"])
        self.assertEqual(sha256(self.source), self.original_hash)
        db = connect(self.data)
        try:
            row = db.execute("SELECT source_sha256, model_id, model_revision, settings_json, evidence_json FROM catalog_suggestions WHERE id=?", (suggestion["id"],)).fetchone()
            self.assertEqual(row["source_sha256"], self.original_hash)
            self.assertTrue(all(row[key] for key in ("model_id", "model_revision", "settings_json", "evidence_json")))
        finally:
            db.close()

    def test_accepted_metadata_revokes_approved_prompt_and_source_hash_mismatch_blocks_recognition(self):
        saved = self.client.patch(f"/api/photos/{self.photo_id}", json={"expected_revision": 0, "user_instructions": "Preserve natural texture."})
        self.assertEqual(saved.status_code, 200, saved.text)
        prompt = self.client.post(f"/api/photos/{self.photo_id}/prompts/compile")
        self.assertEqual(prompt.status_code, 200, prompt.text)
        approved = self.client.post(f"/api/prompts/{prompt.json()['id']}/approve")
        self.assertEqual(approved.status_code, 200, approved.text)
        suggestion = self.run_prefill().json()["results"][0]
        accepted = self.client.post(f"/api/catalog/suggestions/{suggestion['id']}/decide", json={"fields": ["content_tags"], "expected_revision": 1})
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()["photo"]["draft"]["user_instructions"], "Preserve natural texture.")
        self.assertTrue(accepted.json()["photo"]["draft"]["compiled_prompt_stale"])
        self.assertFalse(accepted.json()["photo"]["prompt_history"][0]["approved_for_job"])
        db = connect(self.data)
        try:
            db.execute("UPDATE photos SET sha256=? WHERE id=?", ("0" * 64, self.photo_id))
            db.commit()
        finally:
            db.close()
        blocked = self.client.post("/api/catalog/suggestions/run", json={"photo_ids": [self.photo_id], "authorized": True})
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(sha256(self.source), self.original_hash)

    def test_owner_fields_stay_and_city_revisions_invalidate_suggestions(self):
        city = self.city()
        db = connect(self.data)
        try:
            db.execute("UPDATE photos SET private_lat=47.51, private_lon=19.05 WHERE id=?", (self.photo_id,))
            db.commit()
        finally:
            db.close()
        suggestion = self.run_prefill().json()["results"][0]
        self.assertEqual(suggestion["proposed"]["city"], "Budapest")
        self.assertNotIn("private_lat", self.client.get("/api/catalog/cities").text)
        self.assertNotIn("47.51", self.client.get(f"/api/photos/{self.photo_id}").text)
        self.client.patch(f"/api/photos/{self.photo_id}", json={"expected_revision": 0, "primary_subject": "Owner's Opera", "city": "Vienna", "country": "Austria"})
        changed = self.client.post(f"/api/catalog/suggestions/{suggestion['id']}/decide", json={"fields": ["city", "primary_subject"], "expected_revision": 0})
        self.assertEqual(changed.status_code, 409)
        current = self.client.get(f"/api/photos/{self.photo_id}").json()
        self.assertEqual((current["city"], current["primary_subject"]), ("Vienna", "Owner's Opera"))
        # A visited-city edit makes an old GPS match stale even at a current photo revision.
        second = self.run_prefill().json()["results"][0]
        updated = self.client.patch(f"/api/catalog/cities/{city['id']}", json={"city": "Budapest", "country": "Hungary", "latitude": 47.507, "longitude": 19.045, "radius_km": 30})
        self.assertEqual(updated.status_code, 200)
        stale = self.client.post(f"/api/catalog/suggestions/{second['id']}/decide", json={"fields": ["content_tags"], "expected_revision": current["revision"]})
        self.assertEqual(stale.status_code, 409)

    def test_acceptance_appends_tags_without_overwriting_owner_fields(self):
        saved = self.client.patch(f"/api/photos/{self.photo_id}", json={
            "expected_revision": 0, "primary_subject": "Owner label", "content_tags": ["facade"],
            "editorial_description": "Owner description", "city": "Vienna", "country": "Austria", "preset_id": "portrait-gentle",
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        suggestion = self.run_prefill().json()["results"][0]
        accepted = self.client.post(f"/api/catalog/suggestions/{suggestion['id']}/decide", json={
            "fields": ["primary_subject", "content_tags", "editorial_description", "city", "country", "preset_id"],
            "expected_revision": 1,
        })
        self.assertEqual(accepted.status_code, 200, accepted.text)
        photo = accepted.json()["photo"]
        self.assertEqual(photo["primary_subject"], "Owner label")
        self.assertEqual(photo["editorial_description"], "Owner description")
        self.assertEqual((photo["city"], photo["country"]), ("Vienna", "Austria"))
        self.assertEqual(photo["draft"]["preset_id"], "portrait-gentle")
        self.assertEqual({tag["display_name"] for tag in photo["tags"]}, {"facade", "opera house"})

    def test_accepting_subject_does_not_promote_unrelated_ai_tag(self):
        db = connect(self.data)
        try:
            db.execute("INSERT INTO tags(id,slug,display_name,kind) VALUES ('ai-tag','possible-stone','possible stone','CONTENT')")
            db.execute("INSERT INTO photo_tags(photo_id,tag_id,source,user_confirmed,confidence) VALUES (?,?,'AI',0,0.4)", (self.photo_id, "ai-tag"))
            db.commit()
        finally:
            db.close()
        suggestion = self.run_prefill().json()["results"][0]
        accepted = self.client.post(f"/api/catalog/suggestions/{suggestion['id']}/decide", json={"fields": ["primary_subject"], "expected_revision": 0})
        self.assertEqual(accepted.status_code, 200, accepted.text)
        db = connect(self.data)
        try:
            tag = db.execute("SELECT source,user_confirmed,confidence FROM photo_tags WHERE photo_id=? AND tag_id='ai-tag'", (self.photo_id,)).fetchone()
            self.assertEqual(tuple(tag), ("AI", 0, 0.4))
        finally:
            db.close()

    def test_bulk_location_preview_apply_undo_and_stale_preview(self):
        city = self.city()
        another = self.root / "second.jpg"
        Image.new("RGB", (80, 60), "#999999").save(another)
        second_id = import_photo(self.data, another)["id"]
        ids = [self.photo_id, second_id]
        preview = self.client.post("/api/catalog/location/preview", json={"photo_ids": ids, "city_id": city["id"]}).json()
        self.assertEqual(sum(item["eligible"] for item in preview["items"]), 2)
        revisions = {item["photo_id"]: item["revision"] for item in preview["items"]}
        denied = self.client.post("/api/catalog/location/apply", json={"photo_ids": ids, "city_id": city["id"], "expected_revisions": revisions})
        self.assertEqual(denied.status_code, 403)
        applied = self.client.post("/api/catalog/location/apply", json={"photo_ids": ids, "city_id": city["id"], "expected_revisions": revisions, "authorized": True})
        self.assertEqual(applied.status_code, 200, applied.text)
        self.assertEqual(applied.json()["applied_count"], 2)
        self.assertEqual(self.client.get(f"/api/photos/{self.photo_id}").json()["city"], "Budapest")
        undone = self.client.post(f"/api/catalog/location/batches/{applied.json()['id']}/undo")
        self.assertEqual(undone.status_code, 200, undone.text)
        self.assertEqual(self.client.get(f"/api/photos/{second_id}").json()["city"], None)
        stale = self.client.post("/api/catalog/location/apply", json={"photo_ids": ids, "city_id": city["id"], "expected_revisions": revisions, "authorized": True})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(sha256(self.source), self.original_hash)

    def test_model_cache_offline_and_checksum(self):
        manager = ModelManager(self.root)
        with self.assertRaises(ModelUnavailable):
            manager.ensure(offline=True)
        content = b"local synthetic model bytes"
        digest = hashlib.sha256(content).hexdigest()
        response = io.BytesIO(content)
        response.headers = {"Content-Length": str(len(content))}
        with patch.dict(MANIFEST, {"files": {"dummy.bin": digest}}), patch("backend.review.local_model.urlopen", return_value=response):
            manager.ensure()
            self.assertTrue(manager.cached())
            (manager.cache / "dummy.bin").write_bytes(b"corrupt")
            with self.assertRaises(ModelUnavailable):
                manager.ensure(offline=True)

    def test_phase_four_catalog_migrates_to_eight_without_losing_rows(self):
        folder = self.root / "legacy"
        folder.mkdir()
        database = folder / "catalog.sqlite"
        scripts = sorted((Path(__file__).resolve().parents[1] / "backend/catalog/migrations").glob("*.sql"))[:6]
        db = sqlite3.connect(database)
        try:
            for script in scripts:
                db.executescript(script.read_text(encoding="utf-8"))
            db.execute("INSERT INTO subjects(id,slug,display_name) VALUES ('legacy','legacy','Legacy subject')")
            db.commit()
        finally:
            db.close()
        db = connect(folder)
        try:
            self.assertEqual(db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 14)
            self.assertEqual(db.execute("SELECT display_name FROM subjects WHERE id='legacy'").fetchone()[0], "Legacy subject")
            self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE name='exports'").fetchone())
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            db.close()

    def test_audit_script_backs_up_and_compares_original_hashes(self):
        evidence = self.root / "evidence"
        script = Path(__file__).resolve().parents[1] / "scripts/phase05_audit.py"
        common = [sys.executable, str(script), "--data-dir", str(self.data), "--evidence-dir", str(evidence)]
        before = subprocess.run(common + ["--stage", "before"], capture_output=True, text=True)
        self.assertEqual(before.returncode, 0, before.stderr)
        self.assertEqual(len(list(evidence.glob("catalog-before-phase05-*.sqlite"))), 1)
        after = subprocess.run(common + ["--stage", "after"], capture_output=True, text=True)
        self.assertEqual(after.returncode, 0, after.stderr)
        self.assertEqual(sha256(self.source), self.original_hash)


if __name__ == "__main__":
    unittest.main()
