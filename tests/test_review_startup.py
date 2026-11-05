"""Service startup uses only synthetic photos and temporary catalogs."""

from pathlib import Path
import tempfile
import unittest

from PIL import Image

from backend.catalog.database import connect
from backend.catalog.ingestion import preflight, sha256
from backend.review.__main__ import prepare_catalog


class ReviewStartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "data"
        self.input = self.root / "input"
        self.catalog = self.root / "catalog"

    def image(self, name: str = "one.jpg") -> Path:
        self.input.mkdir(parents=True, exist_ok=True)
        source = self.input / name
        Image.new("RGB", (20, 10), "red").save(source)
        return source

    def test_fresh_start_creates_catalog_and_repeat_keeps_same_photo(self):
        source = self.image()
        before = sha256(source)
        prepare_catalog(self.catalog)
        first = preflight(self.catalog)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["source"], "OK")
        self.assertEqual(first[0]["thumbnail"], "OK")
        self.assertEqual(sha256(source), before)
        for folder in ("exports", "backups", "evidence", "models"):
            self.assertTrue((self.root / folder).is_dir())
        prepare_catalog(self.catalog)
        self.assertEqual(preflight(self.catalog), first)
        db = connect(self.catalog)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM photos").fetchone()[0], 1)
        finally:
            db.close()

    def test_empty_start_creates_catalog_then_later_imports(self):
        prepare_catalog(self.catalog)
        self.assertTrue((self.catalog / "catalog.sqlite").is_file())
        self.assertEqual(preflight(self.catalog), [])
        self.image()
        prepare_catalog(self.catalog)
        self.assertEqual(len(preflight(self.catalog)), 1)

    def test_existing_catalog_with_missing_source_blocks_new_batch(self):
        source = self.image()
        prepare_catalog(self.catalog)
        source.rename(self.input / "moved.jpg")
        self.image("different.jpg")
        with self.assertRaisesRegex(SystemExit, "missing or changed media"):
            prepare_catalog(self.catalog)
        db = connect(self.catalog)
        try:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM photos").fetchone()[0], 1)
        finally:
            db.close()

    def test_corrupt_photo_blocks_service_start(self):
        self.input.mkdir(parents=True)
        broken = self.input / "broken.jpg"
        broken.write_bytes(b"not an image")
        with self.assertRaisesRegex(SystemExit, "Photo import failed"):
            prepare_catalog(self.catalog)
        self.assertEqual(broken.read_bytes(), b"not an image")


if __name__ == "__main__":
    unittest.main()
