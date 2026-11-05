"""Optional private-key C2PA signing of a separate approved export copy."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import c2pa
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from PIL import Image

from backend.catalog.ingestion import sha256


@dataclass(frozen=True)
class SigningConfig:
    certificate: Path
    private_key: Path


def _credentials(config: SigningConfig) -> tuple[bytes, bytes, str, str]:
    if not config.certificate.is_file() or not config.private_key.is_file():
        raise ValueError("C2PA certificate and private key must exist")
    cert_bytes = config.certificate.read_bytes()
    key_bytes = config.private_key.read_bytes()
    cert = x509.load_pem_x509_certificate(cert_bytes)
    key = serialization.load_pem_private_key(key_bytes, password=None)
    if not isinstance(cert.public_key(), rsa.RSAPublicKey) or not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("The configured C2PA signer requires an RSA PS256 certificate and key")
    if cert.public_key().public_numbers() != key.public_key().public_numbers():
        raise ValueError("C2PA certificate and private key do not match")
    return cert_bytes, key_bytes, cert.subject.rfc4514_string(), hashlib.sha256(cert_bytes).hexdigest()


def sign_copy(source: Path, target: Path, *, approved_version_id: str,
              operations: list[dict], config: SigningConfig) -> dict:
    """Sign only an export copy; the approved JPEG remains untouched."""
    cert, key, identity, cert_hash = _credentials(config)
    if source.resolve() == target.resolve() or target.exists():
        raise ValueError("Signed asset needs a new path")
    source_hash = sha256(source)
    manifest = {
        "claim_generator_info": [{"name": "Photo Mass Editor", "version": "2.4"}],
        "format": "image/jpeg", "title": "Approved travel image",
        "assertions": [
            {"label": "c2pa.actions", "data": {"actions": [
                {"action": "c2pa.created", "digitalSourceType":
                 "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCreation"}]}},
            {"label": "org.photo-mass-editor.provenance",
             "data": {"approved_version_id": approved_version_id,
                      "approved_jpeg_sha256": source_hash,
                      "operations": operations}},
        ],
    }
    info = c2pa.C2paSignerInfo(c2pa.C2paSigningAlg.PS256, cert, key, None)
    try:
        with c2pa.Context() as context, c2pa.Signer.from_info(info) as signer:
            with c2pa.Builder(manifest, context) as builder:
                with source.open("rb") as ingredient:
                    builder.add_ingredient({"title": f"Approved version {approved_version_id}"},
                                           "image/jpeg", ingredient)
                builder.sign_file(str(source), str(target), signer)
        verify_copy(target, approved_version_id, source_hash)
        with Image.open(source) as approved, Image.open(target) as signed:
            if approved.size != signed.size or approved.convert("RGB").tobytes() != signed.convert("RGB").tobytes():
                raise ValueError("C2PA copy changed image pixels")
            if signed.getexif():
                raise ValueError("C2PA copy unexpectedly contains EXIF metadata")
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {"path": target, "sha256": sha256(target), "signer_identity": identity,
            "signer_cert_sha256": cert_hash}


def verify_copy(path: Path, approved_version_id: str, approved_sha256: str) -> None:
    try:
        with c2pa.Reader(path) as reader:
            store = json.loads(reader.json())
    except c2pa.C2paError as exc:
        raise ValueError("C2PA manifest verification failed") from exc
    if not store.get("active_manifest") or not store.get("manifests"):
        raise ValueError("Signed image lacks a C2PA manifest")
    statuses = store.get("validation_status") or []
    # A private or self-signed certificate can be untrusted; binding failures are never acceptable.
    if any(item.get("code") not in ("signingCredential.untrusted",) for item in statuses):
        raise ValueError(f"C2PA verification failed: {statuses}")
    active = store["manifests"][store["active_manifest"]]
    if not active.get("ingredients"):
        raise ValueError("C2PA approved-version ingredient is missing")
    assertions = active.get("assertions") or []
    provenance = [entry.get("data") for entry in assertions
                  if entry.get("label") == "org.photo-mass-editor.provenance"]
    if len(provenance) != 1 or provenance[0].get("approved_version_id") != approved_version_id or \
            provenance[0].get("approved_jpeg_sha256") != approved_sha256:
        raise ValueError("C2PA approved-version provenance differs")
