"""Private server configuration uses synthetic values and never calls the API."""

from pathlib import Path
import tempfile
import unittest

from backend.review.local_config import load_local_config


class LocalConfigTests(unittest.TestCase):
    def test_copied_example_loads_private_values_without_logging_them(self):
        example = Path(__file__).resolve().parents[1] / "config" / "openAI.example.env"
        self.assertTrue(example.is_file())
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "openAI.env"
            private.write_text(
                example.read_text(encoding="utf-8")
                .replace("YOUR_KEY_HERE", "synthetic-secret"),
                encoding="utf-8",
            )
            environment: dict[str, str] = {}
            self.assertTrue(load_local_config(private, environment))
            self.assertEqual(environment["OPENAI_API_KEY"], "synthetic-secret")
            self.assertEqual(environment["PHOTO_EDIT_MODEL"], "gpt-image-2.5-sunburst")
            self.assertEqual(environment["PHOTO_EDIT_PLANNING_COST_USD"], "0.10")

    def test_process_credentials_override_file_and_missing_file_is_optional(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "openAI.env"
            self.assertFalse(load_local_config(private, {}))
            private.write_text('OPENAI_API_KEY="synthetic-file-key"\nPHOTO_EDIT_PLANNING_COST_USD="0.50"\n', encoding="utf-8")
            environment = {"OPENAI_API_KEY": "synthetic-process-key"}
            self.assertTrue(load_local_config(private, environment))
            self.assertEqual(environment["OPENAI_API_KEY"], "synthetic-process-key")

    def test_local_planning_amount_overrides_stale_process_value(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "openAI.env"
            private.write_text('OPENAI_API_KEY="synthetic-file-key"\nPHOTO_EDIT_PLANNING_COST_USD="0.10"\n', encoding="utf-8")
            environment = {"PHOTO_EDIT_PLANNING_COST_USD": "1"}
            self.assertTrue(load_local_config(private, environment))
            self.assertEqual(environment["PHOTO_EDIT_PLANNING_COST_USD"], "0.10")

            private.write_text('OPENAI_API_KEY="synthetic-file-key"\nPHOTO_EDIT_PLANNING_COST_USD=""\n', encoding="utf-8")
            environment["PHOTO_EDIT_PLANNING_COST_USD"] = "1"
            self.assertTrue(load_local_config(private, environment))
            self.assertEqual(environment["PHOTO_EDIT_PLANNING_COST_USD"], "1")

    def test_unfilled_template_fails_without_exposing_values(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "openAI.env"
            private.write_text('OPENAI_API_KEY="YOUR_KEY_HERE"\nPHOTO_EDIT_PLANNING_COST_USD="YOUR_ESTIMATE_HERE"\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "replace the OPENAI_API_KEY example value"):
                load_local_config(private, {})
