"""Phase 06 export uses only synthetic images and makes no paid provider call."""

from decimal import Decimal
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.catalog.database import connect
from backend.catalog.ingestion import import_photo, sha256
from backend.review.app import create_app
from backend.review.editing import enqueue_batch, review_version, run_job
from backend.review.export import ExportError, audit_artifacts, create_export, preview_export, recent_exports
from backend.review.export_cli import backup_database
from backend.review.c2pa_signing import SigningConfig
from scripts.migrate_data_layout import inspect_layout, migrate_layout


class NoNetworkEditor:
    model = "not-used"
    estimated_cost_usd = Decimal("0.10")

    def edit(self, *_args):
        raise AssertionError("Export tests must not call a paid editor")


class ExportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "data"
        self.source = self.root / "source.jpg"
        exif = Image.Exif()
        exif[271] = "Synthetic camera"
        Image.new("RGB", (1200, 800), "#938069").save(self.source, exif=exif)
        self.source_hash = sha256(self.source)
        self.photo_id = import_photo(self.data, self.source)["id"]
        self.editor = NoNetworkEditor()
        self.client = TestClient(create_app(self.data, edit_provider=self.editor))
        saved = self.client.patch(f"/api/photos/{self.photo_id}", json={
            "expected_revision": 0, "primary_subject": "Architecture",
            "content_tags": ["arch"], "condition_tags": [],
            "editorial_description": "A stone building", "city": "Berlin", "country": "Germany",
            "preset_id": "architecture-clarity", "publication_profile_id": "website-standard-v1",
            "ai_allowance": 0, "user_instructions": "Keep stone texture", "review_state": "REVIEWED",
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        db = connect(self.data)
        try:
            db.execute("UPDATE photos SET private_lat=52.52,private_lon=13.405 WHERE id=?", (self.photo_id,))
            db.commit()
        finally:
            db.close()
        prompt = self.client.post(f"/api/photos/{self.photo_id}/prompts/compile")
        self.assertEqual(prompt.status_code, 200, prompt.text)
        self.assertEqual(self.client.post(f"/api/prompts/{prompt.json()['id']}/approve").status_code, 200)

    def _approved(self):
        jobs = enqueue_batch(self.data, [self.photo_id], "DETERMINISTIC", {"exposure": 1.0},
                             self.editor, authorized=True, budget_usd=None,
                             request_key="synthetic-export-edit")
        result = run_job(self.data, jobs[0]["id"], self.editor)
        self.assertEqual(result["status"], "SUCCEEDED", result["error"])
        version_id = result["image_version_id"]
        review_version(self.data, self.photo_id, version_id, "APPROVED", None)
        return version_id

    def test_only_approved_bytes_export_with_private_gps_removed(self):
        self.assertEqual(preview_export(self.data)["approved_count"], 0)
        with self.assertRaisesRegex(ExportError, "No approved"):
            create_export(self.data)
        version_id = self._approved()
        preview = preview_export(self.data)
        self.assertEqual(preview["approved_count"], 1)
        self.assertEqual(preview["items"][0]["version_id"], version_id)
        exported = create_export(self.data)
        folder = self.data / exported["directory"]
        manifest_bytes = (folder / "manifest.json").read_bytes()
        manifest = json.loads(manifest_bytes)
        item = manifest["items"][0]
        db = connect(self.data)
        try:
            version = db.execute("SELECT path,sha256,width,height FROM image_versions WHERE id=?", (version_id,)).fetchone()
            self.assertEqual(db.execute("SELECT COUNT(*) FROM export_items").fetchone()[0], 1)
        finally:
            db.close()
        self.assertEqual((folder / item["image"]).read_bytes(), (self.data / version["path"]).read_bytes())
        self.assertEqual(item["sha256"], version["sha256"])
        self.assertEqual((item["width"], item["height"]), (version["width"], version["height"]))
        self.assertEqual(item["location"], {"city": "Berlin", "country": "Germany"})
        self.assertNotIn(b"52.52", manifest_bytes)
        self.assertNotIn(b"13.405", manifest_bytes)
        self.assertNotIn(b"original_path", manifest_bytes)
        self.assertNotIn(b"source.jpg", manifest_bytes)
        with Image.open(folder / item["image"]) as image:
            self.assertFalse(image.getexif())
        with Image.open(folder / item["thumbnail"]) as thumb:
            self.assertLessEqual(max(thumb.size), 320)
            self.assertFalse(thumb.getexif())
        cost = json.loads((folder / "cost_report.json").read_text(encoding="utf-8"))
        self.assertEqual(cost["operations"]["editing"]["attempts"], 1)
        self.assertEqual(cost["operations"]["editing"]["known_actual_usd"], "0.0")
        self.assertEqual(audit_artifacts(self.data)["missing"], [])
        self.assertEqual(sha256(self.source), self.source_hash)

    def test_optional_signed_copy_keeps_approved_bytes_and_private_text_out_of_manifest(self):
        version_id = self._approved()
        credential = SigningConfig(self.root / "cert.pem", self.root / "key.pem")

        def fake_sign(source, target, *, approved_version_id, operations, config):
            self.assertEqual(approved_version_id, version_id)
            self.assertEqual(config, credential)
            self.assertEqual(operations[0]["class"], "deterministic publication edit")
            target.write_bytes(source.read_bytes() + b"signed-test-copy")
            return {"path": target, "sha256": sha256(target),
                    "signer_identity": "CN=Test", "signer_cert_sha256": "f" * 64}

        with patch("backend.review.export.sign_copy", side_effect=fake_sign):
            exported = create_export(self.data, signing=credential)
        folder = self.data / exported["directory"]
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        item = manifest["items"][0]
        db = connect(self.data)
        try:
            approved_path = db.execute("SELECT path FROM image_versions WHERE id=?", (version_id,)).fetchone()["path"]
        finally:
            db.close()
        self.assertEqual((folder / item["image"]).read_bytes(), (self.data / approved_path).read_bytes())
        self.assertNotEqual(item["sha256"], item["signed_copy"]["sha256"])
        self.assertEqual(item["signed_copy"]["signer_identity"], "CN=Test")
        self.assertNotIn("Keep stone texture", json.dumps(manifest))
        self.assertNotIn("source.jpg", json.dumps(manifest))
        db = connect(self.data)
        try:
            saved = db.execute("SELECT signed_path,signed_sha256 FROM export_items WHERE export_id=?", (exported["export_id"],)).fetchone()
            self.assertEqual(saved["signed_sha256"], item["signed_copy"]["sha256"])
            self.assertTrue(saved["signed_path"].endswith(item["signed_copy"]["image"]))
        finally:
            db.close()
        self.assertEqual(sha256(self.source), self.source_hash)

    def test_rejected_and_changed_approved_artifacts_never_export(self):
        version_id = self._approved()
        db = connect(self.data)
        try:
            path = self.data / db.execute("SELECT path FROM image_versions WHERE id=?", (version_id,)).fetchone()[0]
        finally:
            db.close()
        path.write_bytes(b"damaged synthetic artifact")
        with self.assertRaisesRegex(ExportError, "missing or changed"):
            create_export(self.data)
        self.assertIn(path.relative_to(self.data).as_posix(), audit_artifacts(self.data)["changed"])
        self.assertEqual(sha256(self.source), self.source_hash)

    def test_rejected_version_is_retained_but_not_publishable(self):
        jobs = enqueue_batch(self.data, [self.photo_id], "DETERMINISTIC", {"exposure": 1.0},
                             self.editor, authorized=True, budget_usd=None,
                             request_key="synthetic-rejected-edit")
        result = run_job(self.data, jobs[0]["id"], self.editor)
        self.assertEqual(result["status"], "SUCCEEDED")
        review_version(self.data, self.photo_id, result["image_version_id"], "REJECTED", "Not suitable")
        self.assertEqual(preview_export(self.data)["approved_count"], 0)
        with self.assertRaisesRegex(ExportError, "No approved"):
            create_export(self.data)
        db = connect(self.data)
        try:
            version = db.execute("SELECT path FROM image_versions WHERE id=?", (result["image_version_id"],)).fetchone()
            self.assertTrue((self.data / version["path"]).is_file())
        finally:
            db.close()

    def test_api_authorization_backup_restore_and_orphan_audit(self):
        self._approved()
        self.assertEqual(self.client.post("/api/export", json={"authorized": False}).status_code, 403)
        self.assertEqual(self.client.get("/api/export/preview").json()["approved_count"], 1)
        first = self.client.post("/api/export", json={"authorized": True})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(self.client.get("/api/export/history").json()[0]["export_id"], first.json()["export_id"])
        manifest_response = self.client.get(f"/api/export/{first.json()['export_id']}/manifest")
        self.assertEqual(manifest_response.status_code, 200)
        self.assertEqual(manifest_response.json()["export_id"], first.json()["export_id"])
        denied_open = self.client.post(f"/api/export/{first.json()['export_id']}/open-folder")
        self.assertEqual(denied_open.status_code, 403)
        with patch("backend.review.app.subprocess.Popen") as opener:
            opened = self.client.post(f"/api/export/{first.json()['export_id']}/open-folder",
                                      headers={"X-Local-Action": "open-export-folder"}, json={})
        self.assertEqual(opened.status_code, 200, opened.text)
        self.assertTrue(opener.called)
        backup = backup_database(self.data, self.root / "backups" / "catalog.sqlite")
        self.assertTrue(backup.is_file())
        with self.assertRaises(FileExistsError):
            backup_database(self.data, backup)
        restored = self.root / "restored"
        shutil.copytree(self.data, restored)
        shutil.copy2(backup, restored / "catalog.sqlite")
        self.assertEqual(preview_export(restored)["approved_count"], 1)
        self.assertEqual(audit_artifacts(restored)["missing"], [])
        orphan = restored / "exports" / "stray.txt"
        orphan.write_text("synthetic orphan", encoding="utf-8")
        self.assertIn("exports/stray.txt", audit_artifacts(restored)["orphaned"])
        self.assertTrue(orphan.is_file())
        manifest_path = restored / first.json()["manifest"]
        manifest_path.write_text('{"broken": true}', encoding="utf-8")
        self.assertIn(first.json()["manifest"], audit_artifacts(restored)["invalid_manifests"])
        self.assertEqual(sha256(self.source), self.source_hash)

    def test_backup_of_phase_five_catalog_does_not_migrate_source(self):
        legacy = self.root / "phase05"
        legacy.mkdir()
        scripts = sorted((Path(__file__).resolve().parents[1] / "backend/catalog/migrations").glob("*.sql"))[:7]
        db = sqlite3.connect(legacy / "catalog.sqlite")
        try:
            for script in scripts:
                db.executescript(script.read_text(encoding="utf-8"))
        finally:
            db.close()
        backup = backup_database(legacy, self.root / "pre-migration.sqlite")
        for path in (legacy / "catalog.sqlite", backup):
            db = sqlite3.connect(path)
            try:
                self.assertEqual(db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 7)
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                db.close()

    def test_canonical_copy_keeps_existing_export_and_source(self):
        version_id = self._approved()
        old_export = create_export(self.data)
        target = self.root / "final" / "data"
        plan = inspect_layout(self.data, target)
        self.assertEqual(plan["external_originals_preserved"], 1)
        moved = migrate_layout(self.data, target)
        self.assertEqual(moved["approved_count"], 1)
        self.assertTrue((target / "exports" / old_export["export_id"] / "manifest.json").is_file())
        self.assertEqual(recent_exports(target / "catalog")[0]["export_id"], old_export["export_id"])
        self.assertEqual(audit_artifacts(target / "catalog")["missing"], [])
        self.assertEqual(preview_export(target / "catalog")["items"][0]["version_id"], version_id)
        new_export = create_export(target / "catalog")
        self.assertTrue((target / "exports" / new_export["export_id"] / "manifest.json").is_file())
        self.assertEqual(sha256(self.source), self.source_hash)
        self.assertTrue((self.data / old_export["manifest"]).is_file())

    def test_canonical_copy_rebases_referenced_input_without_changing_bytes(self):
        source_root = self.root / "legacy"
        input_root = source_root / "input"
        input_root.mkdir(parents=True)
        source = input_root / "original.jpg"
        shutil.copy2(self.source, source)
        old_catalog = source_root / "catalog"
        photo_id = import_photo(old_catalog, source)["id"]
        target = self.root / "final" / "data"
        migrated = migrate_layout(old_catalog, target)
        self.assertEqual(migrated["input_originals"], 1)
        db = connect(target / "catalog")
        try:
            new_path = Path(db.execute("SELECT original_path FROM photos WHERE id=?", (photo_id,)).fetchone()[0])
        finally:
            db.close()
        self.assertEqual(new_path.resolve(), (target / "input" / "original.jpg").resolve())
        self.assertEqual(sha256(new_path), self.source_hash)
        self.assertEqual(sha256(source), self.source_hash)


if __name__ == "__main__":
    unittest.main()
