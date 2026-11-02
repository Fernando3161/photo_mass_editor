"""Local correction coverage uses synthetic files and never calls a provider."""

from io import BytesIO
from pathlib import Path
import tempfile
import time
import unittest

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from backend.catalog.database import connect
from backend.catalog.ingestion import import_photo, sha256
from backend.review.app import create_app
from backend.review.export import audit_artifacts, preview_export
from backend.review.local_corrections import (
    LocalCorrectionError, apply_recipe, enqueue, master_media, preview, recommend, run_job,
    validate_settings,
)


class LocalCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "catalog"
        self.source = self.root / "source.png"
        x = np.linspace(25, 210, 1800, dtype=np.uint8)
        gradient = np.broadcast_to(x, (1200, 1800)).copy()
        pixels = np.stack([gradient, gradient, gradient], axis=2)
        Image.fromarray(pixels, "RGB").save(self.source)
        self.source_hash = sha256(self.source)
        self.photo_id = import_photo(self.data, self.source)["id"]

    def test_auto_recipe_needs_no_prompt_and_writes_full_master_and_web_version(self):
        proposal = recommend(self.data, self.photo_id)
        self.assertEqual(proposal["preset_id"], "natural")
        self.assertEqual(proposal["settings"]["straighten_deg"], 0)
        self.assertIn("geometry stays unchanged", proposal["measurements"]["geometry_note"])
        with Image.open(BytesIO(preview(self.data, self.photo_id, proposal["settings"]))) as image:
            self.assertLessEqual(max(image.size), 960)
        job = enqueue(self.data, self.photo_id, proposal["settings"], 0, "local-recipe-001")
        self.assertEqual(job["status"], "QUEUED")
        self.assertIsNone(job["image_version_id"])
        completed = run_job(self.data, job["id"])
        self.assertEqual(completed["status"], "SUCCEEDED", completed["error"])
        self.assertEqual(sha256(self.source), self.source_hash)
        db = connect(self.data)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM compiled_prompts").fetchone()[0], 0)
            recipe = db.execute("SELECT * FROM local_recipes WHERE photo_id=?", (self.photo_id,)).fetchone()
            self.assertEqual(recipe["version_number"], 1)
            self.assertEqual(recipe["source_hash"], self.source_hash)
            self.assertEqual(recipe["user_modified"], 0)
            version = db.execute("SELECT * FROM image_versions WHERE id=?", (completed["image_version_id"],)).fetchone()
            self.assertEqual(version["review_status"], "PENDING")
            self.assertIsNone(version["job_id"])
            self.assertIsNone(version["publication_input_id"])
            self.assertEqual((version["width"], version["height"]), (1600, 1067))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM publication_inputs").fetchone()[0], 0)
        finally:
            db.close()
        master = master_media(self.data, self.photo_id, completed["image_version_id"])
        with Image.open(master) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, (1800, 1200))
            self.assertFalse(image.getexif())
            with Image.open(self.source) as original:
                replay = apply_recipe(original, proposal["settings"])
                self.assertEqual(replay.tobytes(), image.tobytes())
        self.assertEqual(audit_artifacts(self.data)["changed"], [])
        with TestClient(create_app(self.data)) as client:
            approved = client.post(f"/api/photos/{self.photo_id}/versions/{completed['image_version_id']}/review",
                                   json={"decision": "APPROVED"})
            self.assertEqual(approved.status_code, 200, approved.text)
            media = client.get(f"/api/photos/{self.photo_id}/versions/{completed['image_version_id']}/master")
            self.assertEqual(media.status_code, 200)
        self.assertEqual(preview_export(self.data)["approved_count"], 1)

    def test_crop_straighten_lens_and_rejected_recipe_guard(self):
        settings = recommend(self.data, self.photo_id)["settings"]
        settings.update({"crop": [.1, .1, .9, .9], "straighten_deg": 1.0,
                         "lens_k1": -.04, "perspective_vertical": .03})
        with Image.open(self.source) as source:
            corrected = apply_recipe(source, settings)
            self.assertLess(corrected.width, source.width)
            self.assertLess(corrected.height, source.height)
        first = enqueue(self.data, self.photo_id, settings, 0, "local-recipe-002")
        completed = run_job(self.data, first["id"])
        self.assertEqual(completed["status"], "SUCCEEDED", completed["error"])
        with TestClient(create_app(self.data)) as client:
            response = client.post(f"/api/photos/{self.photo_id}/versions/{completed['image_version_id']}/review",
                                   json={"decision": "REJECTED"})
            self.assertEqual(response.status_code, 200, response.text)
        with self.assertRaisesRegex(LocalCorrectionError, "Identical rejected"):
            enqueue(self.data, self.photo_id, settings, 0, "local-recipe-003")
        self.assertEqual(sha256(self.source), self.source_hash)
        with self.assertRaises(LocalCorrectionError):
            validate_settings(settings | {"crop": [.6, 0, .5, 1]})

    def test_api_queues_local_without_prompt_paid_authorization_or_budget(self):
        settings = recommend(self.data, self.photo_id)["settings"]
        with TestClient(create_app(self.data)) as client:
            response = client.post(f"/api/photos/{self.photo_id}/local-edits", json={
                "settings": settings, "expected_revision": 0, "request_key": "api-local-recipe-001"})
            self.assertEqual(response.status_code, 200, response.text)
            job_id = response.json()["id"]
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                status = client.get(f"/api/local/jobs/{job_id}").json()
                if status["status"] not in ("QUEUED", "RUNNING"):
                    break
                time.sleep(.05)
            self.assertEqual(status["status"], "SUCCEEDED", status["error"])
            detail = client.get(f"/api/photos/{self.photo_id}").json()
            self.assertEqual(detail["versions"][0]["review_status"], "PENDING")
            self.assertTrue(detail["versions"][0]["master_url"])
            self.assertEqual(client.get(f"/api/photos/{self.photo_id}/versions/{status['image_version_id']}/master").status_code, 200)
            stale = client.post(f"/api/photos/{self.photo_id}/local-edits", json={
                "settings": settings, "expected_revision": 99, "request_key": "api-local-recipe-002"})
            self.assertEqual(stale.status_code, 409)
        db = connect(self.data)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM compiled_prompts").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM edit_jobs").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM local_jobs").fetchone()[0], 1)
        finally:
            db.close()
        self.assertEqual(sha256(self.source), self.source_hash)

    def test_queued_local_job_is_failed_on_restart_without_creating_a_version(self):
        settings = recommend(self.data, self.photo_id)["settings"]
        queued = enqueue(self.data, self.photo_id, settings, 0, "local-restart-001")
        with TestClient(create_app(self.data)) as client:
            status = client.get(f"/api/local/jobs/{queued['id']}").json()
            self.assertEqual(status["status"], "FAILED")
            self.assertIsNone(status["image_version_id"])
            self.assertEqual(client.get(f"/api/photos/{self.photo_id}").json()["versions"], [])
        self.assertEqual(sha256(self.source), self.source_hash)

    def test_approved_local_version_can_be_explicitly_replaced_without_deleting_history(self):
        settings = recommend(self.data, self.photo_id)["settings"]
        first_job = enqueue(self.data, self.photo_id, settings, 0, "local-replace-001")
        first = run_job(self.data, first_job["id"])
        self.assertEqual(first["status"], "SUCCEEDED", first["error"])
        with TestClient(create_app(self.data)) as client:
            approved = client.post(
                f"/api/photos/{self.photo_id}/versions/{first['image_version_id']}/review",
                json={"decision": "APPROVED"},
            )
            self.assertEqual(approved.status_code, 200, approved.text)
        with self.assertRaisesRegex(LocalCorrectionError, "already has an approved"):
            enqueue(self.data, self.photo_id, settings, 0, "local-replace-002")

        replacement_job = enqueue(
            self.data, self.photo_id, settings | {"exposure_ev": 0.1}, 0,
            "local-replace-003", replace_approved=True,
        )
        self.assertEqual(replacement_job["replacement_of_version_id"], first["image_version_id"])
        replacement = run_job(self.data, replacement_job["id"])
        self.assertEqual(replacement["status"], "SUCCEEDED", replacement["error"])
        with TestClient(create_app(self.data)) as client:
            detail = client.get(f"/api/photos/{self.photo_id}").json()
            self.assertEqual([item["review_status"] for item in detail["versions"]], ["APPROVED", "PENDING"])
            self.assertEqual(detail["versions"][1]["replacement_of_version_id"], first["image_version_id"])
            implicit = client.post(
                f"/api/photos/{self.photo_id}/versions/{replacement['image_version_id']}/review",
                json={"decision": "APPROVED"},
            )
            self.assertEqual(implicit.status_code, 409)
            promoted = client.post(
                f"/api/photos/{self.photo_id}/versions/{replacement['image_version_id']}/review",
                json={"decision": "APPROVED", "replace_approved": True},
            )
            self.assertEqual(promoted.status_code, 200, promoted.text)
            detail = client.get(f"/api/photos/{self.photo_id}").json()
        self.assertEqual([item["review_status"] for item in detail["versions"]], ["SUPERSEDED", "APPROVED"])
        self.assertEqual(detail["versions"][0]["superseded_by_version_id"], replacement["image_version_id"])
        export = preview_export(self.data)
        self.assertEqual(export["approved_count"], 1)
        self.assertEqual(export["items"][0]["version_id"], replacement["image_version_id"])
        db = connect(self.data)
        try:
            prior = db.execute("SELECT * FROM image_versions WHERE id=?", (first["image_version_id"],)).fetchone()
            self.assertEqual(prior["review_status"], "REJECTED")
            self.assertEqual(prior["superseded_by_version_id"], replacement["image_version_id"])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM review_events").fetchone()[0], 3)
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM image_versions WHERE photo_id=? AND review_status='APPROVED'",
                (self.photo_id,),
            ).fetchone()[0], 1)
        finally:
            db.close()
        self.assertEqual(sha256(self.source), self.source_hash)


if __name__ == "__main__":
    unittest.main()
