"""Phase 01 tests use only tiny synthetic images in temporary directories."""

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

from PIL import Image

from backend.catalog.database import connect
from backend.catalog.ingestion import (
    ImportErrorDetail, _gps_decimal, import_folder, import_photo, preflight, relink_photo, sha256,
)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.sources = self.root / "sources"
        self.sources.mkdir()

    def image(self, name="one.jpg", format="JPEG", color="red", exif=None):
        path = self.sources / name
        image = Image.new("RGB", (20, 10), color)
        options = {"exif": exif} if exif is not None else {}
        image.save(path, format=format, **options)
        return path

    def row(self, photo_id):
        db = connect(self.data)
        try:
            return dict(db.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone())
        finally:
            db.close()

    def test_reference_import_restart_and_source_integrity(self):
        source = self.image()
        before = sha256(source)
        result = import_photo(self.data, source)
        self.assertEqual(result["status"], "imported")
        self.assertEqual(import_photo(self.data, source)["id"], result["id"])
        row = self.row(result["id"])
        self.assertEqual(row["sha256"], before)
        self.assertEqual(row["thumbnail_sha256"], sha256(self.data / row["thumbnail_path"]))
        self.assertEqual(row["original_path"], str(source.resolve()))
        self.assertIsNone(row["managed_original_path"])
        self.assertIsNone(row["private_lat"])
        self.assertIsNone(row["capture_offset"])
        self.assertEqual(sha256(source), before)
        self.assertEqual(preflight(self.data)[0]["source"], "OK")
        self.assertTrue((self.data / row["thumbnail_path"]).is_file())

    def test_managed_copy_and_orientation_preview(self):
        exif = Image.Exif()
        exif[274] = 6
        exif[306] = "2020:01:02 03:04:05"
        source = self.image(exif=exif)
        before = sha256(source)
        result = import_photo(self.data, source, mode="copy")
        row = self.row(result["id"])
        self.assertEqual(row["orientation"], 6)
        self.assertEqual(row["capture_datetime_raw"], "2020:01:02 03:04:05")
        self.assertEqual(sha256(source), before)
        self.assertEqual(sha256(self.data / row["managed_original_path"]), before)
        with Image.open(self.data / row["thumbnail_path"]) as thumb:
            self.assertEqual(thumb.size, (10, 20))
        self.assertEqual(preflight(self.data)[0]["managed"], "OK")

    def test_duplicate_keeps_separate_photo_and_original(self):
        first = self.image()
        second = self.sources / "another.jpg"
        second.write_bytes(first.read_bytes())
        one = import_photo(self.data, first)
        two = import_photo(self.data, second)
        self.assertNotEqual(one["id"], two["id"])
        self.assertEqual(two["duplicate_of_id"], one["id"])
        self.assertEqual(sha256(first), sha256(second))

    def test_corrupt_file_rejected_without_catalog_row(self):
        source = self.sources / "broken.jpg"
        source.write_bytes(b"not an image")
        before = sha256(source)
        with self.assertRaises(ImportErrorDetail):
            import_photo(self.data, source)
        self.assertEqual(sha256(source), before)
        db = connect(self.data)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM photos").fetchone()[0], 0)
        finally:
            db.close()

    def test_path_conflict_and_changed_preflight(self):
        source = self.image()
        photo_id = import_photo(self.data, source)["id"]
        self.image(color="blue")
        self.assertEqual(preflight(self.data)[0]["source"], "CHANGED")
        with self.assertRaisesRegex(ImportErrorDetail, "Path conflict"):
            import_photo(self.data, source)
        self.assertEqual(self.row(photo_id)["source_missing"], 0)

    def test_missing_and_relink_preserves_id(self):
        source = self.image()
        photo_id = import_photo(self.data, source)["id"]
        moved = self.sources / "moved.jpg"
        source.rename(moved)
        self.assertEqual(preflight(self.data)[0]["source"], "MISSING")
        self.assertEqual(self.row(photo_id)["source_missing"], 1)
        relink_photo(self.data, photo_id, moved)
        self.assertEqual(self.row(photo_id)["original_path"], str(moved.resolve()))
        self.assertEqual(preflight(self.data)[0]["source"], "OK")
        self.assertEqual(self.row(photo_id)["id"], photo_id)

    def test_relink_requires_same_bytes_and_unclaimed_path(self):
        first = self.image()
        second = self.image("two.jpg", color="blue")
        one_id = import_photo(self.data, first)["id"]
        import_photo(self.data, second)
        with self.assertRaises(ImportErrorDetail):
            relink_photo(self.data, one_id, second)

    def test_multiformat_and_sidecar_report(self):
        for name, format in (("a.jpg", "JPEG"), ("b.png", "PNG"),
                             ("c.tif", "TIFF"), ("d.webp", "WEBP")):
            self.image(name, format)
        (self.sources / "a.xmp").write_text("sidecar", encoding="utf-8")
        (self.sources / "unsupported.heic").write_bytes(b"placeholder")
        results = import_folder(self.data, self.sources)
        self.assertEqual(len(results["imported"]), 4)
        self.assertEqual(len(results["sidecars"]), 1)
        self.assertEqual(len(results["unsupported"]), 1)
        self.assertEqual(results["errors"], [])
        again = import_folder(self.data, self.sources)
        self.assertEqual(len(again["existing"]), 4)
        self.assertEqual({item["id"] for item in again["existing"]},
                         {item["id"] for item in results["imported"]})

    def test_gps_conversion_missing_and_invalid(self):
        self.assertIsNone(_gps_decimal({}, (2, 1), "N", "S"))
        self.assertIsNone(_gps_decimal({2: (999, 0, 0), 1: "N"}, (2, 1), "N", "S"))
        self.assertAlmostEqual(_gps_decimal({2: (52, 30, 0), 1: "S"}, (2, 1), "N", "S"), -52.5)

    def test_exif_ifd_capture_and_private_gps(self):
        exif = Image.Exif()
        exif[34665] = {36867: "2024:06:07 08:09:10", 36881: "+02:00", 42036: "Test lens"}
        exif[34853] = {1: "N", 2: (52, 30, 0), 3: "E", 4: (13, 24, 0)}
        source = self.image(exif=exif)
        row = self.row(import_photo(self.data, source)["id"])
        self.assertEqual(row["capture_datetime_raw"], "2024:06:07 08:09:10")
        self.assertEqual(row["capture_offset"], "+02:00")
        self.assertEqual(row["lens"], "Test lens")
        self.assertAlmostEqual(row["private_lat"], 52.5)
        self.assertAlmostEqual(row["private_lon"], 13.4)
        self.assertIn("ExifIFD", json.loads(row["original_exif_json"]))

    def test_malformed_exif_does_not_mutate_image(self):
        source = self.image(exif=b"invalid-exif-payload")
        before = sha256(source)
        row = self.row(import_photo(self.data, source)["id"])
        self.assertIsNone(row["private_lat"])
        self.assertEqual(sha256(source), before)

    def test_migration_idempotent_and_review_history_constraints(self):
        source = self.image()
        photo_id = import_photo(self.data, source)["id"]
        db = connect(self.data)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], 2)
            self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            values = (str(uuid4()), photo_id, 1, "edited/test.png", "0" * 64, 20, 10, "2026-01-01T00:00:00Z", "APPROVED")
            db.execute("INSERT INTO image_versions(id,photo_id,version_number,path,sha256,width,height,created_at,review_status) VALUES (?,?,?,?,?,?,?,?,?)", values)
            db.execute("INSERT INTO review_events(id,version_id,actor,reviewed_at,previous_status,next_status) VALUES (?,?,?,?,?,?)",
                       (str(uuid4()), values[0], "test-user", "2026-01-01T00:00:00Z", "PENDING", "APPROVED"))
            db.commit()
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO image_versions(id,photo_id,version_number,path,sha256,width,height,created_at,review_status) VALUES (?,?,?,?,?,?,?,?,?)",
                           (str(uuid4()), photo_id, 2, "edited/other.png", "1" * 64, 20, 10, "2026-01-01T00:00:01Z", "APPROVED"))
            db.rollback()
            self.assertEqual(db.execute("SELECT COUNT(*) FROM review_events").fetchone()[0], 1)
        finally:
            db.close()

        db = connect(self.data)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], 2)
        finally:
            db.close()

    def test_cli_init_import_and_preflight(self):
        source = self.image()
        command = [sys.executable, "-m", "backend.catalog", "--data-dir", str(self.data)]
        root = Path(__file__).resolve().parents[1]
        initialized = subprocess.run(command + ["init"], cwd=root, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(initialized.stdout)["schema_version"], 2)
        imported = subprocess.run(command + ["import-photo", str(source)], cwd=root,
                                  capture_output=True, text=True, check=True)
        photo_id = json.loads(imported.stdout)["id"]
        listed = subprocess.run(command + ["list"], cwd=root,
                                capture_output=True, text=True, check=True)
        item = json.loads(listed.stdout)[0]
        self.assertEqual(item["id"], photo_id)
        self.assertEqual(item["original_filename"], source.name)
        self.assertTrue(Path(item["thumbnail_path"]).is_file())
        self.assertFalse(item["gps_present"])
        self.assertEqual(item["gps_status"], "ABSENT")
        checked = subprocess.run(command + ["preflight"], cwd=root,
                                 capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(checked.stdout)[0]["id"], photo_id)

    def test_cli_reports_invalid_gps_reference_without_guessing_location(self):
        exif = Image.Exif()
        exif[34853] = {1: "\x00", 2: (52, 30, 0), 3: "\x00", 4: (13, 24, 0)}
        source = self.image(exif=exif)
        photo_id = import_photo(self.data, source)["id"]
        row = self.row(photo_id)
        self.assertIsNone(row["private_lat"])
        self.assertIsNone(row["private_lon"])
        command = [sys.executable, "-m", "backend.catalog", "--data-dir", str(self.data), "list"]
        listed = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, check=True)
        item = json.loads(listed.stdout)[0]
        self.assertFalse(item["gps_present"])
        self.assertEqual(item["gps_status"], "INVALID_REFERENCE")


if __name__ == "__main__":
    unittest.main()
