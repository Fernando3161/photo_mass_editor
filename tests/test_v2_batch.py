"""V2 selection-wide local and prompt workflows use only tiny synthetic sources."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.catalog.database import connect
from backend.catalog.ingestion import import_photo, sha256
from backend.review.app import create_app
from backend.review import local_batch, local_corrections, prompt_batch


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.data = root / "catalog"
        self.sources = []
        self.ids = []
        for number in range(2):
            path = root / f"photo-{number}.png"
            Image.new("RGB", (48, 32), (60 + number * 20, 90, 130)).save(path)
            self.sources.append((path, sha256(path)))
            self.ids.append(import_photo(self.data, path)["id"])

    def test_local_preview_mixed_selection_named_recipe_override_and_receipts(self):
        settings = local_corrections.recommend(self.data, self.ids[0])["settings"]
        named = local_batch.save_named_recipe(self.data, "Warm daylight", settings)
        self.assertEqual(local_batch.named_recipes(self.data)[0]["id"], named["id"])
        first = local_batch.preview(self.data, self.ids, named["id"])
        self.assertEqual(first["eligible_count"], 2)
        self.assertNotIn("source_hash", str(first))
        self.assertEqual(first["items"][0]["output_targets"], ["full-resolution PNG master", "website JPEG"])
        adjusted = dict(settings, exposure_ev=0.25)
        changed = local_batch.preview(self.data, self.ids, named["id"], {self.ids[1]: adjusted})
        self.assertNotEqual(first["signature"], changed["signature"])
        with self.assertRaises(local_corrections.LocalCorrectionError):
            local_batch.enqueue(self.data, self.ids, "batch-request-01", first["signature"], named["id"], {self.ids[1]: adjusted})
        queued = local_batch.enqueue(self.data, self.ids, "batch-request-02", changed["signature"], named["id"], {self.ids[1]: adjusted})
        self.assertEqual(len(queued["jobs"]), 2)
        self.assertEqual(local_batch.enqueue(self.data, self.ids, "batch-request-02", changed["signature"], named["id"], {self.ids[1]: adjusted})["id"], queued["id"])
        local_corrections.run_job(self.data, queued["jobs"][0]["id"])
        local_batch.cancel(self.data, queued["id"])
        status = local_batch.batch_status(self.data, queued["id"])
        self.assertEqual({job["status"] for job in status["jobs"]}, {"SUCCEEDED", "CANCELLED"})
        self.assertEqual(status["status"], "COMPLETED")
        db = connect(self.data)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM image_versions WHERE review_status='PENDING'").fetchone()[0], 1)
        finally:
            db.close()
        for path, digest in self.sources:
            self.assertEqual(sha256(path), digest)

    def test_api_requires_current_run_authorization_for_local_batch(self):
        client = TestClient(create_app(self.data))
        plan = local_batch.preview(self.data, self.ids)
        response = client.post("/api/local/batches", json={"photo_ids": self.ids,
            "preview_signature": plan["signature"], "request_key": "auth-denied-001"})
        self.assertEqual(response.status_code, 403)
        db = connect(self.data)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM local_batches").fetchone()[0], 0)
        finally:
            db.close()

    def test_rejected_duplicate_and_batch_restart(self):
        plan = local_batch.preview(self.data, self.ids)
        queued = local_batch.enqueue(self.data, self.ids, "batch-restart-01", plan["signature"])
        resumable = local_batch.resume_queued(self.data)
        self.assertEqual(set(resumable), {job["id"] for job in queued["jobs"]})
        self.assertEqual(local_batch.recent_batches(self.data)[0]["id"], queued["id"])
        completed = local_corrections.run_job(self.data, resumable[0])
        self.assertEqual(completed["status"], "SUCCEEDED", completed["error"])
        with TestClient(create_app(self.data)) as client:
            version_id = completed["image_version_id"]
            self.assertEqual(client.post(f"/api/photos/{self.ids[0]}/versions/{version_id}/review", json={"decision": "REJECTED"}).status_code, 200)
        result = local_batch.preview(self.data, [self.ids[0]])
        self.assertFalse(result["items"][0]["eligible"])
        self.assertTrue(local_batch.preview(self.data, [self.ids[0]], retry_override=True)["items"][0]["eligible"])

    def test_one_failed_render_does_not_discard_another_batch_receipt(self):
        plan = local_batch.preview(self.data, self.ids)
        batch = local_batch.enqueue(self.data, self.ids, "batch-partial-01", plan["signature"])
        with patch.object(local_corrections, "apply_recipe", side_effect=RuntimeError("synthetic render failure")):
            failed = local_corrections.run_job(self.data, batch["jobs"][0]["id"])["status"]
        succeeded = local_corrections.run_job(self.data, batch["jobs"][1]["id"])["status"]
        outcomes = [failed, succeeded]
        self.assertEqual(outcomes, ["FAILED", "SUCCEEDED"])
        self.assertEqual(len(local_batch.batch_status(self.data, batch["id"])["jobs"]), 2)
        for path, digest in self.sources:
            self.assertEqual(sha256(path), digest)

    def test_prompt_diffs_acknowledgment_staleness_and_approval(self):
        client = TestClient(create_app(self.data))
        for photo_id in self.ids:
            response = client.patch(f"/api/photos/{photo_id}", json={
                "expected_revision": 0, "preset_id": "architecture-clarity",
                "publication_profile_id": "website-standard-v1", "approved_constraints": "Keep the sky unchanged.",
                "user_instructions": "Correct tones conservatively.",
            })
            self.assertEqual(response.status_code, 200, response.text)
        plan = prompt_batch.preview(self.data, self.ids, "Refine the local color balance.")
        self.assertTrue(all(item["eligible"] for item in plan["items"]))
        self.assertNotIn("source_hash", str(plan))
        self.assertIn("Selection instruction:", plan["items"][0]["proposed_text"])
        with self.assertRaises(ValueError):
            prompt_batch.compile_selected(self.data, self.ids, "Refine the local color balance.", plan["signature"], [self.ids[0]])
        prompts = prompt_batch.compile_selected(self.data, self.ids, "Refine the local color balance.", plan["signature"], self.ids)
        self.assertEqual(len(prompts), 2)
        db = connect(self.data)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM edit_jobs").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM compiled_prompts WHERE approved_for_job=1").fetchone()[0], 0)
        finally:
            db.close()
        approved = prompt_batch.approve_selected(self.data, {prompt["id"]: prompt["approval_hash"] for prompt in prompts})
        self.assertEqual(len(approved), 2)
        changed = client.patch(f"/api/photos/{self.ids[0]}", json={"expected_revision": 1, "user_instructions": "Change the sky."})
        self.assertEqual(changed.status_code, 200, changed.text)
        with self.assertRaises(Exception):
            prompt_batch.approve_selected(self.data, {prompts[0]["id"]: prompts[0]["approval_hash"]})

    def test_owner_edited_prompt_cannot_remove_constraints_or_add_unconsented_scene_change(self):
        client = TestClient(create_app(self.data))
        saved = client.patch(f"/api/photos/{self.ids[0]}", json={"expected_revision": 0,
            "publication_profile_id": "website-standard-v1", "approved_constraints": "Keep the sky unchanged."})
        self.assertEqual(saved.status_code, 200, saved.text)
        baseline = client.post(f"/api/photos/{self.ids[0]}/prompts/compile").json()
        weakened = client.patch(f"/api/prompts/{baseline['id']}", json={"compiled_text": baseline["compiled_text"].replace("Approved constraints: Keep the sky unchanged.", "")}).json()
        self.assertEqual(client.post(f"/api/prompts/{weakened['id']}/approve").status_code, 409)
        altered = client.patch(f"/api/prompts/{baseline['id']}", json={"compiled_text": baseline["compiled_text"] + "\nRemove the person."}).json()
        self.assertEqual(client.post(f"/api/prompts/{altered['id']}/approve").status_code, 409)

    def test_prompt_preview_is_invalidated_by_draft_change(self):
        client = TestClient(create_app(self.data))
        self.assertEqual(client.patch(f"/api/photos/{self.ids[0]}", json={"expected_revision": 0,
            "publication_profile_id": "website-standard-v1"}).status_code, 200)
        plan = prompt_batch.preview(self.data, [self.ids[0]])
        self.assertEqual(client.patch(f"/api/photos/{self.ids[0]}", json={"expected_revision": 1,
            "publication_profile_id": "website-standard-v1", "user_instructions": "Reduce highlights."}).status_code, 200)
        with self.assertRaises(ValueError):
            prompt_batch.compile_selected(self.data, [self.ids[0]], "", plan["signature"], [self.ids[0]])


if __name__ == "__main__":
    unittest.main()
