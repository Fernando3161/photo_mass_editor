"""V2 Priority 3 text refinement uses a fake provider and synthetic image."""

from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from PIL import Image

from backend.catalog.database import connect
from backend.catalog.ingestion import import_photo, sha256
from backend.review.app import create_app
from backend.review.prompt_refinement import RefinementResult


class FakeRefiner:
    name = "fake"
    model = "fake-text"
    template_version = "test-v1"

    def __init__(self):
        self.calls = []
        self.output = None

    def refine(self, baseline):
        self.calls.append(baseline)
        return RefinementResult(self.output or baseline, {"secret_trace": "private"}, {"tokens": 10}, Decimal("0.0001"))


class RefinementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.data = root / "catalog"
        self.source = root / "original.jpg"
        Image.new("RGB", (40, 30), "#637786").save(self.source)
        self.original_hash = sha256(self.source)
        self.photo_id = import_photo(self.data, self.source)["id"]
        self.refiner = FakeRefiner()
        self.client = TestClient(create_app(self.data, refinement_provider=self.refiner))
        saved = self.client.patch(f"/api/photos/{self.photo_id}", json={
            "expected_revision": 0, "preset_id": "natural-balance", "publication_profile_id": "website-standard-v1",
            "ai_allowance": 0, "user_instructions": "Keep the stone texture.",
            "approved_constraints": "Preserve the sky.", "semantic_change_consent": False,
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        compiled = self.client.post(f"/api/photos/{self.photo_id}/prompts/compile")
        self.assertEqual(compiled.status_code, 200, compiled.text)
        self.prompt = compiled.json()

    def test_authorization_cost_text_only_and_explicit_approval(self):
        prompt_id = self.prompt["id"]
        estimate = self.client.post(f"/api/prompts/{prompt_id}/refinement/estimate")
        self.assertEqual(estimate.status_code, 200, estimate.text)
        budget = estimate.json()["estimated_cost_usd"]
        route = f"/api/prompts/{prompt_id}/refinement/run"
        self.assertEqual(self.client.post(route, json={"budget_usd": budget}).status_code, 403)
        self.assertEqual(self.client.post(route, json={"authorized": True, "budget_usd": "0"}).status_code, 409)
        self.assertEqual(self.refiner.calls, [])
        result = self.client.post(route, json={"authorized": True, "budget_usd": budget})
        self.assertEqual(result.status_code, 200, result.text)
        proposal = result.json()
        self.assertEqual(self.refiner.calls, [self.prompt["compiled_text"]])
        self.assertNotIn(str(self.source), result.text)
        self.assertNotIn(self.original_hash, result.text)
        self.assertNotIn("secret_trace", result.text)
        self.assertEqual(sha256(self.source), self.original_hash)
        db = connect(self.data)
        try:
            row = db.execute("SELECT * FROM prompt_refinements WHERE id=?", (proposal["id"],)).fetchone()
            self.assertEqual(row["source_hash"], self.original_hash)
            self.assertIn("secret_trace", row["response_json"])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM edit_jobs").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM image_versions").fetchone()[0], 0)
        finally:
            db.close()
        adopted = self.client.post(f"/api/prompt-refinements/{proposal['id']}/adopt")
        self.assertEqual(adopted.status_code, 200, adopted.text)
        self.assertEqual(adopted.json()["approved_for_job"], 0)
        self.assertEqual(adopted.json()["refinement_id"], proposal["id"])
        self.assertEqual(self.client.post(f"/api/prompts/{adopted.json()['id']}/approve").status_code, 200)

    def test_removed_owner_instruction_is_blocked_and_baseline_survives(self):
        self.refiner.output = self.prompt["compiled_text"].replace("Owner instructions: Keep the stone texture.\n", "")
        budget = self.client.post(f"/api/prompts/{self.prompt['id']}/refinement/estimate").json()["estimated_cost_usd"]
        proposal = self.client.post(f"/api/prompts/{self.prompt['id']}/refinement/run",
                                    json={"authorized": True, "budget_usd": budget}).json()
        self.assertEqual(proposal["restored_requirements"], 1)
        self.assertIn("Owner instructions: Keep the stone texture.", proposal["adoption_text"])
        blocked = self.client.post(f"/api/prompt-refinements/{proposal['id']}/adopt",
                                   json={"compiled_text": proposal["proposed_text"]})
        self.assertEqual(blocked.status_code, 409, blocked.text)
        self.assertEqual(self.client.post(f"/api/prompts/{self.prompt['id']}/approve").status_code, 200)

    def test_saved_ai_proposal_can_be_repaired_and_adopted_without_new_paid_call(self):
        required = next(line for line in self.prompt["compiled_text"].splitlines()
                        if line.startswith("Use only the deterministic publication input"))
        self.refiner.output = self.prompt["compiled_text"].replace(required + "\n", "")
        budget = self.client.post(f"/api/prompts/{self.prompt['id']}/refinement/estimate").json()["estimated_cost_usd"]
        proposal = self.client.post(f"/api/prompts/{self.prompt['id']}/refinement/run",
                                    json={"authorized": True, "budget_usd": budget}).json()
        self.assertEqual(proposal["restored_requirements"], 1)
        self.assertNotIn(required, proposal["proposed_text"])
        self.assertIn(required, proposal["adoption_text"])
        history = self.client.get(f"/api/photos/{self.photo_id}/prompt-refinements").json()
        self.assertEqual(history[0]["adoption_text"], proposal["adoption_text"])
        adopted = self.client.post(f"/api/prompt-refinements/{proposal['id']}/adopt",
                                   json={"compiled_text": history[0]["adoption_text"]})
        self.assertEqual(adopted.status_code, 200, adopted.text)
        self.assertEqual(adopted.json()["compiled_text"], proposal["adoption_text"])
        self.assertEqual(adopted.json()["refinement_id"], proposal["id"])
        self.assertEqual(adopted.json()["approved_for_job"], 0)
        self.assertEqual(len(self.refiner.calls), 1)
        photo = self.client.get(f"/api/photos/{self.photo_id}").json()
        self.assertEqual(photo["prompt_history"][0]["id"], adopted.json()["id"])
        db = connect(self.data)
        try:
            raw = db.execute("SELECT proposed_text FROM prompt_refinements WHERE id=?",
                             (proposal["id"],)).fetchone()[0]
            self.assertEqual(raw, proposal["proposed_text"])
        finally:
            db.close()

    def test_stale_prompt_cannot_run_or_adopt(self):
        budget = self.client.post(f"/api/prompts/{self.prompt['id']}/refinement/estimate").json()["estimated_cost_usd"]
        proposal = self.client.post(f"/api/prompts/{self.prompt['id']}/refinement/run",
                                    json={"authorized": True, "budget_usd": budget}).json()
        self.assertEqual(proposal["status"], "SUCCEEDED")
        changed = self.client.patch(f"/api/photos/{self.photo_id}", json={
            "expected_revision": 1, "preset_id": "natural-balance", "publication_profile_id": "website-standard-v1",
            "ai_allowance": 0, "user_instructions": "Keep the newer texture.",
        })
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(self.client.post(f"/api/prompt-refinements/{proposal['id']}/adopt").status_code, 409)
        self.assertEqual(self.client.post(f"/api/prompts/{self.prompt['id']}/refinement/run",
                                          json={"authorized": True, "budget_usd": budget}).status_code, 409)


if __name__ == "__main__":
    unittest.main()
