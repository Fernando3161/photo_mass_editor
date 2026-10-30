"""Phase 03 analysis and prompt tests use an injected provider and no network."""

from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from PIL import Image

from backend.catalog.database import connect
from backend.catalog.ingestion import import_photo
from backend.review.analysis import AnalysisSuggestion
from backend.review.app import create_app


class FakeProvider:
    provider_name = "fake-local-test"
    model = "fake-vision-1"
    template_version = "test-v1"
    currency = "USD"

    def __init__(self, signature="fake-vision-1:test-v1"):
        self.config_signature = signature
        self.calls = 0

    def estimate(self, image_count):
        return Decimal("0.05") * image_count

    def analyze(self, image_path, context):
        self.calls += 1
        return AnalysisSuggestion(
            primary_subject="Architecture",
            tags=[{"display_name": "facade", "kind": "CONTENT", "confidence": 0.91}],
            suggested_edits="Correct perspective conservatively.",
            raw_response={"private_provider_trace": "server-only-test-value"},
            usage={"images": 1},
            actual_cost=Decimal("0.04"),
        )


class AnalysisPromptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.data = root / "data"
        source = root / "source.jpg"
        Image.new("RGB", (40, 24), "#54718a").save(source)
        self.photo_id = import_photo(self.data, source)["id"]
        self.provider = FakeProvider()
        self.client = TestClient(create_app(self.data, analysis_provider=self.provider))

    def save_payload(self, revision=0, **updates):
        payload = {
            "expected_revision": revision,
            "editorial_description": "",
            "city": "",
            "country": "",
            "primary_subject": "Architecture",
            "content_tags": ["facade"],
            "condition_tags": ["daylight"],
            "preset_id": "architecture-clarity",
            "ai_allowance": 2,
            "ai_suggestion_editable": "Correct perspective conservatively.",
            "user_instructions": "Preserve the stone texture.",
            "approved_constraints": "Keep the sky unchanged.",
            "semantic_change_consent": False,
            "analysis_run_id": None,
            "review_state": "IN_PROGRESS",
        }
        payload.update(updates)
        return payload

    def test_analysis_requires_permission_estimates_cost_and_uses_cache(self):
        request = {"photo_ids": [self.photo_id]}
        estimate = self.client.post("/api/analysis/estimate", json=request)
        self.assertEqual(estimate.status_code, 200, estimate.text)
        self.assertEqual(estimate.json()["estimated_cost"], "0.05")
        self.assertEqual(estimate.json()["billable_count"], 1)

        denied = self.client.post("/api/analysis/run", json=request)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.provider.calls, 0)

        first = self.client.post("/api/analysis/run", json={**request, "authorized": True})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertFalse(first.json()["results"][0]["cached"])
        self.assertNotIn("raw_response", first.text)
        self.assertNotIn("server-only-test-value", first.text)
        self.assertEqual(self.provider.calls, 1)

        second = self.client.post("/api/analysis/run", json={**request, "authorized": True})
        self.assertTrue(second.json()["results"][0]["cached"])
        self.assertEqual(self.provider.calls, 1)
        cached_estimate = self.client.post("/api/analysis/estimate", json=request).json()
        self.assertEqual(cached_estimate["billable_count"], 0)
        self.assertEqual(cached_estimate["estimated_cost"], "0.00")

    def test_changed_analysis_config_invalidates_cache(self):
        request = {"photo_ids": [self.photo_id], "authorized": True}
        self.assertEqual(self.client.post("/api/analysis/run", json=request).status_code, 200)
        changed = FakeProvider("fake-vision-1:test-v2")
        changed_client = TestClient(create_app(self.data, analysis_provider=changed))
        result = changed_client.post("/api/analysis/run", json=request)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["results"][0]["cached"])
        self.assertEqual(changed.calls, 1)

    def test_prompt_conflicts_version_edit_approval_and_invalidation(self):
        conflicting = self.client.patch(
            f"/api/photos/{self.photo_id}",
            json=self.save_payload(user_instructions="Replace the sky with sunset."),
        )
        self.assertEqual(conflicting.status_code, 200)
        blocked = self.client.post(f"/api/photos/{self.photo_id}/prompts/compile")
        self.assertEqual(blocked.status_code, 409)
        self.assertIn("sky", blocked.text.lower())

        clean = self.client.patch(
            f"/api/photos/{self.photo_id}",
            json=self.save_payload(revision=1),
        )
        self.assertEqual(clean.status_code, 200, clean.text)
        compiled = self.client.post(f"/api/photos/{self.photo_id}/prompts/compile")
        self.assertEqual(compiled.status_code, 200, compiled.text)
        self.assertEqual(compiled.json()["version_number"], 1)
        self.assertFalse(compiled.json()["approved_for_job"])

        edited = self.client.patch(
            f"/api/prompts/{compiled.json()['id']}",
            json={"compiled_text": compiled.json()["compiled_text"] + "\nKeep crop unchanged."},
        )
        self.assertEqual(edited.json()["version_number"], 2)
        self.assertEqual(edited.json()["parent_prompt_id"], compiled.json()["id"])
        self.assertTrue(edited.json()["user_modified"])

        approved = self.client.post(f"/api/prompts/{edited.json()['id']}/approve")
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertTrue(approved.json()["approved_for_job"])

        changed = self.client.patch(
            f"/api/photos/{self.photo_id}",
            json=self.save_payload(revision=2, user_instructions="Also reduce highlights."),
        )
        self.assertEqual(changed.status_code, 200)
        stale = self.client.post(f"/api/prompts/{edited.json()['id']}/approve")
        self.assertEqual(stale.status_code, 409)
        detail = self.client.get(f"/api/photos/{self.photo_id}").json()
        old = next(item for item in detail["prompt_history"] if item["id"] == edited.json()["id"])
        self.assertFalse(old["approved_for_job"])

    def test_preset_edit_invalidates_approved_prompt(self):
        self.assertEqual(
            self.client.patch(f"/api/photos/{self.photo_id}", json=self.save_payload()).status_code, 200
        )
        prompt = self.client.post(f"/api/photos/{self.photo_id}/prompts/compile").json()
        self.assertEqual(self.client.post(f"/api/prompts/{prompt['id']}/approve").status_code, 200)
        preset = self.client.patch(
            "/api/presets/architecture-clarity",
            json={"name": "Architecture clarity", "structured_instructions": "Revised instructions."},
        )
        self.assertEqual(preset.status_code, 200)
        detail = self.client.get(f"/api/photos/{self.photo_id}").json()
        self.assertTrue(detail["draft"]["compiled_prompt_stale"])
        self.assertFalse(detail["prompt_history"][0]["approved_for_job"])

    def test_high_allowance_requires_explicit_semantic_consent(self):
        saved = self.client.patch(
            f"/api/photos/{self.photo_id}",
            json=self.save_payload(ai_allowance=6, semantic_change_consent=False),
        )
        self.assertEqual(saved.status_code, 200)
        blocked = self.client.post(f"/api/photos/{self.photo_id}/prompts/compile")
        self.assertEqual(blocked.status_code, 409)
        allowed = self.client.patch(
            f"/api/photos/{self.photo_id}",
            json=self.save_payload(revision=1, ai_allowance=6, semantic_change_consent=True),
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(self.client.post(f"/api/photos/{self.photo_id}/prompts/compile").status_code, 200)

    def test_schema_version_three_contains_analysis_and_prompt_tables(self):
        db = connect(self.data)
        try:
            self.assertEqual(db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 3)
            names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({"analysis_runs", "compiled_prompts"}.issubset(names))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
