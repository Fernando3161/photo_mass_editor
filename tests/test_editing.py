"""Phase 04 processing checks use synthetic images and never call a provider network service."""

from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import base64
import json
from unittest.mock import patch
from io import BytesIO
from pathlib import Path
import tempfile
import time
import unittest

from fastapi.testclient import TestClient
from PIL import Image

from backend.catalog.database import connect
from backend.catalog.ingestion import import_photo, sha256
from backend.review.app import create_app
from backend.review.image_pipeline import ensure_publication_input
from backend.review.openai_edit import OpenAIEditProvider
from backend.review.editing import (
    EditConflict, EditResult, UnavailableEditProvider, cancel_job, enqueue_batch, preview_batch,
    recover_jobs, review_version, run_job,
)


class FakeEditor:
    model = "fake-image-model"
    estimated_cost_usd = Decimal("0.20")

    def __init__(self):
        self.paths = []
        self.prompts = []
        self.masks = []

    def edit(self, publication_input, prompt, mask):
        self.paths.append(publication_input)
        self.prompts.append(prompt)
        self.masks.append(mask)
        with Image.open(publication_input) as image:
            assert image.format == "JPEG"
            assert max(image.size) == 1600
            assert not image.getexif()
            output = BytesIO()
            image.save(output, "PNG")
        return EditResult(output.getvalue(), ".png", self.model, {"fake": 1}, Decimal("0.18"))


class EditingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.data = root / "data"
        self.source = root / "source.jpg"
        exif = Image.Exif()
        exif[271] = "Synthetic Camera"
        Image.new("RGB", (2000, 1500), "#9c7555").save(self.source, exif=exif)
        self.source_hash = sha256(self.source)
        self.photo_id = import_photo(self.data, self.source)["id"]
        self.editor = FakeEditor()
        self.client = TestClient(create_app(self.data, edit_provider=self.editor))
        saved = self.client.patch(f"/api/photos/{self.photo_id}", json={
            "expected_revision": 0, "primary_subject": "Architecture", "content_tags": [],
            "condition_tags": [], "preset_id": "architecture-clarity",
            "publication_profile_id": "website-standard-v1", "ai_allowance": 0,
            "user_instructions": "Preserve the stonework", "review_state": "IN_PROGRESS",
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        prompt = self.client.post(f"/api/photos/{self.photo_id}/prompts/compile")
        self.assertEqual(prompt.status_code, 200, prompt.text)
        approved = self.client.post(f"/api/prompts/{prompt.json()['id']}/approve")
        self.assertEqual(approved.status_code, 200, approved.text)

    def test_derivative_is_private_1600_jpeg_and_provider_never_receives_original(self):
        preview = preview_batch(self.data, [self.photo_id], "GENERATIVE", self.editor)
        self.assertEqual(preview["estimated_cost_usd"], "0.20")
        self.assertTrue(preview["items"][0]["eligible"])
        denied = self.client.post("/api/edit/batches", json={
            "photo_ids": [self.photo_id], "engine": "GENERATIVE", "authorized": False,
            "budget_usd": "1.00", "request_key": "denied-edit-1",
        })
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.editor.paths, [])
        with self.assertRaises(PermissionError):
            enqueue_batch(self.data, [self.photo_id], "GENERATIVE", {}, self.editor,
                          authorized=False, budget_usd=Decimal("1"), request_key="test-request-1")
        jobs = enqueue_batch(self.data, [self.photo_id], "GENERATIVE", {}, self.editor,
                             authorized=True, budget_usd=Decimal("1"), request_key="test-request-1")
        self.assertEqual(jobs[0]["status"], "QUEUED")
        self.assertEqual(sha256(self.source), self.source_hash)
        finished = run_job(self.data, jobs[0]["id"], self.editor)
        self.assertEqual(finished["status"], "SUCCEEDED", finished["error"])
        self.assertEqual(len(self.editor.paths), 1)
        self.assertNotEqual(self.editor.paths[0], self.source)
        self.assertEqual(sha256(self.source), self.source_hash)
        db = connect(self.data)
        try:
            artifact = db.execute("SELECT * FROM publication_inputs WHERE photo_id=?", (self.photo_id,)).fetchone()
            self.assertEqual((artifact["width"], artifact["height"]), (1600, 1200))
            version = db.execute("SELECT * FROM image_versions WHERE id=?", (finished["image_version_id"],)).fetchone()
            self.assertEqual(version["review_status"], "PENDING")
            self.assertEqual((version["width"], version["height"]), (1600, 1200))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM review_events").fetchone()[0], 0)
        finally:
            db.close()

    def test_rejection_retained_retry_guard_and_explicit_review(self):
        jobs = enqueue_batch(self.data, [self.photo_id], "DETERMINISTIC", {"exposure": 1.1}, self.editor,
                             authorized=True, budget_usd=None, request_key="deterministic-1")
        first = run_job(self.data, jobs[0]["id"], self.editor)
        self.assertEqual(first["status"], "SUCCEEDED", first["error"])
        rejected = review_version(self.data, self.photo_id, first["image_version_id"], "REJECTED", "Too bright")
        self.assertEqual(rejected["review_status"], "REJECTED")
        preview = preview_batch(self.data, [self.photo_id], "DETERMINISTIC", self.editor, {"exposure": 1.1})
        self.assertFalse(preview["items"][0]["eligible"])
        self.assertIn("retry override", preview["items"][0]["reason"])
        with self.assertRaises(EditConflict):
            enqueue_batch(self.data, [self.photo_id], "DETERMINISTIC", {"exposure": 1.1}, self.editor,
                          authorized=True, budget_usd=None, request_key="deterministic-2")
        retry = enqueue_batch(self.data, [self.photo_id], "DETERMINISTIC", {"exposure": 1.1}, self.editor,
                              authorized=True, budget_usd=None, request_key="deterministic-3", retry_override=True)
        second = run_job(self.data, retry[0]["id"], self.editor)
        self.assertEqual(second["status"], "SUCCEEDED", second["error"])
        approved = review_version(self.data, self.photo_id, second["image_version_id"], "APPROVED", None)
        self.assertEqual(approved["review_status"], "APPROVED")
        with self.assertRaises(EditConflict):
            enqueue_batch(self.data, [self.photo_id], "DETERMINISTIC", {}, self.editor,
                          authorized=True, budget_usd=None, request_key="deterministic-4")
        db = connect(self.data)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM image_versions").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM review_events").fetchone()[0], 2)
        finally:
            db.close()

    def test_request_idempotency_and_failure_receipt(self):
        jobs = enqueue_batch(self.data, [self.photo_id], "DETERMINISTIC", {}, self.editor,
                             authorized=True, budget_usd=None, request_key="stable-key-1")
        repeated = enqueue_batch(self.data, [self.photo_id], "DETERMINISTIC", {}, self.editor,
                                 authorized=True, budget_usd=None, request_key="stable-key-1")
        self.assertEqual(jobs[0]["id"], repeated[0]["id"])
        with self.assertRaises(EditConflict):
            enqueue_batch(self.data, [self.photo_id], "DETERMINISTIC", {"exposure": 1.2}, self.editor,
                          authorized=True, budget_usd=None, request_key="stable-key-1")
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: run_job(self.data, jobs[0]["id"], self.editor), range(2)))
        self.assertIn("SUCCEEDED", [item["status"] for item in outcomes])
        db = connect(self.data)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM image_versions").fetchone()[0], 1)
        finally:
            db.close()

    def test_failed_provider_keeps_receipt_and_no_approved_image(self):
        class FailingEditor(FakeEditor):
            def edit(self, publication_input, prompt, mask):
                raise RuntimeError("synthetic provider failure")

        failing = FailingEditor()
        jobs = enqueue_batch(self.data, [self.photo_id], "GENERATIVE", {}, failing,
                             authorized=True, budget_usd=Decimal("1"), request_key="provider-fail-1")
        result = run_job(self.data, jobs[0]["id"], failing)
        self.assertEqual(result["status"], "FAILED")
        self.assertNotIn("synthetic provider failure", result["error"])
        db = connect(self.data)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM image_versions").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM publication_inputs").fetchone()[0], 1)
            self.assertIn("synthetic provider failure", db.execute("SELECT error FROM edit_jobs WHERE id=?", (jobs[0]["id"],)).fetchone()[0])
        finally:
            db.close()
        with self.assertRaises(EditConflict):
            enqueue_batch(self.data, [self.photo_id], "GENERATIVE", {}, UnavailableEditProvider(),
                          authorized=True, budget_usd=Decimal("1"), request_key="no-provider-1")

    def test_mask_matches_derivative_and_review_api_returns_edited_media(self):
        mask = Image.new("RGBA", (1600, 1200), (0, 0, 0, 255))
        mask.putpixel((50, 50), (0, 0, 0, 0))
        output = BytesIO()
        mask.save(output, format="PNG")
        saved = self.client.post(f"/api/photos/{self.photo_id}/masks", content=output.getvalue(),
                                 headers={"Content-Type": "image/png"})
        self.assertEqual(saved.status_code, 200, saved.text)
        mask_id = saved.json()["id"]
        jobs = enqueue_batch(self.data, [self.photo_id], "GENERATIVE", {}, self.editor,
                             authorized=True, budget_usd=Decimal("1"), request_key="masked-run-1", mask_id=mask_id)
        result = run_job(self.data, jobs[0]["id"], self.editor)
        self.assertEqual(result["status"], "SUCCEEDED", result["error"])
        self.assertIn("Application AI allowance: 0 of 10", self.editor.prompts[0])
        self.assertIn("Do not introduce semantic changes or new scene content", self.editor.prompts[0])
        self.assertIsNotNone(self.editor.masks[0])
        media = self.client.get(f"/api/photos/{self.photo_id}/versions/{result['image_version_id']}/image")
        self.assertEqual(media.status_code, 200)
        with Image.open(BytesIO(media.content)) as image:
            self.assertEqual(image.size, (1600, 1200))
            self.assertFalse(image.getexif())
        approved = self.client.post(
            f"/api/photos/{self.photo_id}/versions/{result['image_version_id']}/review",
            json={"decision": "APPROVED"},
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        repeat = self.client.post(
            f"/api/photos/{self.photo_id}/versions/{result['image_version_id']}/review",
            json={"decision": "APPROVED"},
        )
        self.assertEqual(repeat.status_code, 409)

    def test_openai_adapter_serializes_only_publication_input_without_network(self):
        db = connect(self.data)
        try:
            profile = dict(db.execute("SELECT * FROM publication_profiles WHERE id='website-standard-v1'").fetchone())
            artifact = ensure_publication_input(db, self.data, self.photo_id, profile)
            db.commit()
        finally:
            db.close()
        derivative = self.data / artifact["path"]
        with Image.open(derivative) as image:
            output = BytesIO()
            image.save(output, "PNG")
        response = BytesIO(json.dumps({"data": [{"b64_json": base64.b64encode(output.getvalue()).decode()}],
                                       "usage": {"input_tokens": 1}}).encode())
        captured = []

        def fake_urlopen(request, timeout):
            captured.append(request)
            return response

        provider = OpenAIEditProvider(api_key="synthetic-key", model="gpt-image-2.5-sunburst",
                                      planning_cost_usd=Decimal("0.20"))
        with patch("backend.review.openai_edit.urlopen", fake_urlopen):
            result = provider.edit(derivative, "Preserve the scene", None)
        self.assertEqual(result.suffix, ".png")
        self.assertEqual(result.usage["input_tokens"], 1)
        self.assertEqual(len(captured), 1)
        self.assertIn(derivative.read_bytes(), captured[0].data)
        self.assertNotIn(self.source.read_bytes(), captured[0].data)
        self.assertIn(b"size\"\r\n\r\n1600x1200", captured[0].data)

    def test_restart_requires_new_authorization_for_queued_paid_job(self):
        jobs = enqueue_batch(self.data, [self.photo_id], "GENERATIVE", {}, self.editor,
                             authorized=True, budget_usd=Decimal("1"), request_key="restart-paid-1")
        with ThreadPoolExecutor(max_workers=2) as pool:
            recover_jobs(self.data, self.editor, pool)
        self.assertEqual(self.editor.paths, [])
        db = connect(self.data)
        try:
            status, error = db.execute("SELECT status,error FROM edit_jobs WHERE id=?", (jobs[0]["id"],)).fetchone()
            self.assertEqual(status, "FAILED")
            self.assertIn("reauthorize", error)
        finally:
            db.close()

    def test_bad_provider_aspect_keeps_raw_attempt_without_review_version(self):
        class WrongAspectEditor(FakeEditor):
            def edit(self, publication_input, prompt, mask):
                output = BytesIO()
                Image.new("RGB", (1600, 1000), "#655443").save(output, "PNG")
                return EditResult(output.getvalue(), ".png", self.model, {"fake": 1})

        editor = WrongAspectEditor()
        jobs = enqueue_batch(self.data, [self.photo_id], "GENERATIVE", {}, editor,
                             authorized=True, budget_usd=Decimal("1"), request_key="wrong-aspect-1")
        result = run_job(self.data, jobs[0]["id"], editor)
        self.assertEqual(result["status"], "FAILED")
        db = connect(self.data)
        try:
            row = db.execute("SELECT raw_path,raw_sha256,error FROM edit_jobs WHERE id=?", (jobs[0]["id"],)).fetchone()
            self.assertTrue((self.data / row["raw_path"]).is_file())
            self.assertEqual(sha256(self.data / row["raw_path"]), row["raw_sha256"])
            self.assertIn("aspect ratio", row["error"])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM image_versions").fetchone()[0], 0)
        finally:
            db.close()

    def test_draft_change_after_queue_prevents_execution(self):
        jobs = enqueue_batch(self.data, [self.photo_id], "GENERATIVE", {}, self.editor,
                             authorized=True, budget_usd=Decimal("1"), request_key="stale-queue-1")
        changed = self.client.patch(f"/api/photos/{self.photo_id}", json={
            "expected_revision": 1, "primary_subject": "Architecture", "content_tags": [],
            "condition_tags": [], "preset_id": "architecture-clarity",
            "publication_profile_id": "website-standard-v1", "ai_allowance": 1,
            "user_instructions": "Different instruction", "review_state": "IN_PROGRESS",
        })
        self.assertEqual(changed.status_code, 200, changed.text)
        result = run_job(self.data, jobs[0]["id"], self.editor)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(self.editor.paths, [])

    def test_queued_job_can_be_cancelled_without_creating_a_version(self):
        jobs = enqueue_batch(self.data, [self.photo_id], "DETERMINISTIC", {}, self.editor,
                             authorized=True, budget_usd=None, request_key="cancelled-local-1")
        cancelled = cancel_job(self.data, jobs[0]["id"])
        self.assertEqual(cancelled["status"], "CANCELLED")
        self.assertEqual(run_job(self.data, jobs[0]["id"], self.editor)["status"], "CANCELLED")
        db = connect(self.data)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM image_versions").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT status FROM edit_batches WHERE id=?", (jobs[0]["batch_id"],)).fetchone()[0], "CANCELLED")
        finally:
            db.close()

    def test_api_queues_and_serves_completed_local_job(self):
        with TestClient(create_app(self.data, edit_provider=self.editor)) as client:
            submitted = client.post("/api/edit/batches", json={
                "photo_ids": [self.photo_id], "engine": "DETERMINISTIC", "authorized": True,
                "settings": {"contrast": 1.1}, "request_key": "api-local-run-1",
            })
            self.assertEqual(submitted.status_code, 200, submitted.text)
            batch_id = submitted.json()["jobs"][0]["batch_id"]
            for _ in range(100):
                current = client.get(f"/api/edit/batches/{batch_id}").json()["jobs"][0]
                if current["status"] not in ("QUEUED", "RUNNING"):
                    break
                time.sleep(0.03)
            self.assertEqual(current["status"], "SUCCEEDED", current["error"])
            detail = client.get(f"/api/photos/{self.photo_id}").json()
            self.assertEqual(detail["versions"][0]["review_status"], "PENDING")
            self.assertEqual(client.get(detail["versions"][0]["image_url"]).status_code, 200)


if __name__ == "__main__":
    unittest.main()
