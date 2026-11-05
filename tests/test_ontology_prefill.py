"""Synthetic recognition rules: no model download, photo upload or paid call."""

import tempfile
import unittest
from pathlib import Path

from backend.review.catalog_prefill import _proposal
from backend.review.ontology import OntologyError, load_ontology, phrases


ONTOLOGY = load_ontology()


def proposal(subject=None, content=None, conditions=None, width=800, height=600, luminance=.4):
    highs = {"primary_subject": subject or {}, "content_tags": content or {}, "condition_tags": conditions or {}}
    ranking = [{"label": f"{kind}:{name}", "similarity": highs[kind].get(name, 20.0)}
               for kind, values in ONTOLOGY["concepts"].items() for name, _, _ in values.values()]
    photo = {"width": width, "height": height, "capture_datetime_raw": None, "camera": None, "original_filename": "synthetic.jpg"}
    return _proposal(photo, {"ranking": ranking, "measurements": {"mean_luminance": luminance}},
                     {"status": "NO_GPS", "city": None, "country": None}, ONTOLOGY)


class OntologyPrefillTests(unittest.TestCase):
    def test_architecture_day_and_night_presets(self):
        day, evidence = proposal({"building": 31}, {"architecture": 29}, {"daytime": 26})
        self.assertEqual((day["primary_subject"], day["preset_id"], evidence["local_recipe"]),
                         ("building", "architecture-clarity", "architecture"))
        self.assertIn("architecture", day["content_tags"])
        self.assertIn("daytime", day["condition_tags"])
        night, evidence = proposal({"building": 31}, {"architecture": 29}, {"nighttime": 26}, luminance=.2)
        self.assertEqual((night["preset_id"], evidence["local_recipe"]), ("night-architecture", "night"))
        self.assertNotIn("daytime", night["condition_tags"])

    def test_mixed_scene_and_independent_content(self):
        item, _ = proposal({"building": 28}, {"architecture": 29, "people": 27, "urban": 26}, {"daytime": 25})
        self.assertTrue({"architecture", "people", "urban"} <= set(item["content_tags"]))
        self.assertIn("people in view", item["editorial_description"])
        uncertain, _ = proposal(content={"landscape": 28, "nature": 27, "water": 26})
        self.assertEqual(uncertain["primary_subject"], "")
        self.assertTrue({"landscape", "water"} <= set(uncertain["content_tags"]))
        self.assertEqual(uncertain["preset_id"], "panoramic-scene")
        self.assertIn("landscape", uncertain["editorial_description"])

    def test_art_ruins_animals_food_and_ambiguous(self):
        for subject, tag, preset in (("sculpture", "art", "museum-artwork"),
                                     ("archaeological ruins", "archaeology", "architecture-clarity"),
                                     ("cat", "animals", "natural-balance"),
                                     ("food", "food", "food")):
            item, _ = proposal({subject: 31})
            self.assertEqual(item["primary_subject"], subject)
            self.assertIn(tag, item["content_tags"])
            self.assertEqual(item["preset_id"], preset)
        item, _ = proposal()
        self.assertEqual(item["primary_subject"], "")
        self.assertEqual(item["content_tags"], [])
        indoor, _ = proposal({"souvenir": 31}, {"urban": 27}, luminance=.55)
        self.assertNotIn("daytime", indoor["condition_tags"])
        self.assertNotIn("nighttime", indoor["condition_tags"])

    def test_custom_aliases_and_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ontology.yaml"
            path.write_text("primary_subject:\n  custom:\n    - {name: lantern, aliases: [paper lamp, hanging light]}\ncontent_tags: [culture]\ncondition_tags: [daytime]\n", encoding="utf-8")
            custom = load_ontology(path)
            self.assertEqual(phrases(custom)["primary_subject:lantern"],
                             ["a travel photograph showing lantern", "paper lamp", "hanging light"])
            path.write_text("primary_subject:\n  custom: [lantern, Lantern]\ncontent_tags: [culture]\ncondition_tags: [daytime]\n", encoding="utf-8")
            with self.assertRaisesRegex(OntologyError, "Duplicate primary_subject concept"):
                load_ontology(path)
            path.write_text("primary_subject: {one: [building]}\ncontent_tags: [urban]\ncontent_tags: [water]\ncondition_tags: [daytime]\n", encoding="utf-8")
            with self.assertRaisesRegex(OntologyError, "Duplicate YAML key"):
                load_ontology(path)


if __name__ == "__main__":
    unittest.main()
