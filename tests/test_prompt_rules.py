"""Rule matching, draft isolation, prompt provenance, and batch composition."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.catalog.database import connect
from backend.catalog.ingestion import import_photo
from backend.review.app import create_app
from backend.review.catalog_prefill import _snapshot as catalog_snapshot, _write as accept_catalog_values
from backend.review.prompt_rules import compose, load_rules


class RuleCompositionTests(unittest.TestCase):
    def test_subject_condition_and_priority_composition(self):
        cathedral = compose("religious building", ["architecture", "people"], ["nighttime"])
        ids = cathedral["selected_ids"]
        self.assertEqual(ids.count("architecture-integrity"), 1)
        self.assertLess(ids.index("architecture-light"), ids.index("night-lights"))
        self.assertIn("people-identity", ids)
        self.assertNotIn("architecture-remove-people", ids)
        self.assertEqual(cathedral, compose("religious building", ["architecture", "people"], ["nighttime"]))
        nature = compose("mountain", ["landscape"], ["golden hour"])
        self.assertIn("nature-color", nature["selected_ids"])
        self.assertIn("golden-hour-warmth", nature["selected_ids"])

    def test_animals_transport_and_conditions_do_not_cross(self):
        animal = compose("cat", [], ["blurred", "hazy"])
        transport = compose("train", [], ["reflections"])
        self.assertIn("animal-anatomy", animal["selected_ids"])
        self.assertNotIn("transport-clarity", animal["selected_ids"])
        self.assertIn("transport-clarity", transport["selected_ids"])
        self.assertNotIn("animal-sharpness", transport["selected_ids"])
        self.assertIn("blurred-clarity", animal["selected_ids"])
        self.assertIn("hazy-visibility", animal["selected_ids"])

    def test_optional_consent_conflicts_and_incompatible_weather(self):
        day = compose("street", ["urban"], ["daytime"])
        self.assertFalse(next(rule for rule in day["rules"] if rule["id"] == "urban-clear-sky")["selected"])
        chosen = compose("street", ["urban"], ["daytime"], day["selected_ids"] + ["urban-clear-sky"])
        self.assertTrue(any("consent" in conflict for conflict in chosen["conflicts"]))
        allowed = compose("street", ["urban"], ["daytime"], chosen["selected_ids"], semantic_change_consent=True)
        self.assertFalse(allowed["conflicts"])
        rainy = compose("street", ["urban"], ["rainy"], chosen["selected_ids"], semantic_change_consent=True)
        self.assertNotIn("urban-clear-sky", rainy["selected_ids"])
        night = compose("building", [], ["nighttime"], ["night-sky", "night-dark-sky"], semantic_change_consent=True)
        self.assertTrue(any("conflicts" in conflict for conflict in night["conflicts"]))
        people = compose("person", ["architecture"], [], ["architecture-remove-people"], semantic_change_consent=True)
        self.assertNotIn("architecture-remove-people", people["selected_ids"])
        self.assertEqual(load_rules()["version"], 1)


class RuleWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.data = root / "data"
        self.ids = []
        for index in range(2):
            source = root / f"photo-{index}.jpg"
            Image.new("RGB", (40, 30), (60 + index, 80, 110)).save(source)
            self.ids.append(import_photo(self.data, source)["id"])
        self.client = TestClient(create_app(self.data))

    def payload(self, photo_id, **updates):
        revision = self.client.get(f"/api/photos/{photo_id}").json()["revision"]
        return {"expected_revision": revision, "primary_subject": "building", "content_tags": ["architecture"],
                "condition_tags": ["nighttime"], "user_instructions": "Keep the original crop.",
                "ai_suggestion_editable": "Owner reviewed paid suggestion.", **updates}

    def test_manual_tags_preview_and_accepted_recognition_match(self):
        first, second = self.ids
        manual = self.payload(first)
        preview = self.client.post(f"/api/photos/{first}/prompts/preview", json=manual)
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertIn("night-lights", preview.json()["rule_suggestions"]["selected_ids"])
        self.assertIn("Keep the original crop", preview.json()["proposed_text"])
        self.assertIn("Owner reviewed paid suggestion", preview.json()["proposed_text"])
        self.assertEqual(self.client.patch(f"/api/photos/{first}", json=manual).status_code, 200)
        db = connect(self.data)
        try:
            db.execute("BEGIN IMMEDIATE")
            before = catalog_snapshot(db, second)
            after = {**before, "primary_subject": "building", "content_tags": ["architecture"], "condition_tags": ["nighttime"]}
            accept_catalog_values(db, second, before, after)
            db.commit()
        finally:
            db.close()
        recognized = self.client.get(f"/api/photos/{second}").json()
        compare = self.client.post(f"/api/photos/{second}/prompts/preview", json={
            **self.payload(second), "expected_revision": recognized["revision"]}).json()
        self.assertEqual(preview.json()["rule_suggestions"]["selected_ids"], compare["rule_suggestions"]["selected_ids"])

    def test_edits_selection_idempotence_and_stale_approval(self):
        photo_id = self.ids[0]
        payload = self.payload(photo_id, rule_selected_ids=["architecture-integrity", "architecture-light"],
                               rule_instructions_override="Gently brighten the stonework.")
        saved = self.client.patch(f"/api/photos/{photo_id}", json=payload)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["draft"]["user_instructions"], "Keep the original crop.")
        self.assertEqual(saved.json()["draft"]["ai_suggestion_editable"], "Owner reviewed paid suggestion.")
        first = self.client.post(f"/api/photos/{photo_id}/prompts/compile")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertIn("Gently brighten the stonework", first.json()["compiled_text"])
        self.assertNotIn("Improve architectural illumination", first.json()["compiled_text"])
        self.assertEqual(self.client.post(f"/api/photos/{photo_id}/prompts/compile").json()["id"], first.json()["id"])
        weakened = self.client.patch(f"/api/prompts/{first.json()['id']}", json={"compiled_text":
            first.json()["compiled_text"].replace("Preserve architectural geometry, perspective, proportions, ornaments, and historically relevant details.", "")})
        self.assertEqual(weakened.status_code, 200, weakened.text)
        self.assertEqual(self.client.post(f"/api/prompts/{weakened.json()['id']}/approve").status_code, 409)
        self.assertEqual(self.client.post(f"/api/prompts/{first.json()['id']}/approve").status_code, 200)
        revised = self.client.patch(f"/api/photos/{photo_id}", json=self.payload(photo_id, condition_tags=["golden hour"],
            rule_selected_ids=["architecture-integrity", "architecture-light"], rule_instructions_override="Gently brighten the stonework."))
        self.assertEqual(revised.status_code, 200, revised.text)
        self.assertEqual(revised.json()["draft"]["rule_instructions_override"], "Gently brighten the stonework.")
        self.assertEqual(self.client.post(f"/api/prompts/{first.json()['id']}/approve").status_code, 409)
        refreshed = self.client.post(f"/api/photos/{photo_id}/prompts/preview", json=self.payload(photo_id,
            condition_tags=["golden hour"], rule_selected_ids=None, rule_instructions_override=None)).json()
        self.assertIn("architecture-light", refreshed["rule_suggestions"]["selected_ids"])

    def test_semantic_rule_and_rule_config_change_block_approval(self):
        photo_id = self.ids[0]
        denied = self.client.patch(f"/api/photos/{photo_id}", json=self.payload(photo_id,
            ai_allowance=1, rule_selected_ids=["architecture-remove-people"]))
        self.assertEqual(denied.status_code, 200, denied.text)
        self.assertEqual(self.client.post(f"/api/photos/{photo_id}/prompts/compile").status_code, 409)
        allowed = self.client.patch(f"/api/photos/{photo_id}", json=self.payload(photo_id,
            ai_allowance=1, semantic_change_consent=True, rule_selected_ids=["architecture-remove-people"]))
        self.assertEqual(allowed.status_code, 200, allowed.text)
        compiled = self.client.post(f"/api/photos/{photo_id}/prompts/compile")
        self.assertEqual(compiled.status_code, 200, compiled.text)
        current = load_rules()
        with patch("backend.review.prompts.load_rules", return_value={**current, "sha256": "changed"}):
            self.assertEqual(self.client.post(f"/api/prompts/{compiled.json()['id']}/approve").status_code, 409)

    def test_batch_prompts_are_individualized(self):
        first, second = self.ids
        self.assertEqual(self.client.patch(f"/api/photos/{first}", json=self.payload(first)).status_code, 200)
        self.assertEqual(self.client.patch(f"/api/photos/{second}", json=self.payload(second,
            primary_subject="mountain", content_tags=["landscape"], condition_tags=["golden hour"])).status_code, 200)
        plan = self.client.post("/api/prompt-batches/preview", json={"photo_ids": self.ids, "shared_instruction": ""})
        self.assertEqual(plan.status_code, 200, plan.text)
        items = plan.json()["items"]
        self.assertTrue(all(item["eligible"] for item in items))
        self.assertNotEqual(items[0]["proposed_text"], items[1]["proposed_text"])
        self.assertIn("architectural illumination", items[0]["proposed_text"].lower())
        self.assertIn("golden-hour", items[1]["proposed_text"].lower())
        selected = self.client.post("/api/prompt-batches/compile", json={"photo_ids": self.ids,
            "shared_instruction": "", "preview_signature": plan.json()["signature"], "acknowledged_ids": [first]})
        self.assertEqual(selected.status_code, 200, selected.text)
        self.assertEqual([prompt["photo_id"] for prompt in selected.json()["prompts"]], [first])
