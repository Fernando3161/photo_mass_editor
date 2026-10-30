"""Phase 02 review API tests use only synthetic images and temporary catalogs."""

from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from PIL import Image

from backend.catalog.database import connect
from backend.catalog.ingestion import import_photo, sha256
from backend.review.app import create_app


class ReviewApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.source = self.root / "source.jpg"
        Image.new("RGB", (40, 24), "#8b5a2b").save(self.source)
        self.source_hash = sha256(self.source)
        self.photo_id = import_photo(self.data, self.source)["id"]
        self.client = TestClient(create_app(self.data))

    def payload(self, revision=0, **updates):
        values = {
            "expected_revision": revision,
            "editorial_description": "Stone facade in warm light",
            "city": "Test City",
            "country": "Test Country",
            "primary_subject": "Architecture",
            "content_tags": ["facade", "stone"],
            "condition_tags": ["golden hour"],
            "preset_id": "architecture-clarity",
            "ai_allowance": 2,
            "ai_suggestion_editable": "",
            "user_instructions": "Preserve the masonry texture",
            "review_state": "IN_PROGRESS",
        }
        values.update(updates)
        return values

    def test_list_detail_and_media_do_not_expose_private_coordinates(self):
        listed = self.client.get("/api/photos")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], self.photo_id)
        detail = self.client.get(f"/api/photos/{self.photo_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn("private_lat", detail.json())
        self.assertNotIn("private_lon", detail.json())
        self.assertNotIn("source_hash", detail.text)
        self.assertIn("gps_present", detail.json())
        thumbnail = self.client.get(f"/api/photos/{self.photo_id}/thumbnail")
        self.assertEqual(thumbnail.status_code, 200)
        self.assertEqual(thumbnail.headers["content-type"], "image/png")
        original = self.client.get(f"/api/photos/{self.photo_id}/original")
        self.assertEqual(original.status_code, 200)
        self.assertEqual(sha256(self.source), self.source_hash)

    def test_metadata_tags_draft_and_review_state_persist(self):
        saved = self.client.patch(f"/api/photos/{self.photo_id}", json=self.payload())
        self.assertEqual(saved.status_code, 200, saved.text)
        item = saved.json()
        self.assertEqual(item["revision"], 1)
        self.assertEqual(item["primary_subject"], "Architecture")
        self.assertEqual({tag["display_name"] for tag in item["tags"]}, {"facade", "stone", "golden hour"})
        self.assertEqual(item["draft"]["preset_id"], "architecture-clarity")
        self.assertEqual(item["draft"]["user_instructions"], "Preserve the masonry texture")
        reloaded = self.client.get(f"/api/photos/{self.photo_id}").json()
        self.assertEqual(reloaded["editorial_description"], "Stone facade in warm light")
        self.assertEqual(reloaded["review_state"], "IN_PROGRESS")
        self.assertEqual(sha256(self.source), self.source_hash)

    def test_stale_save_returns_conflict_without_losing_first_save(self):
        first = self.client.patch(f"/api/photos/{self.photo_id}", json=self.payload())
        self.assertEqual(first.status_code, 200)
        stale = self.client.patch(
            f"/api/photos/{self.photo_id}",
            json=self.payload(editorial_description="Overwritten by stale browser"),
        )
        self.assertEqual(stale.status_code, 409)
        current = self.client.get(f"/api/photos/{self.photo_id}").json()
        self.assertEqual(current["editorial_description"], "Stone facade in warm light")

    def test_reviewed_status_and_editable_presets(self):
        saved = self.client.patch(
            f"/api/photos/{self.photo_id}", json=self.payload(review_state="REVIEWED")
        )
        self.assertEqual(saved.json()["review_state"], "REVIEWED")
        db = connect(self.data)
        try:
            row = db.execute("SELECT metadata_reviewed_at FROM photos WHERE id = ?", (self.photo_id,)).fetchone()
            self.assertIsNotNone(row["metadata_reviewed_at"])
        finally:
            db.close()
        preset = self.client.patch(
            "/api/presets/natural-balance",
            json={"name": "My natural preset", "structured_instructions": "Keep colors restrained."},
        )
        self.assertEqual(preset.status_code, 200)
        self.assertEqual(preset.json()["version"], 2)
        options = self.client.get("/api/options").json()
        self.assertIn("My natural preset", [item["name"] for item in options["presets"]])

    def test_schema_migrates_existing_catalog_through_version_three(self):
        db = connect(self.data)
        try:
            self.assertEqual(db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM presets").fetchone()[0], 3)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
