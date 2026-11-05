"""Synthetic V2 Priority 4 cost, billing, signing and bundle checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import csv
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ObjectIdentifier
from PIL import Image

from backend.catalog.database import connect
from backend.catalog.ingestion import import_photo
from backend.review.billing import import_billing
from backend.review.c2pa_signing import SigningConfig, sign_copy, verify_copy
from backend.review.costs import PRICE_VERSION, calculate
from backend.review.costs import PaidRequestError
from backend.review.openai_edit import OpenAIEditProvider
from backend.review.export import _cost_report
from scripts.frontend_bundle import fingerprint


class CostTests(unittest.TestCase):
    def test_image_usage_calculation_and_incomplete_usage(self):
        usage = {"input_tokens": 1200, "input_tokens_details": {"text_tokens": 200, "image_tokens": 1000},
                 "output_tokens": 3000}
        self.assertEqual(calculate("openai", "gpt-image-2.5-flare", usage, direct_images=True),
                         ("0.09900000", PRICE_VERSION))
        self.assertEqual(calculate("openai", "gpt-image-2.5-flare", {"input_tokens": 1200}, direct_images=True),
                         (None, None))

    def test_text_cached_usage_and_unknown_model(self):
        usage = {"input_tokens": 1000, "output_tokens": 500,
                 "input_tokens_details": {"cached_tokens": 400}}
        self.assertEqual(calculate("openai", "gpt-6-luna", usage), ("0.00031400", PRICE_VERSION))
        self.assertEqual(calculate("openai", "other", usage), (None, None))

    def test_bundle_fingerprint_is_repeatable(self):
        self.assertEqual(fingerprint(), fingerprint())

    def test_failed_image_response_keeps_request_identity_and_usage(self):
        class Response(BytesIO):
            headers = {"x-request-id": "req-image-failed"}

        with tempfile.TemporaryDirectory() as temporary:
            derivative = Path(temporary) / "publication.jpg"
            Image.new("RGB", (512, 512), "blue").save(derivative, "JPEG")
            provider = OpenAIEditProvider(api_key="synthetic", model="gpt-image-2.5-flare",
                                          planning_cost_usd=Decimal("0.10"))
            response = Response(json.dumps({"data": [], "usage": {"input_tokens": 10,
                "input_tokens_details": {"text_tokens": 2, "image_tokens": 8},
                "output_tokens": 0}}).encode())
            with patch("backend.review.openai_edit.urlopen", return_value=response):
                with self.assertRaises(PaidRequestError) as caught:
                    provider.edit(derivative, "Preserve scene", None)
            self.assertEqual(caught.exception.request_id, "req-image-failed")
            self.assertEqual(caught.exception.usage["input_tokens"], 10)

    def test_billing_reconciliation_keeps_planning_and_calculation_distinct(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.jpg"
            Image.new("RGB", (24, 24), "red").save(source, "JPEG")
            photo_id = import_photo(root / "catalog", source)["id"]
            db = connect(root / "catalog")
            try:
                db.execute("""INSERT INTO analysis_runs(id,photo_id,source_hash,provider,model,
                    template_version,config_signature,status,estimated_cost,currency,analyzed_at,
                    request_id,calculated_cost_usd,price_version,usage_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    ("run-1", photo_id, "a" * 64, "openai", "gpt-6-luna", "t1", "c1",
                     "SUCCEEDED", 0.1, "USD", "2026-11-04T00:00:00Z", "req-1", "0.03", PRICE_VERSION,
                     '{"input_tokens": 100}'))
                db.commit()
                report = _cost_report(db, "export-1", "2026-11-05T00:00:00Z")
                self.assertEqual(report["operations"]["analysis"]["estimated_usd"], "0.1")
                self.assertEqual(report["operations"]["analysis"]["calculated_usd"], "0.03")
                self.assertEqual(report["operations"]["analysis"]["actual_cost_unknown_count"], 1)
            finally:
                db.close()
            billing = root / "billing.csv"
            with billing.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["operation", "receipt_id", "provider_request_id", "billed_usd"])
                writer.writerow(["analysis", "run-1", "wrong-request", "0.04"])
            with self.assertRaisesRegex(ValueError, "identity"):
                import_billing(root / "catalog", billing)
            with billing.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["operation", "receipt_id", "provider_request_id", "billed_usd"])
                writer.writerow(["analysis", "run-1", "req-1", "0.04"])
            self.assertEqual(import_billing(root / "catalog", billing)["reconciled"], 1)
            db = connect(root / "catalog")
            try:
                report = _cost_report(db, "export-2", "2026-11-05T00:00:00Z")
                self.assertEqual(report["operations"]["analysis"]["reconciled_usd"], "0.04")
                self.assertEqual(report["operations"]["analysis"]["actual_cost_unknown_count"], 0)
            finally:
                db.close()
            with self.assertRaises(ValueError):
                import_billing(root / "catalog", billing)


class SigningTests(unittest.TestCase):
    def test_signed_copy_has_ingredient_and_tamper_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            now = datetime.now(timezone.utc)
            ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Local test CA")])
            leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Local test signer")])
            ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
                  .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
                  .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
                  .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                  .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
                  .sign(ca_key, hashes.SHA256()))
            leaf = (x509.CertificateBuilder().subject_name(leaf_name).issuer_name(ca_name)
                    .public_key(leaf_key.public_key()).serial_number(x509.random_serial_number())
                    .not_valid_before(now - timedelta(hours=1)).not_valid_after(now + timedelta(days=1))
                    .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                    .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), critical=True)
                    .add_extension(x509.ExtendedKeyUsage([ObjectIdentifier("1.3.6.1.4.1.62558.2.1"),
                                                          ObjectIdentifier("1.3.6.1.5.5.7.3.36"),
                                                          ObjectIdentifier("1.3.6.1.5.5.7.3.4")]), critical=False)
                    .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
                    .sign(ca_key, hashes.SHA256()))
            cert_path, key_path = root / "cert.pem", root / "key.pem"
            cert_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM) + ca.public_bytes(serialization.Encoding.PEM))
            key_path.write_bytes(leaf_key.private_bytes(serialization.Encoding.PEM,
                                                        serialization.PrivateFormat.PKCS8,
                                                        serialization.NoEncryption()))
            original, signed = root / "approved.jpg", root / "signed.jpg"
            Image.new("RGB", (32, 32), "blue").save(original, "JPEG")
            before = original.read_bytes()
            result = sign_copy(original, signed, approved_version_id="version-1",
                               operations=[{"class": "deterministic local correction"}],
                               config=SigningConfig(cert_path, key_path))
            self.assertEqual(original.read_bytes(), before)
            self.assertNotEqual(signed.read_bytes(), before)
            self.assertEqual(result["path"], signed)
            self.assertNotIn(str(root).encode(), signed.read_bytes())
            self.assertNotIn(b"private_lat", signed.read_bytes())
            self.assertNotIn(b"Owner instructions", signed.read_bytes())
            verify_copy(signed, "version-1", hashlib.sha256(before).hexdigest())
            tampered = root / "tampered.jpg"
            changed = bytearray(signed.read_bytes())
            changed[-2] ^= 1
            tampered.write_bytes(changed)
            with self.assertRaises((ValueError, RuntimeError)):
                verify_copy(tampered, "version-1", hashlib.sha256(before).hexdigest())


if __name__ == "__main__":
    unittest.main()
